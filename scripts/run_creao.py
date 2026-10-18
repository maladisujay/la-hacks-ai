"""Start a CREAO agent run from your laptop (fallback when Base44 backend functions aren't available).

The agent writes its results into Base44 itself; the app's UI updates live.

    uv run python scripts/run_creao.py curate --member Alex --spot hero_illustration_slot --budget 40
    uv run python scripts/run_creao.py teammate --member Alex --element hero_heading --request "make it feel more premium"
    uv run python scripts/run_creao.py catchup --member Priya

Needs in .env: CREAO_CURATOR_APP_ID / CREAO_CURATOR_KEY (and TEAMMATE, CATCHUP likewise). Never commit them.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import httpx
from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("kind", choices=["curate", "teammate", "catchup"])
    p.add_argument("--member", default="Alex")
    p.add_argument("--spot", default="hero_illustration_slot")
    p.add_argument("--budget", type=float, default=40)
    p.add_argument("--licence", default="commercial")
    p.add_argument("--element", default="hero_heading")
    p.add_argument("--request", default="make it feel more premium")
    p.add_argument("--since", default="2026-10-18T00:00:00Z")
    a = p.parse_args()

    role = {"curate": "CURATOR", "teammate": "TEAMMATE", "catchup": "CATCHUP"}[a.kind]
    app_id, key = os.getenv(f"CREAO_{role}_APP_ID"), os.getenv(f"CREAO_{role}_KEY")
    if not (app_id and key):
        sys.exit(f"Set CREAO_{role}_APP_ID and CREAO_{role}_KEY in .env")

    inputs = {
        "curate": {"file_slug": "fintech-landing", "spot_key": a.spot, "member_name": a.member,
                   "budget_usd": a.budget, "licence": a.licence},
        "teammate": {"element_key": a.element, "member_name": a.member, "request": a.request},
        "catchup": {"member_name": a.member, "since": a.since},
    }[a.kind]

    base = f"https://agent.creao.ai/api/v1/apps/{app_id}/runs"
    head = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=30) as c:
        r = c.post(base, headers=head, json={"inputs": inputs})
        r.raise_for_status()
        run = r.json()
        print(f"run {run['id']} started ({run.get('appName', role.lower())}) — runs take a few minutes")
        while True:
            time.sleep(10)
            s = c.get(f"{base}/{run['id']}", headers=head).json()
            print("  status:", s.get("status"))
            if s.get("status") in ("completed", "failed", "cancelled"):
                print((s.get("result") or {}).get("text") or s.get("errorCode") or s)
                break


if __name__ == "__main__":
    main()
