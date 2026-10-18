"""Messages the five agents exchange. Each request has exactly one response type."""

from uagents import Model


class CurateRequest(Model):
    file_id: str
    team_id: str
    member_id: str
    kind: str  # "illustration" | "icon-set"
    budget_cents: int | None = None
    licence: str = "commercial"
    limit: int = 4


class CuratedAsset(Model):
    asset_id: str
    title: str
    creator: str
    price_cents: int
    score: float
    fits: list[str]
    breaks: list[str]
    members: list[str]
    why: str


class CurateResponse(Model):
    ok: bool
    assets: list[CuratedAsset] = []
    error: str | None = None


class RenderRequest(Model):
    file_id: str
    spot_id: str
    asset_ids: list[str]
    watermark: bool = True


class RenderedImage(Model):
    asset_id: str
    url: str


class RenderResponse(Model):
    ok: bool
    images: list[RenderedImage] = []
    frame_url: str | None = None
    spot_tiles: dict[str, str] = {}
    error: str | None = None


class SpotsRequest(Model):
    file_id: str


class FileRequest(Model):
    file_id: str


class FileResponse(Model):
    ok: bool
    file_json: str = "{}"
    error: str | None = None


class QuoteRequest(Model):
    member_id: str
    asset_id: str
    licence: str


class QuoteResponse(Model):
    ok: bool
    within_mandate: bool = False
    amount_cents: int = 0
    remaining_after_cents: int = 0
    limit_cents: int = 0
    reason: str | None = None
    cheaper_licence: str | None = None
    cheaper_amount_cents: int | None = None


class CheckoutRequest(Model):
    member_id: str
    asset_id: str
    licence: str
    amount_cents: int
    reference: str
    description: str


class CheckoutResponse(Model):
    ok: bool
    checkout_session_id: str | None = None
    client_secret: str | None = None
    publishable_key: str | None = None
    checkout_url: str | None = None
    link_session_id: str | None = None  # hosted-page fallback session, verified the same way
    error: str | None = None


class VerifyPaymentRequest(Model):
    checkout_session_id: str


class VerifyPaymentResponse(Model):
    paid: bool
    status: str
    error: str | None = None


class FulfilRequest(Model):
    file_id: str
    member_id: str
    asset_id: str
    licence: str
    spot_ids: list[str]
    amount_cents: int
    payment_ref: str


class FulfilResponse(Model):
    ok: bool
    licence_id: str | None = None
    final_image_url: str | None = None
    error: str | None = None
