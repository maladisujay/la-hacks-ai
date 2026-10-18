"""Mock of the Strata backend (the Base44 app replaces it later, same routes).

Run: uv run uvicorn strata_agents.mock_strata:app --port 8090
"""

from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import seed
from .config import DATA_DIR, PREVIEW_DIR, settings

STATE_PATH = DATA_DIR / "strata_state.json"


def _fresh_state() -> dict:
    return {
        "files": copy.deepcopy(seed.FILES),
        "mandates": copy.deepcopy(seed.MANDATES),
        "rules": copy.deepcopy(seed.RULES),
        "licences": [],
        "history": [],
    }


def _load() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return _fresh_state()


STATE = _load()


def _save() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(STATE, indent=2))


def require_secret(x_strata_secret: str = Header(default="")) -> None:
    if x_strata_secret != settings.strata_api_secret:
        raise HTTPException(status_code=401, detail="bad secret")


app = FastAPI(title="Strata mock API")
PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/previews", StaticFiles(directory=PREVIEW_DIR), name="previews")


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.get("/files/{file_id}", dependencies=[Depends(require_secret)])
def get_file(file_id: str) -> dict:
    f = STATE["files"].get(file_id)
    if not f:
        raise HTTPException(404, "no such file")
    return f


@app.get("/teams/{team_id}/rules", dependencies=[Depends(require_secret)])
def get_rules(team_id: str) -> list[dict]:
    return STATE["rules"]


@app.get("/catalog", dependencies=[Depends(require_secret)])
def get_catalog(kind: str | None = None) -> list[dict]:
    return [a for a in seed.CATALOG if kind is None or a["kind"] == kind]


@app.get("/mandates/{member_id}", dependencies=[Depends(require_secret)])
def get_mandate(member_id: str) -> dict:
    m = STATE["mandates"].get(member_id)
    if not m:
        raise HTTPException(404, "no mandate")
    return m


class FulfilBody(BaseModel):
    member_id: str
    asset_id: str
    licence: str
    spot_ids: list[str]
    amount_cents: int
    payment_ref: str
    via: str = "ASI:One"


@app.post("/files/{file_id}/fulfil", dependencies=[Depends(require_secret)])
def fulfil(file_id: str, body: FulfilBody) -> dict:
    f = STATE["files"].get(file_id)
    if not f:
        raise HTTPException(404, "no such file")
    # Idempotent on payment_ref so a retried call never double-charges the mandate.
    for lic in STATE["licences"]:
        if lic["payment_ref"] == body.payment_ref:
            return lic
    m = STATE["mandates"][body.member_id]
    m["spent_cents"] += body.amount_cents
    licence_id = f"STR-{uuid.uuid4().hex[:4].upper()}"
    for spot in body.spot_ids:
        f["placements"][spot] = body.asset_id
        for s in f["spots"]:
            if s["id"] == spot:
                s["status"] = "licensed"
                s["note"] = f"{body.licence} licence"
    record = {
        "licence_id": licence_id,
        "file_id": file_id,
        "asset_id": body.asset_id,
        "licence": body.licence,
        "spot_ids": body.spot_ids,
        "member_id": body.member_id,
        "amount_cents": body.amount_cents,
        "payment_ref": body.payment_ref,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    STATE["licences"].append(record)
    STATE["history"].append({
        "kind": "purchase",
        "author": body.member_id,
        "via": body.via,
        "elements": body.spot_ids,
        "summary": f"Bought {body.asset_id} ({body.licence}) via {body.via}",
        "licence_id": licence_id,
        "at": record["at"],
    })
    _save()
    return record


@app.get("/files/{file_id}/history", dependencies=[Depends(require_secret)])
def history(file_id: str) -> list[dict]:
    return [h for h in STATE["history"]]


@app.post("/admin/reset", dependencies=[Depends(require_secret)])
def reset() -> dict:
    global STATE
    STATE = _fresh_state()
    _save()
    return {"ok": True}
