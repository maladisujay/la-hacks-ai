"""Concierge: the agent people talk to in ASI:One.

Speaks the Agent Chat Protocol, runs the LangGraph shopping graph (one durable thread per
chat window), turns each graph interrupt into an Interactive Card or a Payment Protocol
request, and reaches the four worker agents through `AgentBus`.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from uagents import Agent, Context, Protocol
from uagents.crypto import Identity
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    chat_protocol_spec,
)
from uagents_core.contrib.protocols.payment import (
    CancelPayment,
    CommitPayment,
    CompletePayment,
    Funds,
    RejectPayment,
    RequestPayment,
    payment_protocol_spec,
)

from .. import cards
from ..config import DATA_DIR, settings
from ..graph import Command, build_graph, initial_state
from ..messages import (
    CheckoutResponse,
    CurateResponse,
    FileRequest,
    FileResponse,
    FulfilResponse,
    QuoteResponse,
    RenderResponse,
    SpotsRequest,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
)

ADDR = {name: Identity.from_seed(seed, 0).address for name, seed in (
    ("curator", settings.curator_seed),
    ("renderer", settings.renderer_seed),
    ("checkout", settings.checkout_seed),
    ("ledger", settings.ledger_seed),
)}

README = Path(__file__).parent / "readmes" / "concierge.md"

concierge = Agent(
    name="strata-concierge",
    seed=settings.concierge_seed,
    port=8001,
    mailbox=True,
    handle="strata",
    description=(
        "Shop for design assets without leaving the chat. Strata picks the spot in your team's design "
        "file, ranks illustrations and icons by your team's learned taste, shows each one placed on your "
        "real design, checks your spending limit, takes payment, and places the licensed asset in the file."
    ),
    readme_path=str(README) if README.exists() else None,
    publish_agent_details=True,
)

chat = Protocol(spec=chat_protocol_spec)
payments = Protocol(spec=payment_protocol_spec, role="seller")
_graph = None
_graph_lock = asyncio.Lock()


async def get_graph():
    """SQLite-backed graph, opened on first use so no message can race a startup hook.

    Threads survive restarts: a half-finished purchase resumes where the user left it.
    """
    global _graph
    async with _graph_lock:
        if _graph is None:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            conn = await aiosqlite.connect(str(DATA_DIR / "concierge_threads.sqlite"))
            _graph = build_graph(AsyncSqliteSaver(conn))
    return _graph


class WorkerError(RuntimeError):
    pass


class AgentBus:
    """The graph's view of the four worker agents, over uAgents request/response."""

    def __init__(self, ctx: Context):
        self.ctx = ctx

    async def _call(self, worker: str, msg, resp_type, timeout: int = 45):
        reply, status = await self.ctx.send_and_receive(ADDR[worker], msg, response_type=resp_type, timeout=timeout)
        if reply is None:
            # Raising lets the node's RetryPolicy try again before the run fails.
            raise WorkerError(f"{worker} did not answer: {getattr(status, 'detail', status)}")
        return reply

    async def get_file(self, file_id: str) -> dict:
        r: FileResponse = await self._call("ledger", FileRequest(file_id=file_id), FileResponse)
        if not r.ok:
            raise WorkerError(r.error or "file unavailable")
        return json.loads(r.file_json)

    async def spots(self, file_id: str):
        return await self._call("renderer", SpotsRequest(file_id=file_id), RenderResponse, timeout=60)

    async def curate(self, req):
        return await self._call("curator", req, CurateResponse, timeout=60)

    async def render(self, req):
        return await self._call("renderer", req, RenderResponse, timeout=60)

    async def quote(self, req):
        return await self._call("checkout", req, QuoteResponse)

    async def checkout(self, req):
        return await self._call("checkout", req, CheckoutResponse)

    async def verify(self, checkout_session_id: str):
        return await self._call("checkout", VerifyPaymentRequest(checkout_session_id=checkout_session_id),
                                VerifyPaymentResponse)

    async def fulfil(self, req):
        return await self._call("ledger", req, FulfilResponse, timeout=60)


# ---------------------------------------------------------------- threads


def _window_changed(ctx: Context, sender: str) -> bool:
    """ASI:One reuses the sender across chat windows; the session id tells windows apart."""
    window = str(ctx.session)
    changed = ctx.storage.get(f"window:{sender}") not in (None, window)
    ctx.storage.set(f"window:{sender}", window)
    return changed


def _thread(ctx: Context, sender: str, new: bool = False) -> str:
    """The sender's current LangGraph thread, or a fresh one when `new`."""
    current = ctx.storage.get(f"thread:{sender}")
    if new or not current:
        n = int(ctx.storage.get(f"n:{sender}") or 0) + 1
        ctx.storage.set(f"n:{sender}", n)
        current = f"{sender}:{n}"
        ctx.storage.set(f"thread:{sender}", current)
    return current


def _current_thread(ctx: Context, sender: str) -> str:
    return ctx.storage.get(f"thread:{sender}") or _thread(ctx, sender)


def _config(ctx: Context, thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id, "bus": AgentBus(ctx)}}


async def _pending(cfg: dict):
    snap = await (await get_graph()).aget_state(cfg)
    if snap.next and snap.tasks and snap.tasks[0].interrupts:
        return snap.tasks[0].interrupts[0].value
    return None


# ---------------------------------------------------------------- running the graph


async def _run(ctx: Context, sender: str, cfg: dict, payload) -> dict | None:
    try:
        result = await (await get_graph()).ainvoke(payload, cfg, durability="sync")
    except Exception as exc:  # a worker stayed down after retries
        ctx.logger.error(f"graph failed: {exc}")
        _thread(ctx, sender, new=True)
        await ctx.send(sender, cards.text_message(
            "Something on our side didn't answer in time, and nothing was charged. "
            "Say “try again” and I'll start over from your file."))
        return None
    await _emit(ctx, sender, result)
    return result


async def _emit(ctx: Context, sender: str, result: dict) -> None:
    interrupts = result.get("__interrupt__") or []
    if interrupts:
        value = interrupts[0].value
        if value.get("type") == "payment":
            await _request_payment(ctx, sender, value["payment"])
        else:
            await ctx.send(sender, cards.to_message(value))
        return
    if result.get("receipt"):
        tx = result["payment"].get("verified_id")
        ctx.storage.set(f"fulfilled:{tx}", True)
        await ctx.send(sender, CompletePayment(transaction_id=tx))
        await ctx.send(sender, cards.to_message(cards.receipt(result)))
        _thread(ctx, sender, new=True)
        return
    await ctx.send(sender, cards.text_message(result.get("note") or "All done."))
    _thread(ctx, sender, new=True)


async def _request_payment(ctx: Context, sender: str, p: dict) -> None:
    if str(p.get("checkout_session_id", "")).startswith("cs_sim_"):
        # No Stripe key configured: say so plainly and continue as a simulated test payment.
        await ctx.send(sender, cards.text_message("Test mode without Stripe keys: payment is simulated, nothing is charged."))
        await _run(ctx, sender, _config(ctx, _current_thread(ctx, sender)),
                   Command(resume={"transaction_id": p["checkout_session_id"]}))
        return
    # Sent alone: a text message in the same turn makes ASI:One hide the payment sheet.
    await ctx.send(sender, RequestPayment(
        accepted_funds=[Funds(currency="USD", amount=f"{p['amount_cents'] / 100:.2f}", payment_method="stripe")],
        recipient=str(ctx.agent.address),
        deadline_seconds=1800,
        reference=p["reference"],
        description=f"{p['title']} · Strata",
        metadata={"stripe": {
            "ui_mode": "embedded",
            "publishable_key": p.get("publishable_key") or "",
            "client_secret": p.get("client_secret") or "",
            "checkout_session_id": p.get("checkout_session_id") or "",
            "currency": "usd",
            "amount_cents": str(p["amount_cents"]),
        }},
    ))


# ---------------------------------------------------------------- chat protocol


@chat.on_message(ChatMessage)
async def on_chat(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, ChatAcknowledgement(acknowledged_msg_id=msg.msg_id))
    seen_key = f"seen:{msg.msg_id}"
    if ctx.storage.get(seen_key):
        return  # redelivered message: acknowledge again, never act twice
    ctx.storage.set(seen_key, True)
    try:
        await _handle(ctx, sender, msg)
    except Exception as exc:
        ctx.logger.exception("concierge handler crashed")
        await ctx.send(sender, cards.text_message(f"Something went wrong on my end ({exc}). Say “try again”."))


async def _handle(ctx: Context, sender: str, msg: ChatMessage) -> None:
    text = cards.clean_text(msg.text())
    if not text:
        return  # session start/end markers carry no text

    low = text.lower()
    reply = cards.parse_reply(text)
    is_card_reply = "step" in reply
    # A typed message in a new chat window starts fresh; a click on an open card never does.
    restart = low in ("try again", "start over", "restart", "new") or (
        _window_changed(ctx, sender) and not is_card_reply)
    cfg = _config(ctx, _thread(ctx, sender, new=restart))
    pending = None if restart else await _pending(cfg)

    if pending is None:
        if reply.get("step") == "next":  # "Fix the icons" on the last receipt
            spot = reply.get("spot")
            if not spot or spot == "none":
                await ctx.send(sender, cards.text_message("Okay. Your file is up to date in Strata."))
                return
            text = f"shop for the {spot.replace('-', ' ')}"
        await _run(ctx, sender, cfg, initial_state(text))
        return

    if pending.get("type") == "payment":
        p = pending["payment"]
        if any(w in low for w in ("cancel", "stop", "change", "go back")):
            await _run(ctx, sender, cfg, Command(resume={"rejected": True}))
        elif any(w in low for w in ("link", "sheet", "not showing", "didn't appear")):
            await ctx.send(sender, cards.text_message(cards.pay_narration(p)))
        elif any(w in low for w in ("paid", "done", "finished")):
            await _run(ctx, sender, cfg, Command(resume={"transaction_id": p.get("link_session_id")}))
        else:
            await ctx.send(sender, cards.text_message(
                "Waiting for the payment. Say “send a link” if the sheet didn't appear, or “cancel” to go back."))
        return

    await _run(ctx, sender, cfg, Command(resume=reply))


@chat.on_message(ChatAcknowledgement)
async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass


# ---------------------------------------------------------------- payment protocol (seller)


@payments.on_message(CommitPayment)
async def on_commit(ctx: Context, sender: str, msg: CommitPayment):
    if ctx.storage.get(f"fulfilled:{msg.transaction_id}"):
        await ctx.send(sender, CompletePayment(transaction_id=msg.transaction_id))  # duplicate commit: already done
        return
    cfg = _config(ctx, _current_thread(ctx, sender))
    pending = await _pending(cfg)
    if not pending or pending.get("type") != "payment":
        await ctx.send(sender, CancelPayment(transaction_id=msg.transaction_id, reason="No open cart for this payment"))
        return
    # verify → fulfil → receipt run inside the graph; _emit sends CompletePayment on success.
    try:
        result = await (await get_graph()).ainvoke(Command(resume={"transaction_id": msg.transaction_id}), cfg, durability="sync")
    except Exception as exc:
        ctx.logger.error(f"post-payment failure: {exc}")
        await ctx.send(sender, cards.text_message(
            "Your payment went through but placing the asset failed. I'll retry when you say “try again”; "
            "you won't be charged twice."))
        return
    if not result.get("receipt"):
        await ctx.send(sender, CancelPayment(transaction_id=msg.transaction_id,
                                             reason="Stripe has not confirmed this payment"))
    await _emit(ctx, sender, result)


@payments.on_message(RejectPayment)
async def on_reject(ctx: Context, sender: str, msg: RejectPayment):
    cfg = _config(ctx, _current_thread(ctx, sender))
    if (await _pending(cfg) or {}).get("type") == "payment":
        await _run(ctx, sender, cfg, Command(resume={"rejected": True}))


concierge.include(chat, publish_manifest=True)
concierge.include(payments, publish_manifest=True)
