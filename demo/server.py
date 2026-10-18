"""Strata local demo: the workspace, shop and checkout run here; every AI step runs on a CREAO agent.

    uv run python demo/server.py        → http://localhost:8044
"""

from __future__ import annotations

import asyncio
import copy
import json
import os
import re
import sys
import uuid
from pathlib import Path

import httpx
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
sys.path.insert(0, str(HERE))
load_dotenv(REPO / ".env")

import agents  # noqa: E402
from seed_data import EDITABLE, seed  # noqa: E402

PORT = int(os.getenv("STRATA_DEMO_PORT", "8044"))
STATE_FILE = HERE / "state.json"
LICENCE_LABELS = {"personal": "Personal · not for client work", "commercial": "Commercial · site and app",
                  "extended": "Extended · print and merchandise"}

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


def stripe_key() -> str | None:
    key = os.getenv("STRIPE_SECRET_KEY", "")
    return key if key.startswith("sk_test_") else None  # test mode only, never live


# ---------------------------------------------------------------- state

@app.get("/")
def index():
    return FileResponse(HERE / "static" / "index.html")


@app.get("/api/state")
def state():
    return {**S, "modes": {k: agents.mode(k) for k in agents.ROLES},
            "payments": "stripe-test" if stripe_key() else "simulated", "licence_labels": LICENCE_LABELS}


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
               "reason": h.get("ai_reason"), "at": h["at"]}
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
    known = {a["id"] for a in S["catalog"]}
    items = [i for i in reply.get("shortlist", []) if i.get("asset_id") in known][:4]
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
        el["props"].update(h["before"])
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


# ---------------------------------------------------------------- shop, limit, checkout, licences

class CartIn(BaseModel):
    member: str
    asset_id: str
    licence: str
    element_key: str = "hero_illustration"
    upgrade_of: str | None = None


def money(c: int) -> str:
    return f"${c / 100:.2f}"


@app.post("/api/cart")
def make_cart(body: CartIn):
    m, a, el = member_ok(body.member), asset(body.asset_id), element(body.element_key)
    if body.licence not in LICENCE_LABELS:
        raise HTTPException(400, "unknown licence")
    price = a["prices"][body.licence]
    if body.upgrade_of:
        old = next((l for l in S["licences"] if l["licence_id"] == body.upgrade_of), None)
        if old:
            price = max(0, price - old["amount_cents"])
    md = S["mandates"][m]
    left = md["limit_cents"] - md["spent_cents"]
    within = price <= left and body.licence in md["allowed_licences"]
    now = agents.now()
    trail = [
        {"step": "Intent", "text": f"{m} wants {a['title']} for the {el['name'].lower()}", "at": now},
        {"step": "Cart", "text": f"{a['title']} · {LICENCE_LABELS[body.licence]} · {money(price)}", "at": now},
        {"step": "Limit", "ok": within, "at": now,
         "text": (f"Within {m}'s {money(md['limit_cents'])} limit set by {md['set_by']} · "
                  f"{money(left - price)} left after" if within else
                  f"Over {m}'s limit ({money(left)} left) · needs {md['set_by']}'s OK")},
    ]
    cart = {"id": uid("cart_"), "member": m, "asset_id": a["id"], "title": a["title"], "licence": body.licence,
            "element_key": el["key"], "amount_cents": price, "upgrade_of": body.upgrade_of,
            "status": "ready" if within else "needs_approval", "trail": trail, "created": now}
    S["carts"][cart["id"]] = cart
    save()
    return cart


@app.post("/api/cart/{cart_id}/approve")
def approve(cart_id: str, who: Who):
    cart = S["carts"].get(cart_id) or {}
    lead = S["mandates"][cart.get("member", "Alex")]["set_by"]
    if who.member != lead:
        raise HTTPException(403, f"Only {lead} can approve")
    cart["status"] = "ready"
    cart["trail"].append({"step": "Approved", "text": f"{lead} approved this one purchase", "at": agents.now()})
    save()
    return cart


@app.post("/api/cart/{cart_id}/pay")
async def pay(cart_id: str):
    cart = S["carts"].get(cart_id)
    if not cart or cart["status"] != "ready":
        raise HTTPException(409, "cart isn't ready to pay")
    key = stripe_key()
    if not key:
        fulfil(cart, f"sim_{uuid.uuid4().hex[:10]}", "Simulated test payment (no Stripe key set)")
        return {"done": True, "cart": cart}
    base = f"http://localhost:{PORT}"
    form = {
        "mode": "payment",
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][unit_amount]": str(max(cart["amount_cents"], 50)),
        "line_items[0][price_data][product_data][name]": f"{cart['title']} · {cart['licence']} licence",
        "success_url": f"{base}/paid?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{base}/?cancelled={cart_id}",
        "metadata[cart_id]": cart_id,
        "metadata[member]": cart["member"],
    }
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post("https://api.stripe.com/v1/checkout/sessions", data=form, auth=(key, ""))
    if r.status_code >= 400:
        raise HTTPException(502, f"Stripe: {r.json().get('error', {}).get('message', r.status_code)}")
    session = r.json()
    cart["trail"].append({"step": "Payment", "text": "Stripe test checkout opened", "at": agents.now()})
    save()
    return {"url": session["url"]}


@app.get("/paid")
async def paid(session_id: str):
    key = stripe_key()
    if not key:
        return RedirectResponse("/")
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(f"https://api.stripe.com/v1/checkout/sessions/{session_id}", auth=(key, ""))
    s = r.json()
    cart = S["carts"].get((s.get("metadata") or {}).get("cart_id", ""))
    if cart and s.get("payment_status") == "paid" and cart["status"] != "paid":
        fulfil(cart, s.get("payment_intent") or session_id, "Paid with Stripe test mode (Visa test card)")
    return RedirectResponse(f"/?paid={cart['id'] if cart else ''}")


def fulfil(cart: dict, payment_ref: str, how: str) -> None:
    if cart["status"] == "paid":
        return
    now = agents.now()
    lic = {"licence_id": f"L-{uuid.uuid4().hex[:4].upper()}", "asset_id": cart["asset_id"],
           "tier": cart["licence"], "element_keys": [cart["element_key"]], "member": cart["member"],
           "amount_cents": cart["amount_cents"], "payment_ref": payment_ref, "status": "active", "at": now}
    for old in S["licences"]:
        if old["licence_id"] == cart.get("upgrade_of"):
            old["status"] = "upgraded"
    S["licences"].append(lic)
    S["mandates"][cart["member"]]["spent_cents"] += cart["amount_cents"]
    el = element(cart["element_key"])
    el["props"]["asset_id"] = cart["asset_id"]
    el.update(authorship="human", last_author=cart["member"])
    atom(element_key=el["key"], kind="purchase", actor="human", author=cart["member"],
         summary=f"Bought {cart['title']} · {cart['licence']} licence · {money(cart['amount_cents'])}")
    cart["status"] = "paid"
    cart["licence_id"] = lic["licence_id"]
    cart["trail"] += [{"step": "Payment", "text": f"{how} · {payment_ref}", "at": now},
                      {"step": "Receipt", "text": f"Licence {lic['licence_id']} tied to {el['name']}", "at": now}]
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
                           "problem": "no licence", "asset_id": aid})
        elif lic["tier"] == "personal" and S["file"]["client_work"]:
            issues.append({"element_key": el["key"], "element": el["name"], "asset": a["title"], "asset_id": aid,
                           "problem": f"personal licence ({lic['member']}) in client work",
                           "licence_id": lic["licence_id"],
                           "upgrade_cents": a["prices"]["commercial"] - lic["amount_cents"]})
    return {"ok": not issues, "issues": issues}


if __name__ == "__main__":
    print(f"Strata demo → http://localhost:{PORT}")
    for k in agents.ROLES:
        print(f"  {k:9} agent: {agents.mode(k)}")
    print(f"  payments: {'Stripe test' if stripe_key() else 'simulated'}")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
