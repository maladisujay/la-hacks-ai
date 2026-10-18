"""First-hour checks against the live Base44 app (run after publishing agentApi and seeding).

Checks: function reachable and secret enforced, cold vs warm latency, file shape, a ~270 KB
base64 PNG upload (body-size limit), and that the returned image URL is public.

    uv run python scripts/check_base44.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

import httpx

sys.path.insert(0, ".")
from strata_agents.config import settings  # noqa: E402
from strata_agents.strata_client import StrataClient, StrataError  # noqa: E402


async def main() -> None:
    if not settings.base44_app_url:
        sys.exit("Set BASE44_APP_URL (https://<app>.base44.app) in .env")
    client = StrataClient(backend="base44")

    async with httpx.AsyncClient(timeout=20) as h:
        r = await h.post(f"{client.base_url}/functions/agentApi", json={"action": "getFile", "file_id": "x"})
        print("no secret →", r.status_code, "(expect 401)")

    for label in ("cold", "warm"):
        t = time.perf_counter()
        try:
            f = await client.get_file(settings.demo_file_id)
            print(f"getFile {label}: {time.perf_counter() - t:.2f}s · spots={[s['id'] for s in f['spots']]}")
        except StrataError as exc:
            print(f"getFile {label} failed: {exc}")
            return

    rules = await client.get_rules(f["team_id"])
    cat = await client.get_catalog("illustration")
    mandate = await client.get_mandate(settings.demo_member_id)
    print(f"rules={len(rules)} illustrations={len(cat)} mandate=${mandate['limit_cents'] / 100:.0f}")

    png = os.urandom(200_000)  # ~270 KB once base64-encoded; content doesn't matter for the size test
    t = time.perf_counter()
    try:
        url = await client.upload_preview("size-check.png", png)
        print(f"upload ~270KB: {time.perf_counter() - t:.2f}s → {url}")
        async with httpx.AsyncClient(timeout=20) as h:
            r = await h.get(url)
        print("image URL public:", r.status_code == 200, r.status_code)
    except StrataError as exc:
        print("upload failed (body limit?):", exc)


asyncio.run(main())
