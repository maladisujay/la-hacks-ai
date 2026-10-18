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
SPOT_KIND = {"illustration_slot": "illustration", "icon_row": "icon_set"}

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
S.setdefault("payment_method", payment_method())


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
    pm = {k: v for k, v in S["payment_method"].items() if k != "token"}  # the browser never sees the token
    return {**S, "payment_method": pm, "modes": {k: agents.mode(k) for k in agents.ROLES},
            "payments": "visa-simulated", "licence_labels": LICENCE_LABELS, "editable": EDITABLE,
            "export": export_check(), "today": date.today().isoformat()}


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
    return datetime.fromisoformat(iso).astimezone().strftime("%a %H:%M")


def rules_view() -> list[dict]:
    return [{k: r[k] for k in ("id", "text", "scope", "members", "kept", "undone", "requires")} for r in S["rules"]]


def context_for(kind: str, ask: AgentAsk) -> dict:
    m = ask.member
    if kind == "curate":
        spot = element(ask.spot_key or "hero_illustration")
        spot_kind = "illustration" if spot["kind"] == "illustration_slot" else "icon_set"
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
                "editable_props": EDITABLE[el["kind"]], "history": hist, "rules": rules_view()}
    since = S["last_seen"].get(m, "")
    events = [{"who": h["author"], "actor": h["actor"], "on_behalf_of": h.get("on_behalf_of"),
               "element": S["elements"][h["element_key"]]["name"], "summary": h["summary"],
               "reason": h.get("ai_reason"), "at": local_time(h["at"])}
              for h in S["history"]
              if h["at"] > since and h["author"] != m and h.get("on_behalf_of") != m]
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
            raise HTTPException(400, "The shop fills the hero illustration or the feature row")
    if any(r["kind"] == kind and r["member"] == ask.member and r["status"] in ("queued", "running")
           and r["element_key"] == ask.element_key and r["spot_key"] == ask.spot_key for r in S["runs"]):
        raise HTTPException(409, "Strata is already working on this")
    how = agents.mode(kind)
    if how == "missing":
        raise HTTPException(503, f"The {kind} agent isn't connected. Add CREAO_{agents.ROLES[kind]}_APP_ID "
                                 f"and CREAO_{agents.ROLES[kind]}_KEY to .env and restart.")
    ctx = context_for(kind, ask)
    run = {"id": uid("r"), "kind": kind, "member": ask.member, "request": ask.request,
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
    except Exception as e:  # noqa: BLE001 - shown to the user as a quiet failure line
        run.update(status="failed", message=str(e)[:300])
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
                            "run_id": run["run_id"], "mode": run["mode"], "at": agents.now()}
    run["message"] = reply.get("summary", "")
    atom(element_key=run["spot_key"] or "hero_illustration", kind="rule", actor="ai", author="Strata",
         on_behalf_of=run["member"], summary=f"Shortlisted {len(items)} assets",
         ai_reason=reply.get("summary", ""), status="info")


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
             "locked_value": el["props"].get(prop), "member": m, "wants": wants,
             "reason": reply.get("reason", ""), "status": "open", "at": agents.now(),
             "rule_ids": reply.get("rule_ids") or [],
             "question": f"{m} wants {prop} {wants}; {el['locked_by']} locked it. Keep or change?"}
        S["conflicts"].append(c)
        atom(element_key=el["key"], kind="conflict", actor="ai", author="Strata", on_behalf_of=m,
             summary=f"Stopped: would change {el['locked_by']}'s locked {prop}", ai_reason=c["reason"],
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
    lines = [str(x)[:200] for x in reply.get("lines", [])][:5]
    S["catchups"][run["member"]] = {"lines": lines, "question": reply.get("question", ""),
                                    "run_id": run["run_id"], "mode": run["mode"], "at": agents.now()}
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
    if who.choice == "ask":
        c["status"] = "asked"
        atom(element_key=el["key"], kind="prompt", actor="human", author=m,
             summary=f"Asked {c['locked_by']} about the {c['prop']}")
    elif who.choice in ("keep", "use"):
        if m not in (c["locked_by"], "Priya"):
            raise HTTPException(403, f"Only {c['locked_by']} can decide this")
        if who.choice == "keep":
            c["status"] = "kept"
            bump(c.get("rule_ids", []), "kept")
            atom(element_key=el["key"], kind="lock", actor="human", author=m,
                 summary=f"Kept the locked {c['prop']}")
        else:
            value = HEX.search(c["wants"] or "")
            if value and c["prop"] in EDITABLE[el["kind"]]:
                before = {c["prop"]: el["props"].get(c["prop"])}
                el["props"][c["prop"]] = value.group(0).upper()
                el["locked_props"] = [p for p in el["locked_props"] if p != c["prop"]]
                atom(element_key=el["key"], kind="edit", actor="human", author=m,
                     summary=f"Unlocked and changed {c['prop']} for {c['member']}", before=before,
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


@app.post("/api/cart/{cart_id}/pay")
async def pay(cart_id: str):
    cart = cart_of(cart_id)
    if cart["status"] in ("paid", "paying"):  # idempotent: a double click never charges twice
        return cart
    if cart["status"] != "ready":
        raise HTTPException(409, "This cart isn't ready to pay")
    why_not = None if cart.get("approved_by") else check_limit(cart["member"], cart["licence"], cart["amount_cents"])
    if why_not:  # the limit is re-checked at pay time: it may have changed since the cart was made
        cart["status"] = "declined"
        cart["trail"].append({"step": "Payment", "ok": False, "text": f"Declined before charging: {why_not}",
                              "at": agents.now()})
        save()
        raise HTTPException(402, f"Payment declined: {why_not}.")
    cart["status"] = "paying"
    save()
    await asyncio.sleep(1.2)  # simulated Visa authorization; nothing real is charged
    pm = S["payment_method"]
    auth = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    cart.update(auth_code=auth, network_token=f"vtok_…{pm['last4']}")
    cart["trail"].append({"step": "Payment", "at": agents.now(),
                          "text": f"Visa ending {pm['last4']} · authorized (simulated) · auth {auth} · "
                                  "Strata's agents never see the card"})
    fulfil(cart)
    return cart


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
        ["paid with Visa (simulated)", f"placed on the {el['name'].lower()}"]
    lic = {"licence_id": f"L-{uuid.uuid4().hex[:4].upper()}", "asset_id": cart["asset_id"],
           "tier": cart["licence"], "element_keys": [cart["element_key"]], "member": m,
           "amount_cents": cart["amount_cents"] + (old["amount_cents"] if old else 0), "paid_cents": cart["amount_cents"],
           "payment_ref": cart["auth_code"], "card": f"Visa {pm['last4']}", "network_token": cart["network_token"],
           "status": "active", "at": now, "how": how}
    if old:
        old["status"] = "upgraded"
    S["licences"].append(lic)
    S["mandates"][m]["spent_cents"] += cart["amount_cents"]
    el["props"]["asset_id"] = cart["asset_id"]
    el.update(authorship="human", last_author=m)
    atom(element_key=el["key"], kind="purchase", actor="human", author=m,
         summary=f"Bought {cart['title']} · {cart['licence']} license · {money(cart['amount_cents'])} "
                 f"with Visa ending {pm['last4']}")
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
        lic = next((l for l in S["licences"] if l["asset_id"] == aid and l["status"] == "active"
                    and el["key"] in l["element_keys"]), None)
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
