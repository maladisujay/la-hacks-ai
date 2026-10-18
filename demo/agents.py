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


TASK = {"curate": "shortlist", "teammate": "edit", "catchup": "catchup"}
SHAPE = {
    "curate": '{"summary": "<one sentence, max 25 words>", "shortlist": [{"asset_id": "...", "rank": 1, "score": 1.2, "why": "...", '
              '"fits": ["rule text"], "breaks": ["rule text"]}]}',
    "teammate": '{"action": "edit|conflict|decline", "props": {"prop": "new value"}, "reason": "<one sentence, max 25 words>", '
                '"summary": "<what changed, max 10 words>", "prop": "locked prop if conflict", "wants": "wanted value if conflict", '
                '"rule_ids": ["..."], "middle_ground": {"element_key": "<an element from other_elements or this one>", '
                '"props": {"prop": "new value, never a locked prop"}, "summary": "<what it changes, max 12 words>", '
                '"why": "<one sentence: how it gives the asker what they wanted while keeping the locked decision>"}}',
    "catchup": '{"lines": ["<max 5 lines, max 16 words each>"], "question": "<one short question or empty>"}',
}
NEEDS = {"curate": "shortlist", "teammate": "action", "catchup": "lines"}


def contract(kind: str, request: str) -> str:
    """Appended to every request: the app reads this exact JSON, whatever the agent's report style."""
    extra = (" If the change would touch a locked prop, reply action conflict AND propose a middle_ground: the smallest "
             "change to an unlocked prop (on this element or one in other_elements) that gives the asker what they "
             "wanted without overriding the lock; use the team's rules and history. Omit middle_ground otherwise."
             if kind == "teammate" else "") + (" Only score a rule against an asset if the rule's applies_to list includes spot.kind (rules with an "
             "empty applies_to apply to everything)." if kind == "curate" else "")
    return (f"{request}{extra}\n\nOUTPUT CONTRACT (the Strata app parses this): end your reply with exactly one JSON "
            f"object in this shape, every field filled, inside a ```json block, and also save it as result.json: "
            f"{SHAPE[kind]}").strip()


def _candidates(text: str) -> list[dict]:
    out = []
    for m in re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text or "", re.S):
        try:
            out.append(json.loads(m.group(1)))
        except json.JSONDecodeError:
            pass
    try:
        out.append(parse_json(text))
    except (ValueError, json.JSONDecodeError):
        pass
    return out


def _from_markdown(kind: str, md: str, context: dict) -> dict | None:
    """Fallback for agents that write a markdown report instead of JSON."""
    if kind == "curate":
        rule_text = {r["id"]: r["text"] for r in context.get("rules", [])}
        items = []
        blocks = re.split(r"\n(?=#{2,4}\s*\d+\.)", md)
        for b in blocks:
            head = re.match(r"#{2,4}\s*(\d+)\.\s*`?([\w-]+)`?.*?score\s*(-?[\d.]+)", b)
            if not head:
                continue
            lines = [l.strip() for l in b.splitlines()[1:] if l.strip() and not l.strip().startswith("-")]
            ids = lambda label: re.findall(r"`([\w-]+)`", (re.search(rf"\*\*{label}[^*]*\*\*(.*)", b) or [None, ""])[1])
            items.append({"asset_id": head.group(2), "rank": int(head.group(1)), "score": float(head.group(3)),
                          "why": lines[0] if lines else "", "fits": [rule_text.get(i, i) for i in ids("Fit")],
                          "breaks": [rule_text.get(i, i) for i in ids("Broken")]})
        return {"summary": "", "shortlist": items} if items else None
    if kind == "catchup":
        lines = [re.sub(r"^[-*\d.\s]+", "", l).strip() for l in md.splitlines() if re.match(r"\s*([-*]|\d+\.)\s", l)]
        return {"lines": [l for l in lines if l][:5], "question": ""} if lines else None
    return None


def _first_sentences(text: str, n: int = 2) -> str:
    plain = re.sub(r"[*`#_]", "", text or "").strip()
    return " ".join(re.split(r"(?<=[.!?])\s+", plain)[:n])


def extract(kind: str, request: str, context: dict, texts: list[str]) -> dict:
    """Pick the agent's answer from its reply, chat text or saved files; fill gaps the app can infer."""
    found = [c for t in texts for c in _candidates(t) if NEEDS[kind] in c]
    # prefer the most complete object
    reply = max(found, key=lambda c: len(json.dumps(c)), default=None)
    if kind == "curate" and (not reply or not reply.get("shortlist")):
        md = next((r for t in texts if (r := _from_markdown(kind, t, context))), None)
        if md:
            md["summary"] = next((c["summary"] for t in texts for c in _candidates(t) if c.get("summary")), "")
            reply = md
    if kind == "catchup" and not reply:
        reply = next((r for t in texts if (r := _from_markdown(kind, t, context))), None)
    if not reply:
        raise ValueError("the agent's reply had no usable result")
    chat = texts[1] if len(texts) > 1 else ""
    if kind == "curate" and not reply.get("summary"):
        reply["summary"] = _first_sentences(chat, 2) or "Ranked by your team's learned taste."
    if kind == "teammate":
        el = context.get("element", {})
        reply.setdefault("reason", reply.get("summary") or _first_sentences(chat, 1))
        if not reply.get("reason"):
            reply["reason"] = _first_sentences(chat, 1)
        if reply.get("action") == "conflict":
            reply.setdefault("prop", "")
            if not reply["prop"]:
                reply["prop"] = next((p for p in el.get("locked_props", []) if p in json.dumps(reply) + chat),
                                     (el.get("locked_props") or [""])[0])
            if not reply.get("wants"):
                reply["wants"] = request
    return reply


async def run_creao(kind: str, request: str, context: dict, on_started) -> tuple[dict, str]:
    """Start a run, wait for it, return (parsed reply, raw text)."""
    app_id, key = creds(kind)
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    base = f"{CREAO_API}/apps/{app_id}/runs"
    inputs = {"request": contract(kind, request),
              "context_json": json.dumps({"task": TASK[kind], **context}, ensure_ascii=False)}
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
                texts = [result.get("text") or "", result.get("chatText") or ""]
                for art in sorted(result.get("artifacts") or [], key=lambda a: "json" not in str(a.get("type"))):
                    if art.get("url"):
                        f = await client.get(art["url"], headers=headers, follow_redirects=True)
                        if f.status_code < 400 and len(f.text) < 200_000:
                            texts.append(f.text)
                return extract(kind, request, context, texts), "\n\n---\n\n".join(texts)
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
            if not _applies(rule, member) or (rule.get("applies_to") and a["kind"] not in rule["applies_to"]):
                continue
            ok = _satisfies(rule.get("requires") or {}, a)
            if ok is None:
                continue
            score += _weight(rule) if ok else -_weight(rule)
            (fits if ok else breaks).append(rule["text"])
        price = a["prices"][lic]
        if price > ctx["budget_cents"] or price > left or lic not in m["allowed_licences"]:
            score -= 1.5
            breaks.append("Over your limit")
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
                    "summary": "", "rule_ids": ["r-navy"],
                    "middle_ground": {"element_key": "hero_subcopy", "props": {"color": "#6B4E3D"},
                                      "summary": "Subcopy to warm brown; heading stays navy",
                                      "why": "Warmth comes from the supporting text, so Priya's navy heading stays."}}
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
