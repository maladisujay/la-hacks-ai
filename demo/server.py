"""Strata local demo: the workspace, shop and checkout run here; every AI step runs on a CREAO agent.

    uv run python demo/server.py        → http://localhost:8044
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import string
import sys
import uuid
from datetime import date
from pathlib import Path

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
load_dotenv(REPO / ".env")

import agents  # noqa: E402
from seed_data import EDITABLE, payment_method, seed  # noqa: E402

PORT = int(os.getenv("STRATA_DEMO_PORT", "8044"))
STATE_FILE = Path(os.getenv("STRATA_STATE_FILE", HERE / "state.json"))
LICENCE_LABELS = {"personal": "Personal · not for client work", "commercial": "Commercial · site and app",
                  "extended": "Extended · print and merchandise"}
TIER_RANK = {"personal": 0, "commercial": 1, "extended": 2}
SPOT_KIND = {"illustration_slot": "illustration", "icon_row": "icon_set", "pattern_slot": "pattern"}

app = FastAPI(title="Strata demo")
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")
app.mount("/assets", StaticFiles(directory=REPO / "design" / "assets"), name="assets")


def load() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return seed()


S = load()
if "cards" not in S.get("payment_method", {}):
    S["payment_method"] = payment_method()


def save() -> None:
    STATE_FILE.write_text(json.dumps(S, ensure_ascii=False, indent=1))


def uid(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def member_ok(name: str) -> str:
    if name not in S["members"]:
        raise HTTPException(400, "unknown member")
    return name


def element(key: str) -> dict:
    el = S["elements"].get(key)
    if not el:
        raise HTTPException(404, "no such element")
    return el


def asset(asset_id: str) -> dict:
    for a in S["catalog"]:
        if a["id"] == asset_id:
            return a
    raise HTTPException(404, "no such asset")


def atom(**kw) -> dict:
    a = {"id": uid("h"), "at": agents.now(), "on_behalf_of": None, **kw}
    S["history"].append(a)
    return a


# ---------------------------------------------------------------- state

@app.get("/")
def index():
    return FileResponse(HERE / "static" / "index.html")


@app.get("/api/state")
def state():
    pm = {"brand": "Visa", "cards": [{k: c[k] for k in ("panLastFour", "presentationName")}
                                     for c in S["payment_method"]["cards"]]}  # the browser never sees tokens or MRTs
    hide = ("code", "idToken")  # one-time codes and ID tokens stay server-side
    carts = {k: {**c, "src": {x: y for x, y in c["src"].items() if x not in hide}} if c.get("src") else c
             for k, c in S["carts"].items()}
    return {**S, "carts": carts, "payment_method": pm, "modes": {k: agents.mode(k) for k in agents.ROLES},
            "payments": "visa-simulated", "licence_labels": LICENCE_LABELS, "editable": EDITABLE,
            "export": export_check(), "today": date.today().isoformat()}


SNAPSHOT = HERE / "demo_snapshot.json"


@app.post("/api/snapshot/save")
def snapshot_save():
    """Keep the state right after a successful prepare (real CREAO runs) to restore if the network blocks CREAO."""
    if not any(r["mode"] == "creao" and r["status"] == "completed" for r in S["runs"]):
        raise HTTPException(409, "No completed CREAO runs to keep")
    SNAPSHOT.write_text(json.dumps(S, ensure_ascii=False, indent=1))
    return {"ok": True}


@app.post("/api/snapshot/restore")
def snapshot_restore():
    global S
    if not SNAPSHOT.exists():
        raise HTTPException(404, "No snapshot yet; run prepare_demo.py once on a network that reaches CREAO")
    S = json.loads(SNAPSHOT.read_text())
    save()
    return {"ok": True}


@app.post("/api/reset")
def reset():
    global S
    S = seed()
    save()
    return {"ok": True}


class Seen(BaseModel):
    member: str


@app.post("/api/seen")
def seen(body: Seen):
    S["last_seen"][member_ok(body.member)] = agents.now()
    save()
    return {"ok": True}


# ---------------------------------------------------------------- agents

class AgentAsk(BaseModel):
    member: str
    request: str = ""
    element_key: str | None = None
    spot_key: str | None = None
    licence: str = "commercial"
    budget_cents: int = 4000


def local_time(iso: str) -> str:
    from datetime import datetime
    d = datetime.fromisoformat(iso).astimezone()
    return d.strftime("%H:%M") if d.date() == datetime.now().astimezone().date() else d.strftime("%a %H:%M")


def saw_summary(kind: str, ctx: dict) -> list[str]:
    """Plain list of what the agent was sent, shown in the UI. Card details are never part of any context."""
    if kind == "curate":
        md = ctx["mandate"]
        n = sum(a["kind"] == ctx["spot"]["kind"] for a in ctx["catalog"])
        return [f"{len(ctx['rules'])} team rules with their kept / undone counts",
                f"{n} {ctx['spot']['kind'].replace('_', ' ')}s in the catalog with prices",
                f"{ctx['member']}'s limit: ${md['limit_cents'] // 100} a month, ${md['spent_cents'] / 100:.2f} spent, "
                f"set by {md['set_by']}"]
    if kind == "teammate":
        return [f"The {ctx['element']['name'].lower()} and its locked props",
                f"The last {len(ctx['history'])} changes to it", f"{len(ctx['rules'])} team rules"]
    return [f"{len(ctx['events'])} changes by others since you last looked",
            f"{len(ctx['open_conflicts'])} open conflicts"]


def rules_view() -> list[dict]:
    return [{**{k: r[k] for k in ("id", "text", "scope", "members", "kept", "undone", "requires")},
             "applies_to": r.get("applies_to", [])} for r in S["rules"]]


def context_for(kind: str, ask: AgentAsk) -> dict:
    m = ask.member
    if kind == "curate":
        spot = element(ask.spot_key or "hero_illustration")
        spot_kind = SPOT_KIND[spot["kind"]]
        return {"member": m, "spot": {"key": spot["key"], "label": spot["name"], "kind": spot_kind},
                "licence": ask.licence, "budget_cents": ask.budget_cents, "mandate": S["mandates"][m],
                "rules": rules_view(),
                "catalog": [{k: a[k] for k in ("id", "title", "creator", "kind", "style", "colours", "palette",
                                               "prices")} for a in S["catalog"]]}
    if kind == "teammate":
        el = element(ask.element_key or "hero_heading")
        hist = [{"who": (f"Strata for {h['on_behalf_of']}" if h["actor"] == "ai" else h["author"]),
                 "actor": h["actor"], "summary": h["summary"], "reason": h.get("ai_reason"),
                 "undone_by": h.get("undone_by")} for h in S["history"] if h["element_key"] == el["key"]][-8:]
        return {"member": m,
                "element": {k: el[k] for k in ("key", "name", "kind", "props", "locked_props", "locked_by")},
                "editable_props": EDITABLE[el["kind"]], "history": hist, "rules": rules_view(),
                "other_elements": [{"key": o["key"], "name": o["name"], "kind": o["kind"], "props": {
                    k: v for k, v in o["props"].items() if k in EDITABLE[o["kind"]]}, "editable_props": EDITABLE[o["kind"]],
                    "locked_props": o["locked_props"]} for o in S["elements"].values()
                    if o["key"] != el["key"] and EDITABLE[o["kind"]] and o["kind"] != "nav"]}
    since = S["last_seen"].get(m, "")
    events = [{"who": h["author"], "actor": h["actor"], "on_behalf_of": h.get("on_behalf_of"),
               "element": S["elements"][h["element_key"]]["name"], "summary": h["summary"],
               "reason": h.get("ai_reason"), "at": local_time(h["at"])}
              for h in S["history"]
              if h["at"] > since and h["author"] != m and h.get("on_behalf_of") != m
              and not (h["kind"] == "prompt" and h["actor"] == "ai")]
    opens = [{"element": S["elements"][c["element_key"]]["name"], "question": c["question"]}
             for c in S["conflicts"] if c["status"] == "open" and m in (c["locked_by"], c["member"])]
    return {"member": m, "since": since, "events": events, "open_conflicts": opens}


@app.post("/api/agents/{kind}")
async def start_agent(kind: str, ask: AgentAsk):
    if kind not in agents.ROLES:
        raise HTTPException(404, "unknown agent")
    member_ok(ask.member)
    ask.request = ask.request.strip()[:500]
    ask.budget_cents = max(0, min(1_000_000, ask.budget_cents))
    if kind == "teammate":
        ask.element_key = ask.element_key or "hero_heading"
        if not EDITABLE[element(ask.element_key)["kind"]]:
            raise HTTPException(400, "Strata edits text and style here; use the shop for art and icons")
        if not ask.request:
            raise HTTPException(400, "Tell Strata what to change")
    if kind == "curate":
        ask.spot_key = ask.spot_key or "hero_illustration"
        if element(ask.spot_key)["kind"] not in SPOT_KIND:
            raise HTTPException(400, "The shop fills art, icon and pattern elements")
    if any(r["kind"] == kind and r["member"] == ask.member and r["status"] in ("queued", "running")
           and r["element_key"] == ask.element_key and r["spot_key"] == ask.spot_key for r in S["runs"]):
        raise HTTPException(409, "Strata is already working on this")
    how = agents.mode(kind)
    if how == "missing":
        raise HTTPException(503, f"The {kind} agent isn't connected. Add CREAO_{agents.ROLES[kind]}_APP_ID "
                                 f"and CREAO_{agents.ROLES[kind]}_KEY to .env and restart.")
    ctx = context_for(kind, ask)
    run = {"saw": saw_summary(kind, ctx), "id": uid("r"), "kind": kind, "member": ask.member, "request": ask.request,
           "element_key": ask.element_key, "spot_key": ask.spot_key, "licence": ask.licence,
           "status": "queued", "mode": how, "run_id": None, "started": agents.now(), "finished": None,
           "message": ""}
    S["runs"].append(run)
    S["runs"] = S["runs"][-40:]
    save()
    asyncio.create_task(execute(run, ctx))
    return run


async def execute(run: dict, ctx: dict) -> None:
    def started(run_id):
        run.update(status="running", run_id=run_id)
        save()

    try:
        if run["mode"] == "creao":
            reply, raw = await agents.run_creao(run["kind"], run["request"], ctx, started)
            run["raw"] = raw[:4000]
        else:
            started("offline")
            await asyncio.sleep(2.5)
            reply = agents.OFFLINE[run["kind"]](run["request"], ctx)
        APPLY[run["kind"]](run, reply)
        run["status"] = "completed"
    except httpx.HTTPError as e:  # network: DNS blocked, offline, timeout
        run.update(status="failed", message=f"can't reach CREAO from this network ({e.__class__.__name__})")
    except Exception as e:  # noqa: BLE001 - shown to the user as a quiet failure line
        run.update(status="failed", message=(str(e) or e.__class__.__name__)[:300])
    run["finished"] = agents.now()
    save()


def apply_curate(run: dict, reply: dict) -> None:
    spot = element(run["spot_key"] or "hero_illustration")
    known = {a["id"] for a in S["catalog"] if a["kind"] == SPOT_KIND.get(spot["kind"])}
    items, seen = [], set()
    for i in reply.get("shortlist", []):
        if isinstance(i, dict) and i.get("asset_id") in known and i["asset_id"] not in seen:
            seen.add(i["asset_id"])
            items.append(i)
    items = items[:4]
    if not items:
        raise ValueError("the curator returned no catalog items")
    for n, i in enumerate(items, 1):
        i["rank"] = n
        i.setdefault("fits", [])
        i.setdefault("breaks", [])
    key = f"{run['member']}:{run['spot_key'] or 'hero_illustration'}"
    S["shortlists"][key] = {"summary": reply.get("summary", ""), "items": items, "licence": run["licence"],
                            "run_id": run["run_id"], "mode": run["mode"], "at": agents.now(),
                            "saw": run.get("saw", [])}
    run["message"] = reply.get("summary", "")
    atom(element_key=run["spot_key"] or "hero_illustration", kind="rule", actor="ai", author="Strata",
         on_behalf_of=run["member"], summary=f"Shortlisted {len(items)} assets",
         ai_reason=reply.get("summary", ""), status="info")


PROP_NAME = {"color": "colour", "font_size": "size", "font_weight": "weight", "bg": "background"}
HEX = re.compile(r"#[0-9a-fA-F]{6}")


def clean_props(el: dict, props: dict) -> dict:
    allowed, out = EDITABLE[el["kind"]], {}
    for k, v in (props or {}).items():
        t = allowed.get(k)
        if t == "hex" and isinstance(v, str) and HEX.fullmatch(v.strip()):
            out[k] = v.strip().upper()
        elif t == "number" and isinstance(v, (int, float)):
            lo, hi = (12, 96) if k == "font_size" else (300, 900)
            out[k] = int(max(lo, min(hi, v)))
        elif t == "string" and isinstance(v, str) and v.strip():
            out[k] = v.strip()[:160]
    return {k: v for k, v in out.items() if el["props"].get(k) != v}


def apply_teammate(run: dict, reply: dict) -> None:
    el, m = element(run["element_key"] or "hero_heading"), run["member"]
    action = reply.get("action")
    props = clean_props(el, reply.get("props") or {})
    locked = [k for k in props if k in el["locked_props"]]
    if action == "conflict" or locked:  # the app double-checks locks; the agent should already have stopped
        prop = reply.get("prop") or (locked[0] if locked else "")
        wants = reply.get("wants") or str(props.get(prop, ""))
        c = {"id": uid("c"), "element_key": el["key"], "prop": prop, "locked_by": el["locked_by"],
             "locked_value": el["props"].get(prop), "member": m, "wants": wants, "request": run["request"],
             "reason": reply.get("reason", ""), "status": "open", "at": agents.now(),
             "rule_ids": reply.get("rule_ids") or [],
             "question": f"{m} wants {prop} {wants}; {el['locked_by']} locked it. Keep or change?"}
        mg = reply.get("middle_ground") if isinstance(reply.get("middle_ground"), dict) else None
        target = S["elements"].get((mg or {}).get("element_key") or "")
        if mg and target:
            mprops = {k: v for k, v in clean_props(target, mg.get("props") or {}).items() if k not in target["locked_props"]}
            if mprops:
                c["suggestion"] = {"element_key": target["key"], "element": target["name"], "props": mprops,
                                   "before": {k: target["props"].get(k) for k in mprops},
                                   "summary": str(mg.get("summary") or "")[:120], "why": str(mg.get("why") or "")[:240]}
        S["conflicts"].append(c)
        atom(element_key=el["key"], kind="conflict", actor="ai", author="Strata", on_behalf_of=m,
             summary=f"Stopped: would change {el['locked_by']}'s locked {PROP_NAME.get(prop, prop)}", ai_reason=c["reason"],
             conflict_id=c["id"], status="info")
        run["message"] = c["reason"]
        return
    if action != "edit" or not props:
        run["message"] = reply.get("reason") or "Strata didn't change anything."
        atom(element_key=el["key"], kind="prompt", actor="ai", author="Strata", on_behalf_of=m,
             summary=f"Asked: “{run['request']}” · no change", ai_reason=run["message"], status="info")
        return
    before = {k: el["props"].get(k) for k in props}
    el["props"].update(props)
    el.update(authorship="ai", last_author=f"Strata for {m}")
    atom(element_key=el["key"], kind="edit", actor="ai", author="Strata", on_behalf_of=m,
         summary=reply.get("summary") or ", ".join(f"{k} {before[k]} → {v}" for k, v in props.items()),
         ai_reason=reply.get("reason", ""), before=before, after=props, status="proposed",
         rule_ids=[r for r in reply.get("rule_ids") or [] if any(x["id"] == r for x in S["rules"])],
         request=run["request"])
    run["message"] = reply.get("reason", "")


def apply_catchup(run: dict, reply: dict) -> None:
    lines = [str(x)[:300] for x in reply.get("lines", [])][:5]
    S["catchups"][run["member"]] = {"lines": lines, "question": reply.get("question", ""),
                                    "run_id": run["run_id"], "mode": run["mode"], "at": agents.now(),
                                    "saw": run.get("saw", [])}
    run["message"] = lines[0] if lines else ""


APPLY = {"curate": apply_curate, "teammate": apply_teammate, "catchup": apply_catchup}


# ---------------------------------------------------------------- keep / undo (how Strata learns)

class Who(BaseModel):
    member: str
    choice: str = ""


def bump(rule_ids: list[str], field: str) -> None:
    for r in S["rules"]:
        if r["id"] in rule_ids:
            r[field] += 1


@app.post("/api/history/{hid}/{verdict}")
def judge(hid: str, verdict: str, who: Who):
    m = member_ok(who.member)
    h = next((x for x in S["history"] if x["id"] == hid), None)
    if not h or h.get("status") != "proposed":
        raise HTTPException(409, "already decided")
    el = element(h["element_key"])
    if verdict == "keep":
        h.update(status="kept", kept_by=m)
        bump(h.get("rule_ids", []), "kept")
    elif verdict == "undo":
        after = h.get("after") or {}
        still = {k: v for k, v in (h.get("before") or {}).items() if k in after and el["props"].get(k) == after[k]}
        if not still:
            raise HTTPException(409, "Someone changed this since; nothing to undo")
        el["props"].update(still)
        el.update(authorship="human", last_author=m)
        h.update(status="undone", undone_by=m)
        bump(h.get("rule_ids", []), "undone")
    else:
        raise HTTPException(400, "keep or undo")
    save()
    return {"ok": True}


@app.post("/api/conflicts/{cid}")
def resolve(cid: str, who: Who):
    m = member_ok(who.member)
    c = next((x for x in S["conflicts"] if x["id"] == cid), None)
    if not c or c["status"] not in ("open", "asked"):
        raise HTTPException(409, "already resolved")
    el = element(c["element_key"])
    if who.choice == "middle":
        sg = c.get("suggestion")
        if not sg:
            raise HTTPException(409, "Strata didn't suggest a middle ground for this one")
        if m not in (c["locked_by"], c["member"], "Priya"):
            raise HTTPException(403, f"Only {c['member']} or {c['locked_by']} can accept this")
        target = element(sg["element_key"])
        if any(k in target["locked_props"] for k in sg["props"]):
            raise HTTPException(409, "That middle ground now touches a locked choice")
        before = {k: target["props"].get(k) for k in sg["props"]}
        target["props"].update(sg["props"])
        target.update(authorship="ai", last_author=f"Strata for {c['member']} and {c['locked_by']}")
        atom(element_key=target["key"], kind="edit", actor="ai", author="Strata",
             on_behalf_of=f"{c['member']} & {c['locked_by']}", summary=f"Middle ground: {sg['summary'] or 'applied'}",
             ai_reason=sg["why"], before=before, after=sg["props"], status="proposed", rule_ids=c.get("rule_ids", []),
             request=c.get("request"))
        atom(element_key=c["element_key"], kind="lock", actor="human", author=m,
             summary=f"Accepted Strata's middle ground; the {PROP_NAME.get(c['prop'], c['prop'])} stays locked")
        c.update(status="resolved", resolved_by=m)
        bump(c.get("rule_ids", []), "kept")
        save()
        return {"ok": True}
    if who.choice == "ask":
        c["status"] = "asked"
        atom(element_key=el["key"], kind="prompt", actor="human", author=m,
             summary=f"Asked {c['locked_by']} about the {PROP_NAME.get(c['prop'], c['prop'])}")
    elif who.choice in ("keep", "use"):
        if m not in (c["locked_by"], "Priya"):
            raise HTTPException(403, f"Only {c['locked_by']} can decide this")
        if who.choice == "keep":
            c["status"] = "kept"
            bump(c.get("rule_ids", []), "kept")
            atom(element_key=el["key"], kind="lock", actor="human", author=m,
                 summary=f"Kept the locked {PROP_NAME.get(c['prop'], c['prop'])}")
        else:
            value = HEX.search(c["wants"] or "")
            if not value or c["prop"] not in EDITABLE[el["kind"]]:
                raise HTTPException(409, "Strata didn't say which value to use; ask it again with a specific value")
            if value:
                before = {c["prop"]: el["props"].get(c["prop"])}
                el["props"][c["prop"]] = value.group(0).upper()
                el["locked_props"] = [p for p in el["locked_props"] if p != c["prop"]]
                if not el["locked_props"]:
                    el["locked_by"] = None
                atom(element_key=el["key"], kind="edit", actor="human", author=m,
                     summary=f"Unlocked and changed the {PROP_NAME.get(c['prop'], c['prop'])} for {c['member']}", before=before,
                     after={c["prop"]: el["props"][c["prop"]]})
            c["status"] = "replaced"
            bump(c.get("rule_ids", []), "undone")
    else:
        raise HTTPException(400, "keep, use or ask")
    save()
    return {"ok": True}


# ---------------------------------------------------------------- shop, limit, checkout, licenses

class CartIn(BaseModel):
    member: str
    asset_id: str
    licence: str
    element_key: str = "hero_illustration"
    upgrade_of: str | None = None


def money(c: int) -> str:
    return f"${c / 100:.2f}"


def dollars(c: int) -> str:
    return f"${c // 100}" if c % 100 == 0 else money(c)


def expired(md: dict) -> bool:
    return md.get("expires", "9999") < date.today().isoformat()


def intent_text(m: str, md: dict) -> str:
    top = max(md["allowed_licences"], key=TIER_RANK.get)
    until = date.fromisoformat(md["expires"]).strftime("%b %-d")
    if expired(md):
        return f"{m}'s spending limit ended {until}. Anything new needs {md['set_by']}'s OK."
    return f"{m} may spend up to {dollars(md['limit_cents'])} a month on {top} licenses, until {until}. Set by {md['set_by']}."


def check_limit(m: str, licence: str, price: int) -> str | None:
    """None if the purchase fits the mandate, else why not."""
    md = S["mandates"][m]
    left = md["limit_cents"] - md["spent_cents"]
    if expired(md):
        return f"{m}'s spending limit expired; needs {md['set_by']}'s OK"
    if licence not in md["allowed_licences"]:
        return f"{licence.capitalize()} licenses aren't in {m}'s limit; needs {md['set_by']}'s OK"
    if price > left:
        return f"Over {m}'s limit ({money(max(0, left))} left); needs {md['set_by']}'s OK"
    return None


def team_rule_people() -> str:
    return ", ".join(sorted({p for r in S["rules"] if r["scope"] == "team" for p in r["members"]}))


@app.post("/api/cart")
def make_cart(body: CartIn):
    m, a, el = member_ok(body.member), asset(body.asset_id), element(body.element_key)
    if body.licence not in LICENCE_LABELS:
        raise HTTPException(400, "unknown license")
    if SPOT_KIND.get(el["kind"]) != a["kind"]:
        raise HTTPException(400, f"{a['title']} doesn't fit the {el['name'].lower()}")
    old = None
    if body.upgrade_of:
        old = next((l for l in S["licences"] if l["licence_id"] == body.upgrade_of and l["status"] == "active"), None)
        if not old or old["asset_id"] != a["id"] or TIER_RANK[body.licence] <= TIER_RANK[old["tier"]]:
            raise HTTPException(409, "Nothing to upgrade")
    else:
        have = next((l for l in S["licences"] if l["asset_id"] == a["id"] and l["status"] == "active"
                     and el["key"] in l["element_keys"] and TIER_RANK[l["tier"]] >= TIER_RANK[body.licence]), None)
        if have:
            raise HTTPException(409, f"Already licensed ({have['tier']})")
    price = a["prices"][body.licence] - (old["amount_cents"] if old else 0)
    price = max(0, price)
    md = S["mandates"][m]
    why_not = check_limit(m, body.licence, price)
    sl = S["shortlists"].get(f"{m}:{el['key']}") or {}
    now = agents.now()
    what = (f"Upgrade {old['member']}'s personal license to commercial, {money(price)}" if old else
            f"One {body.licence} license, {dollars(price)}")
    trail = [{"step": "Intent", "ok": not expired(md), "text": intent_text(m, md), "at": now},
             {"step": "Cart", "ok": not why_not, "at": now,
              "text": f"{what}. {'Fits the limit.' if not why_not else why_not + '.'}"}]
    cart = {"id": uid("cart_"), "member": m, "asset_id": a["id"], "title": a["title"], "licence": body.licence,
            "element_key": el["key"], "amount_cents": price, "upgrade_of": body.upgrade_of,
            "suggested": any(i.get("asset_id") == a["id"] for i in sl.get("items", [])),
            "status": "needs_approval" if why_not else "ready", "trail": trail, "created": now}
    S["carts"][cart["id"]] = cart
    save()
    return cart


def cart_of(cart_id: str) -> dict:
    cart = S["carts"].get(cart_id)
    if not cart:
        raise HTTPException(404, "no such cart")
    return cart


@app.post("/api/cart/{cart_id}/ask")
def ask_approval(cart_id: str, who: Who):
    cart = cart_of(cart_id)
    if cart["status"] not in ("needs_approval", "declined"):
        raise HTTPException(409, "This cart doesn't need approval")
    if who.member != cart["member"]:
        raise HTTPException(403, f"Only {cart['member']} can ask for this one")
    lead = S["mandates"][cart["member"]]["set_by"]
    if not cart.get("approval_requested"):
        cart.update(approval_requested=True, status="needs_approval")
        cart["trail"].append({"step": "Approval", "text": f"Asked {lead} to approve {money(cart['amount_cents'])}",
                              "at": agents.now()})
        save()
    return cart


@app.post("/api/cart/{cart_id}/approve")
def approve(cart_id: str, who: Who):
    cart = cart_of(cart_id)
    lead = S["mandates"][cart["member"]]["set_by"]
    if who.member != lead:
        raise HTTPException(403, f"Only {lead} can approve")
    if cart["status"] not in ("needs_approval", "declined"):
        raise HTTPException(409, "Nothing to approve")
    cart.update(status="ready", approved_by=lead)
    cart["trail"].append({"step": "Approved", "text": f"{lead} approved this one purchase, {money(cart['amount_cents'])}",
                          "at": agents.now()})
    save()
    return cart


DECLINE_CODES = {"expired": ("54", "Expired payment instruction"), "tier": ("57", "Not permitted for this agent"),
                 "limit": ("61", "Exceeds spend control")}


def controls_for(cart: dict) -> list[dict]:
    """Visa Intelligent Commerce style spend controls on Strata's agent token, checked for this cart."""
    m, md = cart["member"], S["mandates"][cart["member"]]
    left = md["limit_cents"] - md["spent_cents"]
    approved = cart.get("approved_by")
    return [
        {"label": f"Up to {dollars(md['limit_cents'])} a month for {m}" + (f" · approved by {approved}" if approved else ""),
         "ok": bool(approved) or cart["amount_cents"] <= left, "code": "limit",
         "detail": f"{money(max(0, left))} left before this"},
        {"label": f"{cart['licence'].capitalize()} licenses allowed", "code": "tier",
         "ok": bool(approved) or cart["licence"] in md["allowed_licences"],
         "detail": ", ".join(md["allowed_licences"])},
        {"label": "Design assets only", "ok": True, "code": "category", "detail": "Digital goods · design assets"},
        {"label": f"Valid until {md['expires']}", "ok": not expired(md), "code": "expired", "detail": f"set by {md['set_by']}"},
    ]


# ---------------------------------------------------------------- Visa Click to Pay (EMVCo SRC), simulated
# Mirrors the Click to Pay SDK flow from developer.visa.com: init → isRecognized → identityLookup →
# initiateIdentityValidation → completeIdentityValidation → getSrcProfile → checkout (→ authenticate on step-up) →
# DPA fetches the payment payload (Visa token + TAVV cryptogram) → authorization. Strata is the Digital Terminal
# and DCF (merchant-orchestrated checkout); "Strata Asset Store" is the DPA. Nothing real is charged.

DPA = {"srciDpaId": "dpa_strata_asset_store", "srcInitiatorId": "srci_strata", "dpaName": "Strata Asset Store",
       "dpaAcceptedBillingCountries": ["US"]}
TERMS = "https://www.visa.com/en_US/checkout/legal/terms-of-service.html"
PRIVACY = "https://www.visa.com/en_US/checkout/legal/global-privacy-notice.html"


class Src(BaseModel):
    member: str
    email: str = ""
    code: str = ""
    card: str = ""
    remember: bool = True
    consent: bool = False


def src_of(cart_id: str, body: Src) -> dict:
    cart = cart_of(cart_id)
    if body.member != cart["member"]:
        raise HTTPException(403, f"Only {cart['member']} can pay for this; it's on their limit")
    return cart


def mask_email(e: str) -> str:
    name, _, dom = e.partition("@")
    return f"{name[:1]}***@{dom}"


def masked_cards() -> list[dict]:
    cards = []
    for c in S["payment_method"]["cards"]:
        ok = c["billingCountry"] in DPA["dpaAcceptedBillingCountries"]
        cards.append({k: c[k] for k in ("srcDigitalCardId", "panLastFour", "panExpirationMonth", "panExpirationYear",
                                         "presentationName", "holder", "dateOfCardLastUsed")} |
                     {"usable": ok, "reason": "" if ok else "Billing country isn't accepted by this merchant"})
    # usable first, then by last use (as Visa recommends)
    return sorted(cards, key=lambda c: (not c["usable"], c["dateOfCardLastUsed"] is None, c["dateOfCardLastUsed"] or ""))


def src_view(cart: dict) -> dict:
    src = cart["src"]
    out = {"cart": cart, "screen": src["screen"], "maskedValidationChannel": src.get("maskedValidationChannel"),
           "email": src.get("email"), "dpa": DPA, "terms": TERMS, "privacy": PRIVACY,
           "rules": controls_for(cart), "steps": src.get("steps", []), "simulatedCode": src.get("code")}
    if src["screen"] in ("cards", "review", "authenticate"):
        out["maskedCards"] = masked_cards()
        out["selected"] = src.get("card")
    return out


def src_step(cart: dict, t: str, x: str = "", ok: bool = True) -> None:
    cart["src"].setdefault("steps", []).append({"t": t, "x": x, "ok": ok})


@app.post("/api/cart/{cart_id}/src/init")
def src_init(cart_id: str, body: Src):
    """init() + isRecognized(): open Click to Pay after Strata checks the team's spending rules."""
    cart = src_of(cart_id, body)
    if cart["status"] not in ("ready", "paid"):
        raise HTTPException(409, "This cart isn't ready to pay")
    if cart["status"] == "paid":
        return src_view(cart)
    mrt = S["payment_method"]["recognition"].get(cart["member"])
    cart["src"] = {"srciTransactionId": str(uuid.uuid4()), "steps": [],
                   "dpaTransactionOptions": {"transactionAmount": {"transactionAmount": cart["amount_cents"] / 100,
                                                                   "transactionCurrencyCode": "USD"},
                                             "dpaLocale": "en_US", "dpaShippingPreference": "NONE",
                                             "paymentOptions": [{"dynamicDataType": "CARD_APPLICATION_CRYPTOGRAM_LONG_FORM"}],
                                             "customInputData": {"checkoutOrchestrator": "merchant"}},
                   "screen": "cards" if mrt else "lookup", "recognized": bool(mrt),
                   "email": S["payment_method"]["consumers"].get(cart["member"], "")}
    if mrt:
        cart["src"]["idToken"] = "idt_" + secrets.token_hex(8)
    save()
    return src_view(cart)


@app.post("/api/cart/{cart_id}/src/lookup")
def src_lookup(cart_id: str, body: Src):
    """identityLookup() then initiateIdentityValidation(): Visa sends a one-time code."""
    cart = src_of(cart_id, body)
    email = body.email.strip().lower()
    if email not in S["payment_method"]["consumers"].values():
        raise HTTPException(404, "No Click to Pay profile for that email. Try your work email.")
    code = "".join(secrets.choice(string.digits) for _ in range(6))
    cart["src"].update(email=email, code=code, attempts=0, screen="otp", maskedValidationChannel=mask_email(email))
    save()
    return src_view(cart)


@app.post("/api/cart/{cart_id}/src/validate")
def src_validate(cart_id: str, body: Src):
    """completeIdentityValidation(): the code returns an ID token; getSrcProfile() then lists masked cards."""
    cart = src_of(cart_id, body)
    src = cart["src"]
    if src.get("screen") != "otp":
        raise HTTPException(409, "Ask for a code first")
    src["attempts"] = src.get("attempts", 0) + 1
    if body.code.strip() != src.get("code"):
        if src["attempts"] >= 3:
            src.update(screen="lookup", code=None)
            save()
            raise HTTPException(429, "Too many wrong codes. Start again.")
        save()
        raise HTTPException(400, "That code didn't match. Check the latest code.")
    src.update(idToken="idt_" + secrets.token_hex(8), screen="cards", code=None)
    save()
    return src_view(cart)


@app.post("/api/cart/{cart_id}/src/select")
def src_select(cart_id: str, body: Src):
    cart = src_of(cart_id, body)
    if not cart["src"].get("idToken"):
        raise HTTPException(401, "Verify your identity first")
    card = next((c for c in masked_cards() if c["srcDigitalCardId"] == body.card), None)
    if not card or not card["usable"]:
        raise HTTPException(400, "This card can't be used here")
    cart["src"].update(card=body.card, screen="review")
    save()
    return src_view(cart)


async def authorize(cart: dict, authenticated: bool) -> dict:
    """The DPA fetches the full payment payload by reference and authorizes through VisaNet (simulated)."""
    src, now = cart["src"], agents.now()
    card = next(c for c in S["payment_method"]["cards"] if c["srcDigitalCardId"] == src["card"])
    corr = str(uuid.uuid4())
    src_step(cart, "Checkout complete", f"dcfActionCode COMPLETE · transaction reference {corr[:13]}…")
    await asyncio.sleep(0.6)
    crypt = "CARD_APPLICATION_CRYPTOGRAM_LONG_FORM (TAVV)" + (" + CARDHOLDER_AUTHENTICATION_CRYPTOGRAM" if authenticated else "")
    src_step(cart, "Payment payload retrieved", f"Visa token •••• {card['tokenLastFour']} · {crypt} · card number never shared")
    await asyncio.sleep(0.6)
    approval = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    txn = "".join(secrets.choice(string.digits) for _ in range(15))
    src_step(cart, "Authorized through VisaNet", f"Response 00 Approved · approval code {approval} · ECI {'05' if authenticated else '07'}")
    cart.update(auth_code=approval, network_token=f"•••• {card['tokenLastFour']}",
                auth={"approved": True, "response_code": "00", "auth_code": approval, "txn_id": txn,
                      "srcCorrelationId": corr, "token_last4": card["tokenLastFour"], "card_last4": card["panLastFour"],
                      "card_name": card["presentationName"], "authenticated": authenticated, "at": now})
    src["screen"] = "approved"
    cart["trail"].append({"step": "Payment", "at": now,
                          "text": f"Visa Click to Pay · {card['presentationName']} •••• {card['panLastFour']} · token •••• "
                                  f"{card['tokenLastFour']} · 00 approved · {approval}"})
    fulfil(cart)
    return src_view(cart)


@app.post("/api/cart/{cart_id}/src/checkout")
async def src_checkout(cart_id: str, body: Src):
    """checkout(): Click to Pay may ask for cardholder step-up based on risk; otherwise completes."""
    cart = src_of(cart_id, body)
    if cart["status"] == "paid":
        return src_view(cart)
    src = cart["src"]
    if src.get("screen") not in ("review",) or cart["status"] != "ready":
        raise HTTPException(409, "Review the payment first")
    if not body.consent:
        raise HTTPException(400, "Agree to the Visa Click to Pay Terms to continue")
    failed = next((c for c in controls_for(cart) if not c["ok"]), None)
    if failed:  # Strata's spending rules are re-checked before anything is sent to Visa
        code, text = DECLINE_CODES.get(failed["code"], ("05", "Do not honor"))
        cart["status"] = "declined"
        src.update(screen="declined")
        src_step(cart, "Stopped by Tally's spending rule", f"{failed['label']} · not sent to Visa", ok=False)
        cart["trail"].append({"step": "Payment", "ok": False, "at": agents.now(), "text": f"Stopped before Visa: {failed['label']}"})
        save()
        raise HTTPException(402, f"Stopped by Tally's spending rule: {failed['label']}. Ask {S['mandates'][cart['member']]['set_by']}.")
    if body.remember:
        S["payment_method"]["recognition"][cart["member"]] = "mrt_" + secrets.token_hex(8)
    cart["status"] = "paying"
    risky = cart["amount_cents"] > 5000 or bool(cart.get("approved_by"))
    if risky:  # risk-based step-up: Click to Pay asks the cardholder to authenticate
        src.update(screen="authenticate")
        src_step(cart, "Step-up requested", "Higher-risk purchase: Visa asks the cardholder to verify")
        save()
        return src_view(cart)
    save()
    return await authorize(cart, authenticated=False)


@app.post("/api/cart/{cart_id}/src/authenticate")
async def src_authenticate(cart_id: str, body: Src):
    """authenticate(): cardholder verifies (passkey); then the checkout completes."""
    cart = src_of(cart_id, body)
    if cart["status"] == "paid":
        return src_view(cart)
    if cart["src"].get("screen") != "authenticate":
        raise HTTPException(409, "No verification pending")
    src_step(cart, "Cardholder verified", "Passkey on this device (Visa Secure, simulated)")
    return await authorize(cart, authenticated=True)


@app.post("/api/cart/{cart_id}/src/forget")
def src_forget(cart_id: str, body: Src):
    """unbindAppInstance(): forget this browser for Click to Pay."""
    S["payment_method"]["recognition"].pop(member_ok(body.member), None)
    save()
    return {"ok": True}


def fulfil(cart: dict) -> None:
    if cart.get("licence_id"):
        return
    now, pm, m = agents.now(), S["payment_method"], cart["member"]
    el = element(cart["element_key"])
    old = next((l for l in S["licences"] if l["licence_id"] == cart.get("upgrade_of")), None)
    how = ([f"Upgraded {old['member']}'s personal license {old['licence_id']}"] if old else
           [f"Suggested by Strata from a team rule ({team_rule_people()})", f"tried on by {m}"] if cart.get("suggested")
           else [f"Picked by {m}", f"tried on by {m}"])
    how += ([f"approved by {cart['approved_by']}"] if cart.get("approved_by") else []) + \
        ["paid with Visa Click to Pay (simulated)", f"placed on the {el['name'].lower()}"]
    lic = {"licence_id": f"L-{uuid.uuid4().hex[:4].upper()}", "asset_id": cart["asset_id"],
           "tier": cart["licence"], "element_keys": [cart["element_key"]], "member": m,
           "amount_cents": cart["amount_cents"] + (old["amount_cents"] if old else 0), "paid_cents": cart["amount_cents"],
           "payment_ref": cart["auth_code"], "card": f"Visa {cart.get('auth', {}).get('card_last4', '')}", "network_token": cart["network_token"],
           "status": "active", "at": now, "how": how}
    for l in S["licences"]:  # a higher license for the same asset and element supersedes lower ones
        if l["status"] == "active" and l["asset_id"] == lic["asset_id"] and cart["element_key"] in l["element_keys"] \
                and TIER_RANK[l["tier"]] < TIER_RANK[lic["tier"]]:
            l["status"] = "upgraded"
    if old:
        old["status"] = "upgraded"
    S["licences"].append(lic)
    S["mandates"][m]["spent_cents"] += cart["amount_cents"]
    el["props"]["asset_id"] = cart["asset_id"]
    el.update(authorship="human", last_author=m)
    atom(element_key=el["key"], kind="purchase", actor="human", author=m,
         summary=f"Bought {cart['title']} · {cart['licence']} license · {money(cart['amount_cents'])} "
                 f"with Visa Click to Pay (•••• {cart.get('auth', {}).get('card_last4', '')})")
    cart.update(status="paid", licence_id=lic["licence_id"])
    cart["trail"].append({"step": "Receipt", "text": f"License {lic['licence_id']} filed against the {el['name'].lower()}",
                          "at": now})
    save()


@app.get("/api/export-check")
def export_check():
    issues = []
    for el in S["elements"].values():
        aid = el["props"].get("asset_id")
        if not aid:
            continue
        lic = max((l for l in S["licences"] if l["asset_id"] == aid and l["status"] == "active"
                   and el["key"] in l["element_keys"]), key=lambda l: TIER_RANK[l["tier"]], default=None)
        a = asset(aid)
        if not lic:
            issues.append({"element_key": el["key"], "element": el["name"], "asset": a["title"],
                           "problem": "no license", "asset_id": aid, "kind": a["kind"]})
        elif lic["tier"] == "personal" and S["file"]["client_work"]:
            issues.append({"element_key": el["key"], "element": el["name"], "asset": a["title"], "asset_id": aid,
                           "problem": f"personal license ({lic['member']}) in client work", "kind": a["kind"],
                           "member": lic["member"],
                           "licence_id": lic["licence_id"],
                           "upgrade_cents": a["prices"]["commercial"] - lic["amount_cents"]})
    return {"ok": not issues, "issues": issues}


if __name__ == "__main__":
    print(f"Strata demo → http://localhost:{PORT}")
    for k in agents.ROLES:
        print(f"  {k:9} agent: {agents.mode(k)}")
    print("  payments: Visa, simulated (no real charge)")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
