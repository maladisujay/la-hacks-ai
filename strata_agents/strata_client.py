"""Async client for the Strata backend with timeouts and retries on transient failures.

Two backends, same methods:
- mock:   the local FastAPI app (strata_agents/mock_strata.py), REST routes
- base44: the live Base44 app, one function `agentApi` with an `action` field
"""

from __future__ import annotations

import asyncio
import base64
from typing import Any

import httpx

from .config import settings

RETRYABLE = {429, 500, 502, 503, 504}


class StrataError(RuntimeError):
    pass


class StrataClient:
    def __init__(self, base_url: str | None = None, secret: str | None = None, attempts: int = 3,
                 transport: httpx.AsyncBaseTransport | None = None, backend: str | None = None):
        self.backend = backend or settings.strata_backend
        default = settings.base44_app_url if self.backend == "base44" else settings.strata_api_url
        self.base_url = (base_url or default).rstrip("/")
        self.secret = secret or settings.strata_api_secret
        self.attempts = attempts
        self.transport = transport  # tests pass an ASGI transport to the mock app

    # ------------------------------------------------------------ transport

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        delay = 0.5
        last: Exception | None = None
        headers = {"X-Strata-Secret": self.secret}
        for attempt in range(self.attempts):
            try:
                async with httpx.AsyncClient(timeout=20, transport=self.transport) as client:
                    resp = await client.request(method, self.base_url + path, headers=headers, **kwargs)
            except httpx.TransportError as exc:
                last = exc
            else:
                if resp.status_code not in RETRYABLE:
                    if resp.status_code >= 400:
                        raise StrataError(f"{resp.status_code}: {resp.text[:200]}")
                    return resp.json()
                last = StrataError(f"{resp.status_code} from Strata")
            if attempt + 1 < self.attempts:
                await asyncio.sleep(delay)
                delay *= 2
        raise StrataError(f"Strata unavailable after {self.attempts} tries: {last}")

    async def _action(self, action: str, **params) -> Any:
        return await self._request("POST", "/functions/agentApi", json={"action": action, **params})

    # ------------------------------------------------------------ Base44 → graph shapes

    @staticmethod
    def _file(rec: dict) -> dict:
        return {**rec, "id": rec.get("slug", rec.get("id")), "team_id": rec.get("team_slug", rec.get("team_id")),
                "placements": rec.get("placements") or {}, "spots": rec.get("spots") or []}

    @staticmethod
    def _rule(rec: dict) -> dict:
        return {**rec, "id": rec.get("rule_key", rec.get("id")), "requires": rec.get("requires") or {},
                "members": rec.get("members") or [], "kept": rec.get("kept", 0), "undone": rec.get("undone", 0)}

    @staticmethod
    def _asset(rec: dict) -> dict:
        return {**rec, "id": rec.get("asset_id", rec.get("id"))}

    # ------------------------------------------------------------ API

    async def get_file(self, file_id: str) -> dict:
        if self.backend == "base44":
            return self._file(await self._action("getFile", file_id=file_id))
        return await self._request("GET", f"/files/{file_id}")

    async def get_rules(self, team_id: str) -> list[dict]:
        if self.backend == "base44":
            return [self._rule(r) for r in await self._action("getRules", team_id=team_id)]
        return await self._request("GET", f"/teams/{team_id}/rules")

    async def get_catalog(self, kind: str | None = None) -> list[dict]:
        if self.backend == "base44":
            return [self._asset(a) for a in await self._action("getCatalog", kind=kind)]
        return await self._request("GET", "/catalog", params={"kind": kind} if kind else None)

    async def get_mandate(self, member_id: str) -> dict:
        if self.backend == "base44":
            return await self._action("getMandate", member_id=member_id)
        return await self._request("GET", f"/mandates/{member_id}")

    async def fulfil(self, file_id: str, body: dict) -> dict:
        if self.backend == "base44":
            return await self._action("fulfil", file_id=file_id, **body)
        return await self._request("POST", f"/files/{file_id}/fulfil", json=body)

    async def upload_preview(self, name: str, png: bytes) -> str | None:
        """Base44 only: returns a permanent public URL for an ASI:One card image."""
        if self.backend != "base44":
            return None
        res = await self._action("uploadPreview", name=name, png_b64=base64.b64encode(png).decode())
        return res.get("url")
