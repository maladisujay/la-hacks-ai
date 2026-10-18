"""LangGraph orchestration for the Concierge.

Each card is an `interrupt()`: the graph pauses, the Concierge sends the card to ASI:One,
and the user's click resumes the graph with `Command(resume=...)`. Calls to the other four
agents go through a `Bus` passed in the run config, so the same graph runs over uAgents
messages in production and over direct function calls in tests.
"""

from __future__ import annotations

import re
import uuid
from typing import Any, Protocol, TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, RetryPolicy, interrupt

from . import cards, seed
from .config import settings
from .llm import ask_json
from .messages import (
    CheckoutRequest,
    CheckoutResponse,
    CurateRequest,
    CurateResponse,
    FulfilRequest,
    FulfilResponse,
    QuoteRequest,
    QuoteResponse,
    RenderRequest,
    RenderResponse,
    VerifyPaymentResponse,
)


class Bus(Protocol):
    async def spots(self, file_id: str) -> RenderResponse: ...
    async def curate(self, req: CurateRequest) -> CurateResponse: ...
    async def render(self, req: RenderRequest) -> RenderResponse: ...
    async def quote(self, req: QuoteRequest) -> QuoteResponse: ...
    async def checkout(self, req: CheckoutRequest) -> CheckoutResponse: ...
    async def verify(self, checkout_session_id: str) -> VerifyPaymentResponse: ...
    async def fulfil(self, req: FulfilRequest) -> FulfilResponse: ...
    async def get_file(self, file_id: str) -> dict: ...


class ShopState(TypedDict, total=False):
    member_id: str
    file_id: str
    team_id: str
    user_text: str
    intent: dict
    file: dict
    frame_url: str
    spot_tiles: dict
    spot: dict
    brief: dict
    candidates: list[dict]
    chosen: dict
    quote: dict
    payment: dict
    receipt: dict
    note: str  # one-line message carried into the next card (recoveries, refusals)
    done: bool


def _bus(config) -> Bus:
    return config["configurable"]["bus"]


def _ask(card: dict) -> Any:
    """Pause on a card and return what the user chose."""
    return interrupt({"type": "card", **card})


# ---------------------------------------------------------------- nodes


async def understand(state: ShopState) -> dict:
    text = state.get("user_text", "")
    parsed = await ask_json(
        "Extract a shopping intent for design assets. Reply with JSON only: "
        '{"spot_hint": "hero-art|feature-icons|mobile-hero|null", "budget_usd": number|null, '
        '"licence": "personal|commercial|extended|null"}',
        text,
    ) or {}
    budget = parsed.get("budget_usd")
    if budget is None:
        m = re.search(r"\$\s*(\d+(?:\.\d+)?)", text) or re.search(r"(\d+)\s*(?:dollars|usd)", text, re.I)
        budget = float(m.group(1)) if m else None
    spot = parsed.get("spot_hint")
    if spot in (None, "null"):
        low = text.lower()
        spot = "feature-icons" if "icon" in low else "mobile-hero" if "mobile" in low else None
    licence = parsed.get("licence") if parsed.get("licence") in seed.LICENCE_LABELS else None
    return {"intent": {"spot_hint": spot, "budget_cents": int(budget * 100) if budget else None, "licence": licence}}


async def load_file(state: ShopState, config) -> dict:
    bus = _bus(config)
    f = await bus.get_file(state["file_id"])
    pics = await bus.spots(state["file_id"])
    return {
        "file": f,
        "team_id": f["team_id"],
        "frame_url": pics.frame_url if pics.ok else None,
        "spot_tiles": pics.spot_tiles if pics.ok else {},
        "note": "" if pics.ok else "I couldn't draw your file just now, so the tiles are text only.",
    }


async def pick_spot(state: ShopState) -> dict:
    spots = [s for s in state["file"]["spots"] if s["status"] != "licensed"]
    if not spots:
        return {"done": True, "note": "Every spot in this file is already licensed."}
    reply = _ask(cards.element_picker(state["file"], spots, state.get("frame_url"), state.get("spot_tiles", {}),
                                      preselect=state["intent"].get("spot_hint"), note=state.get("note", "")))
    chosen = cards.match_choice(reply, [s["id"] for s in spots], key="spot") or spots[0]["id"]
    return {"spot": next(s for s in spots if s["id"] == chosen), "note": ""}


async def brief(state: ShopState) -> dict:
    spot = state["spot"]
    kind = "icon-set" if spot["kind"] == "icon-set" else "illustration"
    defaults = {
        "style": "Flat, two colours" if kind == "illustration" else "Flat icons",
        "budget_usd": (state["intent"].get("budget_cents") or 4000) // 100,
        "licence": state["intent"].get("licence") or "commercial",
        "also_mobile": spot["id"] == "hero-art",
    }
    reply = _ask(cards.brief_form(spot, defaults))
    values = cards.form_values(reply)
    budget = values.get("budget_usd") or defaults["budget_usd"]
    try:
        budget_cents = int(float(str(budget).strip("$ ")) * 100)
    except ValueError:
        budget_cents = defaults["budget_usd"] * 100
    licence = values.get("licence") if values.get("licence") in seed.LICENCE_LABELS else defaults["licence"]
    also_mobile = str(values.get("also_mobile", defaults["also_mobile"])).lower() in ("true", "1", "yes", "on")
    return {"brief": {"kind": kind, "budget_cents": budget_cents, "licence": licence, "also_mobile": also_mobile}}


async def curate(state: ShopState, config) -> dict:
    b = state["brief"]
    res = await _bus(config).curate(CurateRequest(
        file_id=state["file_id"], team_id=state["team_id"], member_id=state["member_id"],
        kind=b["kind"], budget_cents=b["budget_cents"], licence=b["licence"],
    ))
    if not res.ok or not res.assets:
        raise RuntimeError(res.error or "no assets")  # RetryPolicy retries, then the edge recovers
    return {"candidates": [a.model_dump() for a in res.assets]}


async def render_options(state: ShopState, config) -> dict:
    ids = [c["asset_id"] for c in state["candidates"]]
    res = await _bus(config).render(RenderRequest(file_id=state["file_id"], spot_id=state["spot"]["id"], asset_ids=ids))
    urls = {i.asset_id: i.url for i in res.images} if res.ok else {}
    out = [{**c, "image": urls.get(c["asset_id"])} for c in state["candidates"]]
    note = "" if res.ok else "Previews are slow right now, so these show the catalog art instead."
    return {"candidates": out, "note": note}


async def choose(state: ShopState) -> dict:
    reply = _ask(cards.carousel(state["spot"], state["candidates"], state["brief"], note=state.get("note", "")))
    asset_id = cards.match_choice(reply, [c["asset_id"] for c in state["candidates"]], key="asset")
    if not asset_id:
        asset_id = state["candidates"][0]["asset_id"]
    cand = next(c for c in state["candidates"] if c["asset_id"] == asset_id)
    return {"chosen": {"asset_id": asset_id, "candidate": cand, "licence": state["brief"]["licence"]}, "note": ""}


async def detail(state: ShopState) -> dict:
    cand = state["chosen"]["candidate"]
    asset = next(a for a in seed.CATALOG if a["id"] == cand["asset_id"])
    reply = _ask(cards.detail(asset, cand, state["chosen"]["licence"], note=state.get("note", "")))
    if cards.match_choice(reply, ["see_others"], key="action") == "see_others":
        return {"chosen": {}, "note": ""}
    licence = cards.match_choice(reply, list(seed.LICENCE_LABELS), key="licence") or state["chosen"]["licence"]
    return {"chosen": {**state["chosen"], "licence": licence}, "note": ""}


async def check_quote(state: ShopState, config) -> dict:
    q = await _bus(config).quote(QuoteRequest(
        member_id=state["member_id"], asset_id=state["chosen"]["asset_id"], licence=state["chosen"]["licence"]
    ))
    if not q.ok:
        raise RuntimeError(q.reason or "quote failed")
    note = ""
    if not q.within_mandate:
        note = q.reason or "That's over your spending limit."
        if q.cheaper_licence:
            note += f" The {q.cheaper_licence} licence (${q.cheaper_amount_cents / 100:.2f}) fits."
    return {"quote": q.model_dump(), "note": note}


async def review(state: ShopState) -> dict:
    spots = [state["spot"]["label"]] + (["Mobile hero"] if state["brief"].get("also_mobile") else [])
    reply = _ask(cards.review(state["chosen"], state["quote"], spots, note=state.get("note", "")))
    if cards.match_choice(reply, ["approve", "change"], key="action") == "change":
        return {"chosen": {**state["chosen"], "approved": False}, "note": ""}
    return {"chosen": {**state["chosen"], "approved": True}, "note": ""}


async def create_checkout(state: ShopState, config) -> dict:
    # Side effect lives in its own node: an interrupted node re-runs from the top on resume,
    # and we must never open a second Stripe session for the same cart.
    c, q = state["chosen"], state["quote"]
    reference = f"STR-{uuid.uuid4().hex[:6].upper()}"
    title = c["candidate"]["title"]
    res = await _bus(config).checkout(CheckoutRequest(
        member_id=state["member_id"], asset_id=c["asset_id"], licence=c["licence"],
        amount_cents=q["amount_cents"], reference=reference,
        description=f"{title}, {c['licence']} licence",
    ))
    if not res.ok:
        raise RuntimeError(res.error or "checkout failed")
    return {"payment": {**res.model_dump(), "reference": reference, "amount_cents": q["amount_cents"], "title": title}}


async def await_payment(state: ShopState) -> dict:
    payment = state["payment"]
    # The Concierge turns this into a native RequestPayment (Payment Protocol).
    committed = interrupt({"type": "payment", "payment": payment, "narration": cards.pay_narration(payment)})
    committed = committed if isinstance(committed, dict) else {}
    if committed.get("rejected"):
        return {"payment": {**payment, "rejected": True}}
    return {"payment": {**payment, "transaction_id": committed.get("transaction_id")}}


async def verify(state: ShopState, config) -> dict:
    p = state["payment"]
    # Trust the session we opened first; ASI:One's transaction_id is only a fallback.
    ids = [i for i in (p.get("checkout_session_id"), p.get("link_session_id"), p.get("transaction_id")) if i]
    for sid in dict.fromkeys(ids):
        v = await _bus(config).verify(sid)
        if v.paid:
            return {"payment": {**p, "paid": True, "verified_id": sid}, "note": ""}
    return {"payment": {**p, "paid": False}, "note": "Stripe hasn't confirmed the payment, so nothing was charged."}


async def fulfil(state: ShopState, config) -> dict:
    c, p = state["chosen"], state["payment"]
    spot_ids = [state["spot"]["id"]] + (["mobile-hero"] if state["brief"].get("also_mobile") else [])
    res = await _bus(config).fulfil(FulfilRequest(
        file_id=state["file_id"], member_id=state["member_id"], asset_id=c["asset_id"], licence=c["licence"],
        spot_ids=spot_ids, amount_cents=p["amount_cents"], payment_ref=p["verified_id"],
    ))
    if not res.ok:
        raise RuntimeError(res.error or "fulfil failed")
    f = await _bus(config).get_file(state["file_id"])
    nxt = next((s for s in f["spots"] if s["status"] == "licence-issue"), None)
    return {"receipt": {**res.model_dump(), "spot_ids": spot_ids, "next_spot": nxt,
                        "remaining_after_cents": state["quote"]["remaining_after_cents"]}}


async def receipt(state: ShopState) -> dict:
    return {"done": True}


# ---------------------------------------------------------------- routing


def after_pick(state: ShopState) -> str:
    return END if state.get("done") else "brief"


def after_detail(state: ShopState) -> str:
    return "choose" if not state.get("chosen") else "check_quote"


def after_quote(state: ShopState) -> str:
    return "review" if state["quote"]["within_mandate"] else "detail"


def after_review(state: ShopState) -> str:
    return "create_checkout" if state["chosen"].get("approved") else "detail"


def after_payment(state: ShopState) -> str:
    return "review" if state["payment"].get("rejected") else "verify"


def after_verify(state: ShopState) -> str:
    return "fulfil" if state["payment"].get("paid") else "review"


RETRY = RetryPolicy(max_attempts=3, initial_interval=0.5, backoff_factor=2.0)


def build_graph(checkpointer=None):
    g = StateGraph(ShopState)
    g.add_node("understand", understand)
    g.add_node("load_file", load_file, retry_policy=RETRY)
    g.add_node("pick_spot", pick_spot)
    g.add_node("brief", brief)
    g.add_node("curate", curate, retry_policy=RETRY)
    g.add_node("render_options", render_options, retry_policy=RETRY)
    g.add_node("choose", choose)
    g.add_node("detail", detail)
    g.add_node("check_quote", check_quote, retry_policy=RETRY)
    g.add_node("review", review)
    g.add_node("create_checkout", create_checkout, retry_policy=RETRY)
    g.add_node("await_payment", await_payment)
    g.add_node("verify", verify, retry_policy=RETRY)
    g.add_node("fulfil", fulfil, retry_policy=RETRY)
    g.add_node("receipt", receipt)

    g.add_edge(START, "understand")
    g.add_edge("understand", "load_file")
    g.add_edge("load_file", "pick_spot")
    g.add_conditional_edges("pick_spot", after_pick, ["brief", END])
    g.add_edge("brief", "curate")
    g.add_edge("curate", "render_options")
    g.add_edge("render_options", "choose")
    g.add_edge("choose", "detail")
    g.add_conditional_edges("detail", after_detail, ["choose", "check_quote"])
    g.add_conditional_edges("check_quote", after_quote, ["review", "detail"])
    g.add_conditional_edges("review", after_review, ["create_checkout", "detail"])
    g.add_edge("create_checkout", "await_payment")
    g.add_conditional_edges("await_payment", after_payment, ["verify", "review"])
    g.add_conditional_edges("verify", after_verify, ["fulfil", "review"])
    g.add_edge("fulfil", "receipt")
    g.add_edge("receipt", END)
    return g.compile(checkpointer=checkpointer or InMemorySaver())


def initial_state(user_text: str, member_id: str | None = None, file_id: str | None = None) -> ShopState:
    return {
        "user_text": user_text,
        "member_id": member_id or settings.demo_member_id,
        "file_id": file_id or settings.demo_file_id,
        "note": "",
    }


__all__ = ["build_graph", "initial_state", "Command", "ShopState", "Bus"]
