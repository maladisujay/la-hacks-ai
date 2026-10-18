"""The AI in Strata: three CREAO agents, called through CREAO's API trigger.

Each agent gets `request` + `context_json` and replies with one JSON object. The app never ranks, edits or
summarises on its own. `STRATA_OFFLINE_AGENTS=1` swaps in rough local stand-ins for UI work when CREAO isn't
set up; the UI labels them as stand-ins.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import datetime, timezone

import httpx

CREAO_API = "https://agent.creao.ai/api/v1"
ROLES = {"curate": "CURATOR", "teammate": "TEAMMATE", "catchup": "CATCHUP"}
POLL_SECONDS = 4
TIMEOUT_SECONDS = 8 * 60


def creds(kind: str) -> tuple[str | None, str | None]:
    """A dedicated agent per job if configured, else the one combined Strata agent (CREAO_STRATA_*)."""
    role = ROLES[kind]
    app_id, key = os.getenv(f"CREAO_{role}_APP_ID") or None, os.getenv(f"CREAO_{role}_KEY") or None
    if app_id and key:
        return app_id, key
    return os.getenv("CREAO_STRATA_APP_ID") or None, os.getenv("CREAO_STRATA_KEY") or None


def offline() -> bool:
    return os.getenv("STRATA_OFFLINE_AGENTS", "") in ("1", "true", "yes")


def mode(kind: str) -> str:
    if all(creds(kind)):
        return "creao"
    return "offline" if offline() else "missing"


def parse_json(text: str) -> dict:
    """Agents are told to reply with bare JSON; tolerate code fences or a sentence around it."""
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("the agent did not reply with JSON")
    return json.loads(text[start:end + 1])


def _unwrap(body: dict) -> dict:
    return body.get("data", body) if isinstance(body.get("data"), dict) else body


async def run_creao(kind: str, request: str, context: dict, on_started) -> tuple[dict, str]:
    """Start a run, wait for it, return (parsed reply, raw text)."""
    app_id, key = creds(kind)
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    base = f"{CREAO_API}/apps/{app_id}/runs"
    task = {"curate": "shortlist", "teammate": "edit", "catchup": "catchup"}[kind]
    inputs = {"request": request, "context_json": json.dumps({"task": task, **context}, ensure_ascii=False)}
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(base, headers=headers, json={"inputs": inputs})
        if r.status_code >= 400:
            raise RuntimeError(f"CREAO refused the run ({r.status_code}): {r.text[:200]}")
        run_id = _unwrap(r.json()).get("id")
        on_started(run_id)
        waited = 0
        while waited < TIMEOUT_SECONDS:
            await asyncio.sleep(POLL_SECONDS)
            waited += POLL_SECONDS
            s = await client.get(f"{base}/{run_id}", headers=headers)
            if s.status_code >= 400:
                continue
            body = _unwrap(s.json())
            status = body.get("status")
            if status == "completed":
                result = body.get("result") or {}
                text = result.get("text") or result.get("chatText") or ""
                return parse_json(text), text
            if status in ("failed", "cancelled", "error"):
                raise RuntimeError(f"CREAO run {status}: {body.get('errorCode') or body.get('error') or ''}")
    raise RuntimeError("CREAO run took too long")


# ---------- offline stand-ins (UI development only) ----------

def _weight(rule: dict) -> float:
    return (rule["kept"] + 1) / (rule["kept"] + rule["undone"] + 2)


def _applies(rule: dict, member: str) -> bool:
    return rule["scope"] == "team" or (rule["scope"] == "personal" and member in rule["members"])


def _satisfies(req: dict, asset: dict) -> bool | None:
    if not req:
        return None
    ok = True
    if "style" in req:
        ok &= asset["style"] == req["style"]
    if "max_colours" in req:
        ok &= asset["colours"] <= req["max_colours"]
    if "palette_includes" in req:
        ok &= req["palette_includes"] in asset["palette"]
    return ok


def offline_curate(request: str, ctx: dict) -> dict:
    member, lic, m = ctx["member"], ctx["licence"], ctx["mandate"]
    left = m["limit_cents"] - m["spent_cents"]
    rows = []
    for a in ctx["catalog"]:
        if a["kind"] != ctx["spot"]["kind"]:
            continue
        score, fits, breaks = 0.0, [], []
        for rule in ctx["rules"]:
            if not _applies(rule, member):
                continue
            ok = _satisfies(rule.get("requires") or {}, a)
            if ok is None:
                continue
            score += _weight(rule) if ok else -_weight(rule)
            (fits if ok else breaks).append(rule["text"])
        price = a["prices"][lic]
        if price > ctx["budget_cents"] or price > left or lic not in m["allowed_licences"]:
            score -= 1.5
            breaks.append("over your limit")
        rows.append((score, price, a, fits, breaks))
    rows.sort(key=lambda r: (-r[0], r[1]))
    out = []
    for i, (score, price, a, fits, breaks) in enumerate(rows[:4], 1):
        why = (f"Breaks “{breaks[0]}”." if breaks else
               f"{a['style'].capitalize()} and {a['colours']}-colour, the style Priya and Sam keep choosing.")
        out.append({"asset_id": a["id"], "rank": i, "score": round(score, 2), "why": why,
                    "fits": fits, "breaks": breaks})
    return {"summary": "Ranked by your team's taste: flat, two-colour, navy kept.", "shortlist": out}


def offline_teammate(request: str, ctx: dict) -> dict:
    el, q = ctx["element"], request.lower()
    props = el["props"]
    if any(w in q for w in ("warm", "charcoal", "colour", "color", "red", "blue", "green")) and "color" in props:
        if "color" in el["locked_props"]:
            return {"action": "conflict", "props": {}, "prop": "color", "wants": "warm charcoal #3A3632",
                    "reason": f"{el['locked_by']} locked this colour, so I'm asking instead of changing it.",
                    "summary": "", "rule_ids": ["r-navy"]}
        return {"action": "edit", "props": {"color": "#3A3632"}, "reason": "Warmer, still dark enough to read.",
                "summary": "Colour → warm charcoal", "rule_ids": []}
    if "font_size" in props and any(w in q for w in ("bigger", "premium", "bold", "heavier", "stronger")):
        new = {"font_size": props["font_size"] + 4, "font_weight": min(800, props.get("font_weight", 700) + 100)}
        return {"action": "edit", "props": new, "reason": "More contrast reads as more premium.",
                "summary": f"Size {props['font_size']} → {new['font_size']}", "rule_ids": ["r-heavy"]}
    if "font_size" in props and any(w in q for w in ("calm", "smaller", "quiet", "lighter")):
        new = {"font_size": max(28, props["font_size"] - 4)}
        return {"action": "edit", "props": new, "reason": "A little smaller lets the page breathe.",
                "summary": f"Size {props['font_size']} → {new['font_size']}", "rule_ids": []}
    if "text" in props and any(w in q for w in ("short", "copy", "rewrite", "text")):
        return {"action": "edit", "props": {"text": props["text"].split(".")[0] + "."},
                "reason": "Shorter copy keeps one idea per line.", "summary": "Shortened the copy", "rule_ids": []}
    return {"action": "decline", "props": {}, "reason": "I'm not sure what to change here; can you say more?",
            "summary": "", "rule_ids": []}


def offline_catchup(request: str, ctx: dict) -> dict:
    lines = []
    for e in ctx["events"][-5:][::-1]:
        who = f"Strata for {e['on_behalf_of']}" if e["actor"] == "ai" else e["who"]
        lines.append(f"{who}: {e['summary']} ({e['element']}).")
    q = ctx["open_conflicts"][0]["question"] if ctx["open_conflicts"] else ""
    return {"lines": lines or ["Nothing changed since you last looked."], "question": q}


OFFLINE = {"curate": offline_curate, "teammate": offline_teammate, "catchup": offline_catchup}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()
