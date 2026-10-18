"""In-process Bus: calls the services directly. Used by tests and by `--single-process` runs."""

from __future__ import annotations

from . import services
from .messages import (
    CheckoutRequest,
    CurateRequest,
    FulfilRequest,
    QuoteRequest,
    RenderRequest,
)


class LocalBus:
    async def get_file(self, file_id: str) -> dict:
        return await services.strata.get_file(file_id)

    async def spots(self, file_id: str):
        return await services.render_spots(file_id)

    async def curate(self, req: CurateRequest):
        return await services.curate(req)

    async def render(self, req: RenderRequest):
        return await services.render_options(req)

    async def quote(self, req: QuoteRequest):
        return await services.quote(req)

    async def checkout(self, req: CheckoutRequest):
        return await services.create_checkout(req)

    async def verify(self, checkout_session_id: str):
        return await services.verify_payment(checkout_session_id)

    async def fulfil(self, req: FulfilRequest):
        return await services.fulfil(req)
