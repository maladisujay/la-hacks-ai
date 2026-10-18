"""Drive the real agents end to end over uAgents messages, as a scripted ASI:One user.

    uv run uvicorn strata_agents.mock_strata:app --port 8090 &
    uv run python scripts/simulate_user.py
"""

from __future__ import annotations

import json
import os
import sys

from uagents import Agent, Bureau, Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    MetadataContent,
    chat_protocol_spec,
)
from uagents_core.contrib.protocols.payment import (
    CancelPayment,
    CommitPayment,
    CompletePayment,
    RequestPayment,
    payment_protocol_spec,
)

sys.path.insert(0, ".")
from strata_agents import cards  # noqa: E402
from strata_agents.run import AGENTS  # noqa: E402

user = Agent(name="sim-user", seed="strata sim user seed")
chat = Protocol(spec=chat_protocol_spec)
pay = Protocol(spec=payment_protocol_spec, role="buyer")
CONCIERGE = AGENTS["concierge"].address

# What the scripted user clicks on each card kind, as ASI:One would send it.
ANSWERS = {
    "custom": {"step": "pick_spot", "spot": "hero-art"},
    "form": {"step": "brief", "style": "Flat, two colours", "budget_usd": "40", "licence": "commercial",
             "also_mobile": "true"},
    "carousel": {"step": "choose", "asset": "seedling-jar"},
    "detail": {"step": "detail", "action": "add_to_cart", "licence": "commercial"},
    "review": {"step": "review", "action": "approve"},
}
log: list[str] = []


@user.on_event("startup")
async def start(ctx: Context):
    await ctx.send(CONCIERGE, cards.text_message("Find art for our landing page, under $40"))


@chat.on_message(ChatMessage)
async def on_msg(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, ChatAcknowledgement(acknowledged_msg_id=msg.msg_id))
    meta = next((c.metadata for c in msg.content if isinstance(c, MetadataContent)), None)
    print("\nCONCIERGE:", msg.text()[:200])
    if not meta:
        return
    kind = meta["card_kind"]
    payload = json.loads(meta["card_payload"])
    title = payload.get("title") or payload.get("root", {}).get("title")
    print(f"  [card: {kind}] {title}")
    log.append(kind)
    if kind == "custom" and "Placed" in str(title):
        print("\nRECEIPT:", json.dumps(payload, indent=1)[:1500])
        print("\nFLOW OK:", " → ".join(log), flush=True)
        os._exit(0)  # the Bureau doesn't stop cleanly on SystemExit
    await ctx.send(sender, cards.text_message(json.dumps(ANSWERS[kind])))


@chat.on_message(ChatAcknowledgement)
async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    pass


@pay.on_message(RequestPayment)
async def on_request(ctx: Context, sender: str, msg: RequestPayment):
    print(f"\nPAYMENT REQUEST: {msg.accepted_funds[0].amount} {msg.accepted_funds[0].currency} ref={msg.reference}")
    sid = msg.metadata["stripe"]["checkout_session_id"]
    await ctx.send(sender, CommitPayment(funds=msg.accepted_funds[0], recipient=msg.recipient, transaction_id=sid,
                                         reference=msg.reference))


@pay.on_message(CompletePayment)
async def on_complete(ctx: Context, sender: str, msg: CompletePayment):
    print("PAYMENT COMPLETE:", msg.transaction_id)


@pay.on_message(CancelPayment)
async def on_cancel(ctx: Context, sender: str, msg: CancelPayment):
    print("PAYMENT CANCELLED:", msg.reason)


user.include(chat)
user.include(pay)

if __name__ == "__main__":
    bureau = Bureau(port=8011)
    for a in list(AGENTS.values()) + [user]:
        bureau.add(a)
    bureau.run()
