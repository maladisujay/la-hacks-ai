"""ASI:One Interactive Card builders (the seven cards in the Paper storyboard) and reply parsing.

A card is a ChatMessage carrying narration text plus one MetadataContent. Every value in the
metadata must be a string, the payload is json-encoded, and selection ids are distinctive
tokens so the reply can be matched whether ASI:One sends JSON or the planner's prose.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from uuid import uuid4

from uagents_core.contrib.protocols.chat import ChatMessage, MetadataContent, TextContent

from . import seed


def _usd(cents: int) -> str:
    return f"${cents / 100:.2f}"


def card(narration: str, kind: str, payload: dict, width: int = 520) -> dict:
    return {"narration": narration, "kind": kind, "payload": payload, "width": width}


def to_message(c: dict) -> ChatMessage:
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[
            TextContent(type="text", text=c["narration"]),
            MetadataContent(type="metadata", metadata={
                "card_protocol_version": "1",
                "requires_card_interaction": "true",
                "card_kind": c["kind"],
                "card_payload": json.dumps(c["payload"]),
                "preferred_drawer_width_px": str(c.get("width", 520)),
            }),
        ],
    )


def text_message(text: str) -> ChatMessage:
    return ChatMessage(timestamp=datetime.now(timezone.utc), msg_id=uuid4(),
                       content=[TextContent(type="text", text=text)])


# ---------------------------------------------------------------- 1 · pick the spot


def element_picker(file: dict, spots: list[dict], frame_url: str | None, tiles: dict, preselect: str | None,
                   note: str = "") -> dict:
    issues = sum(1 for s in spots if s["status"] == "licence-issue")
    narration = (
        f"I opened **{file['name']}**. {len(spots)} spot{'s' if len(spots) != 1 else ''} could use an asset"
        + (f", and {issues} has a licence problem" if issues else "")
        + ". Which one?"
    )
    if note:
        narration = f"{note}\n\n{narration}"
    children: list[dict] = []
    if frame_url:
        children.append({"type": "image", "src": frame_url, "alt": f"{file['name']}, rendered just now",
                         "aspect_ratio": "16:9"})
    choices = []
    for s in spots:
        choice = {"value": s["id"], "label": f"{s['label']} · {s['note']}"}
        if tiles.get(s["id"]):
            choice["image"] = tiles[s["id"]]
        choices.append(choice)
    children.append({"type": "choice_grid", "name": "spot", "choices": choices})
    children.append({"type": "button", "label": "Shop this spot", "primary": True,
                     "action": {"selection": {"step": "pick_spot"}}})
    payload = {"root": {"type": "section", "title": file["name"],
                        "subtitle": f"{len(spots)} open spots · rendered from your file just now",
                        "children": children}}
    return card(narration, "custom", payload, width=560)


# ---------------------------------------------------------------- 2 · brief


def brief_form(spot: dict, d: dict) -> dict:
    narration = (f"{spot['label']} it is. I filled in your team's rules so you don't have to repeat them: "
                 f"{d['style'].lower()}, navy kept.")
    fields = [
        {"name": "style", "kind": "select", "label": "Style (team rule · Priya and Sam)", "required": True,
         "options": [d["style"], "Line art", "Anything"]},
        {"name": "budget_usd", "kind": "number", "label": "Budget in USD", "required": True},
        {"name": "licence", "kind": "select", "label": "Licence", "required": True,
         "options": ["commercial", "personal", "extended"]},
    ]
    if spot["id"] == "hero-art":
        fields.append({"name": "also_mobile", "kind": "checkbox", "label": "Also place it on the mobile hero"})
    payload = {"title": f"Brief for the {spot['label'].lower()}", "fields": fields,
               "submit_cta": {"label": "Find 4 options", "selection": {"step": "brief"}}}
    return card(narration, "form", payload)


# ---------------------------------------------------------------- 3 · compare


def carousel(spot: dict, candidates: list[dict], brief: dict, note: str = "") -> dict:
    fitting = sum(1 for c in candidates if not c["breaks"])
    narration = (f"Each picture is your {spot['label'].lower()} with that piece already in place. "
                 f"{fitting} of {len(candidates)} fit every team rule.")
    if note:
        narration = f"{note} {narration}"
    items = []
    for c in candidates:
        badges = [{"label": "Fits team rules", "variant": "success"}] if not c["breaks"] else \
            [{"label": f"Breaks: {c['breaks'][0]}", "variant": "warning"}]
        item = {
            "id": c["asset_id"],
            "title": c["title"],
            "subtitle": c["creator"],
            "secondary_text": f"{_usd(c['price_cents'])} {brief['licence']} · {c['why']}",
            "badges": badges,
            "primary_cta": {"label": "Look closer", "selection": {"step": "choose", "asset": c["asset_id"]}},
        }
        if c.get("image"):
            item["image"] = c["image"]
        items.append(item)
    payload = {"title": f"{len(candidates)} options, tried on your {spot['label'].lower()}",
               "subtitle": "Watermarked previews · nothing is bought yet", "items": items}
    return card(narration, "carousel", payload, width=640)


# ---------------------------------------------------------------- 4 · detail


def detail(asset: dict, cand: dict, licence: str, note: str = "") -> dict:
    narration = f"{asset['title']}, full size on your design. Commercial is the licence client work needs."
    if note:
        narration = f"{note}\n\n{narration}"
    rows = [
        {"label": "Creator", "value": asset["creator"]},
        {"label": "Style", "value": f"{asset['style'].title()} · {' and '.join(asset['palette'])}"},
        {"label": "Team rules", "value": "Fits all" if not cand["breaks"] else f"Breaks {', '.join(cand['breaks'])}"},
        {"label": "Why", "value": cand["why"]},
        {"label": "Files", "value": asset["files"]},
    ]
    choices = [{"value": lic, "label": seed.LICENCE_LABELS[lic], "secondary_text": _usd(price)}
               for lic, price in asset["prices"].items()]
    payload = {
        "title": asset["title"],
        "summary_rows": rows,
        "sub_options": [{"name": "licence", "kind": "radio", "label": "Licence", "choices": choices}],
        "ctas": [
            {"label": "Add to cart", "primary": True, "selection": {"step": "detail", "action": "add_to_cart"}},
            {"label": "See others", "selection": {"step": "detail", "action": "see_others"}},
        ],
    }
    if cand.get("image"):
        payload["hero_image"] = cand["image"]
    return card(narration, "detail", payload, width=600)


# ---------------------------------------------------------------- 5 · review


def review(chosen: dict, quote: dict, placements: list[str], note: str = "") -> dict:
    cand = chosen["candidate"]
    narration = ("Nothing is charged until you approve. This fits the spending limit Priya set for you. "
                 "After you approve, ASI:One opens its own payment sheet; if it doesn't appear, say “send a link”.")
    if note:
        narration = f"{note}\n\n{narration}"
    rows = [
        {"label": "Item", "value": f"{cand['title']} · {cand['creator']}"},
        {"label": "Licence", "value": chosen["licence"].title()},
        {"label": "Placed on", "value": ", ".join(placements)},
        {"label": "Spending limit", "value": f"{_usd(quote['limit_cents'])} a month · "
                                              f"{_usd(quote['remaining_after_cents'])} left after"},
        {"label": "Paid with", "value": "Card via Stripe (test mode)"},
        {"label": "Total", "value": _usd(quote["amount_cents"])},
    ]
    payload = {
        "title": "Review before paying",
        "summary_rows": rows,
        "approve_cta": {"label": "Approve and pay", "primary": True, "selection": {"step": "review", "action": "approve"}},
        "reject_cta": {"label": "Change", "selection": {"step": "review", "action": "change"}},
    }
    return card(narration, "review", payload)


# ---------------------------------------------------------------- 6 · pay


def pay_narration(payment: dict) -> str:
    """Sent only when the user asks for a link: a RequestPayment must travel alone or the sheet is hidden."""
    if payment.get("checkout_url"):
        return (f"Here is a secure Stripe page for {_usd(payment['amount_cents'])} (test mode): "
                f"{payment['checkout_url']}\n\nSay “paid” when you're done and I'll check with Stripe.")
    return "The payment sheet is the only way to pay for this one. Say “cancel” to go back to the review."


# ---------------------------------------------------------------- 7 · receipt


def receipt(state: dict) -> dict:
    r, c, p = state["receipt"], state["chosen"], state["payment"]
    names = {"hero-art": "desktop hero", "mobile-hero": "mobile hero", "feature-icons": "feature icons"}
    placed = " and ".join(names.get(s, s) for s in r["spot_ids"])
    narration = f"Done. It's on the {placed}, and Priya and Sam will see it in their catch-up."
    trail = [
        ("Within your spending limit", "intent"),
        ("Approved by you", "cart"),
        ("Stripe confirmed payment" if not str(p.get("verified_id", "")).startswith("cs_sim_")
         else "Payment simulated (no Stripe key)", "payment"),
        (f"Licence {r['licence_id']} on {len(r['spot_ids'])} element{'s' if len(r['spot_ids']) > 1 else ''}", "receipt"),
    ]
    children: list[dict] = []
    if r.get("final_image_url"):
        children.append({"type": "image", "src": r["final_image_url"], "alt": "Your file with the asset placed",
                         "aspect_ratio": "16:9"})
    children.append({"type": "group", "direction": "row", "gap": 8, "children": [
        {"type": "badge", "label": f"Paid · {_usd(p['amount_cents'])}", "variant": "success"},
        {"type": "badge", "label": c["licence"].title(), "variant": "info"},
    ]})
    children.append({"type": "list", "items": [
        {"children": [{"type": "text", "value": f"✓ {label}"}, {"type": "text", "value": tag, "style": "muted"}]}
        for label, tag in trail
    ]})
    nxt = r.get("next_spot")
    if nxt:
        children.append({"type": "text", "value": f"Next: the {nxt['label'].lower()} are on a personal licence.",
                         "style": "emphasis"})
        children.append({"type": "group", "direction": "row", "gap": 8, "children": [
            {"type": "button", "label": f"Fix the {nxt['label'].lower()}", "primary": True,
             "action": {"selection": {"step": "next", "spot": nxt["id"]}}},
            {"type": "button", "label": "Done for now", "action": {"selection": {"step": "next", "spot": "none"}}},
        ]})
    payload = {"root": {"type": "section", "title": "Placed, licensed, logged",
                        "subtitle": f"{c['candidate']['title']} · {_usd(r['remaining_after_cents'])} left this month",
                        "children": children}}
    return card(narration, "custom", payload, width=560)


# ---------------------------------------------------------------- reply parsing


def clean_text(text: str) -> str:
    """Drop a leading @mention and any markdown images ASI:One adds around the user's words."""
    text = re.sub(r"^@\S+\s+", "", (text or "")).strip()
    return re.sub(r"\n*!\[[^\]]*\]\(https?://[^)]+\)", "", text).strip()


def _flatten(value: dict) -> dict:
    # ASI:One may send the selection flat or nested under "selection".
    nested = value.get("selection")
    if isinstance(nested, dict):
        value = {**{k: v for k, v in value.items() if k != "selection"}, **nested}
    return {str(k): v for k, v in value.items()}


def parse_reply(text: str) -> dict:
    """Card replies arrive as JSON (direct @mention) or as prose that contains the ids (planner)."""
    text = clean_text(text)
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return _flatten(value)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        try:
            value = json.loads(text[start:end + 1])
            if isinstance(value, dict):
                return {**_flatten(value), "text": text}
        except json.JSONDecodeError:
            pass
    return {"text": text}


def match_choice(reply, options: list[str], key: str) -> str | None:
    if isinstance(reply, dict):
        v = reply.get(key)
        if isinstance(v, str) and v in options:
            return v
        text = str(reply.get("text", "")) + " " + json.dumps({k: v for k, v in reply.items() if k != "text"})
    else:
        text = str(reply or "")
    low = text.lower()
    for opt in sorted(options, key=len, reverse=True):
        if opt.lower() in low or opt.replace("-", " ").lower() in low or opt.replace("_", " ").lower() in low:
            return opt
    return None


def form_values(reply) -> dict:
    if isinstance(reply, dict):
        return {k: v for k, v in reply.items() if k != "text"}
    return {}
