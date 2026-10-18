"""Reset the Tally team and pre-run the real CREAO agent so the demo opens with fresh AI results.

    uv run python demo/server.py            # in one terminal
    uv run python scripts/prepare_demo.py   # in another, ~1-2 min

Pre-runs: Alex's shortlists for the hero illustration and footer icons, and Priya's catch-up. The heading conflict is left for
you to run live on camera. On success the state is saved to demo/demo_snapshot.json (real CREAO results);
if a venue network blocks CREAO later, `prepare_demo.py --restore` brings that state back instantly.
"""

from __future__ import annotations

import sys
import time

import httpx

BASE = "http://localhost:8044"


def main() -> None:
    c = httpx.Client(base_url=BASE, timeout=30)
    if "--restore" in sys.argv:
        r = c.post("/api/snapshot/restore")
        sys.exit(r.json().get("detail") if r.status_code >= 400 else "Restored the last prepared demo (real CREAO results).")
    try:
        modes = c.get("/api/state").json()["modes"]
    except httpx.HTTPError:
        sys.exit("Start the app first: uv run python demo/server.py")
    if set(modes.values()) != {"creao"}:
        sys.exit(f"Not every job is on CREAO yet: {modes}. Check CREAO_STRATA_APP_ID / CREAO_STRATA_KEY in .env.")
    c.post("/api/reset").raise_for_status()
    print("Reset the Tally team.")
    jobs = [
        ("curate", {"member": "Alex", "spot_key": "hero_illustration", "licence": "commercial",
                    "budget_cents": 4000, "request": "Art for the hero: something about saving that grows"}),
        ("curate", {"member": "Alex", "spot_key": "footer_icons", "licence": "commercial",
                    "budget_cents": 4000, "request": "Small app-store icons for the footer"}),
        ("catchup", {"member": "Priya"}),
    ]
    for kind, body in jobs:
        r = c.post(f"/api/agents/{kind}", json=body)
        r.raise_for_status()
        print(f"Started CREAO {kind} run for {body['member']}.")
    t0 = time.time()
    while True:
        time.sleep(5)
        runs = c.get("/api/state").json()["runs"]
        live = [r for r in runs if r["status"] in ("queued", "running")]
        print(f"  {int(time.time() - t0)}s · {len(live)} still running")
        if not live:
            break
        if time.time() - t0 > 480:
            sys.exit("CREAO is taking too long; try again.")
    failed = [r for r in runs if r["status"] == "failed"]
    for r in runs:
        print(f"{r['kind']:8} {r['status']:9} run {r['run_id']} · {r['message'][:90]}")
    if failed:
        sys.exit(f"Some runs failed ({failed[0]['message']}). If CREAO is unreachable, switch networks and retry, "
                 "or use --restore.")
    c.post("/api/snapshot/save").raise_for_status()
    print("\nReady. Open http://localhost:8044 and follow the demo script.")


if __name__ == "__main__":
    main()
