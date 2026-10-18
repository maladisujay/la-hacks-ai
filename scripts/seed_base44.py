"""Load the demo world (team rules, catalog, mandates, the Fintech landing file) into the Base44 app.

Needs in .env: BASE44_APP_ID and BASE44_PAT (a personal access token with Full access to this app).

    uv run python scripts/seed_base44.py           # create records that don't exist yet
    uv run python scripts/seed_base44.py --wipe    # delete Strata demo records first
"""

from __future__ import annotations

import argparse
import sys

import httpx

sys.path.insert(0, ".")
from strata_agents import seed  # noqa: E402
from strata_agents.config import settings  # noqa: E402

API = f"https://app.base44.com/api/apps/{settings.base44_app_id}/entities"
HEAD = {"Authorization": f"Bearer {settings.base44_pat}", "Content-Type": "application/json"}


def existing(client: httpx.Client, entity: str, field: str) -> set:
    r = client.get(f"{API}/{entity}", headers=HEAD, params={"limit": 5000})
    r.raise_for_status()
    return {row.get(field) for row in r.json()}


def wipe(client: httpx.Client, entity: str) -> None:
    r = client.get(f"{API}/{entity}", headers=HEAD, params={"limit": 5000})
    r.raise_for_status()
    for row in r.json():
        client.delete(f"{API}/{entity}/{row['id']}", headers=HEAD).raise_for_status()


def create(client: httpx.Client, entity: str, data: dict) -> None:
    client.post(f"{API}/{entity}", headers=HEAD, json=data).raise_for_status()


def main() -> None:
    if not (settings.base44_app_id and settings.base44_pat):
        sys.exit("Set BASE44_APP_ID and BASE44_PAT in .env first.")
    parser = argparse.ArgumentParser()
    parser.add_argument("--wipe", action="store_true")
    args = parser.parse_args()

    with httpx.Client(timeout=30) as c:
        if args.wipe:
            for entity in ("Licence", "HistoryAtom", "Mandate", "TasteRule", "Asset", "DesignFile"):
                wipe(c, entity)
            print("wiped")

        have = existing(c, "DesignFile", "slug")
        for f in seed.FILES.values():
            if f["id"] not in have:
                create(c, "DesignFile", {"slug": f["id"], "name": f["name"], "team_slug": f["team_id"],
                                         "heading": f["heading"], "frames": f["frames"], "spots": f["spots"],
                                         "placements": f["placements"]})
        have = existing(c, "TasteRule", "rule_key")
        for r in seed.RULES:
            if r["id"] not in have:
                create(c, "TasteRule", {"team_slug": seed.TEAM["id"], "rule_key": r["id"], "text": r["text"],
                                        "scope": r["scope"], "applies_to": r["applies_to"], "requires": r["requires"],
                                        "members": r["members"], "kept": r["kept"], "undone": r["undone"],
                                        "pinned": r["id"] == "r-navy"})
        have = existing(c, "Asset", "asset_id")
        for a in seed.CATALOG:
            if a["id"] not in have:
                create(c, "Asset", {"asset_id": a["id"], **{k: v for k, v in a.items() if k != "id"}})
        have = existing(c, "Mandate", "member_id")
        for m in seed.MANDATES.values():
            if m["member_id"] not in have:
                create(c, "Mandate", m)
    print("seeded: 1 file, %d rules, %d assets, %d mandates" % (len(seed.RULES), len(seed.CATALOG), len(seed.MANDATES)))


if __name__ == "__main__":
    main()
