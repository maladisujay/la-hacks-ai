"""What each worker agent actually does. Agents wrap these; tests call them directly."""

from __future__ import annotations

import asyncio
import uuid

from . import render, seed, taste
from .config import settings
from .llm import ask_text
from .messages import (
    CheckoutRequest,
    CheckoutResponse,
    CuratedAsset,
    CurateRequest,
    CurateResponse,
    FulfilRequest,
    FulfilResponse,
    QuoteRequest,
    QuoteResponse,
    RenderedImage,
    RenderRequest,
    RenderResponse,
    VerifyPaymentResponse,
)
from .strata_client import StrataClient, StrataError

strata = StrataClient()


def _url(name: str) -> str:
    return f"{settings.public_base_url.rstrip('/')}/previews/{name}"


_published: dict[str, str] = {}


async def publish(img, stem: str) -> str:
    """Save a render and return a URL ASI:One can load: Base44 storage when live, local otherwise."""
    name = await asyncio.to_thread(render.save_png, img, stem)
    if name in _published:
        return _published[name]
    url = None
    if settings.strata_backend == "base44":
        from .config import PREVIEW_DIR

        png = (PREVIEW_DIR / name).read_bytes()
        try:
            url = await strata.upload_preview(name, png)
        except StrataError:
            url = None  # fall back to the local URL; the card still renders its text
    url = url or _url(name)
    _published[name] = url
    return url


def _asset(asset_id: str) -> dict:
    for a in seed.CATALOG:
        if a["id"] == asset_id:
            return a
    raise KeyError(asset_id)


# ---------------------------------------------------------------- Curator


async def curate(req: CurateRequest) -> CurateResponse:
    try:
        rules, catalog = await asyncio.gather(strata.get_rules(req.team_id), strata.get_catalog(req.kind))
    except StrataError as exc:
        return CurateResponse(ok=False, error=str(exc))
    ranked = taste.rank(catalog, req.kind, rules, req.member_id, req.budget_cents, req.licence, req.limit)
    by_id = {a["id"]: a for a in catalog}
    names = {k: v["name"] for k, v in seed.TEAM["members"].items()}

    async def explain(fit: taste.Fit) -> CuratedAsset:
        a = by_id[fit.asset_id]
        who = " and ".join(names.get(m, m) for m in fit.members) or "the team"
        if fit.breaks:
            fallback = f"Breaks: {', '.join(fit.breaks)}."
        elif fit.fits:
            fallback = f"Fits {len(fit.fits)} team rule{'s' if len(fit.fits) > 1 else ''} taught by {who}."
        else:
            fallback = "No team rule applies to it yet."
        why = await ask_text(
            "You write one short, plain sentence (max 16 words) explaining why a design asset does or "
            "does not fit a design team's learned rules. No marketing language.",
            f"Asset: {a['title']} ({a['style']}, {a['colours']} colours, palette {a['palette']}). "
            f"Fits: {fit.fits}. Breaks: {fit.breaks}. Rules taught by: {who}.",
            fallback,
        )
        return CuratedAsset(
            asset_id=a["id"], title=a["title"], creator=a["creator"],
            price_cents=a["prices"][req.licence], score=round(fit.score, 3),
            fits=fit.fits, breaks=fit.breaks, members=fit.members, why=why[:160],
        )

    assets = await asyncio.gather(*(explain(f) for f in ranked))
    return CurateResponse(ok=True, assets=list(assets))


# ---------------------------------------------------------------- Renderer


async def render_options(req: RenderRequest) -> RenderResponse:
    try:
        f = await strata.get_file(req.file_id)
    except StrataError as exc:
        return RenderResponse(ok=False, error=str(exc))

    def draw(asset_id: str):
        if req.spot_id == "mobile-hero":
            return render.render_mobile(f["heading"], asset_id, watermark=req.watermark)
        return render.render_frame(f["heading"], f["placements"], try_on=(req.spot_id, asset_id))

    async def one(asset_id: str) -> RenderedImage:
        img = await asyncio.to_thread(draw, asset_id)
        return RenderedImage(asset_id=asset_id, url=await publish(img, f"tryon-{asset_id}"))

    images = await asyncio.gather(*(one(a) for a in req.asset_ids))
    return RenderResponse(ok=True, images=list(images))


async def render_spots(file_id: str) -> RenderResponse:
    try:
        f = await strata.get_file(file_id)
    except StrataError as exc:
        return RenderResponse(ok=False, error=str(exc))

    frame = await asyncio.to_thread(render.render_frame, f["heading"], f["placements"])
    tiles = {}
    for spot in f["spots"]:
        tile = await asyncio.to_thread(render.render_spot_tile, spot["id"], f["heading"], f["placements"])
        tiles[spot["id"]] = await publish(tile, f"tile-{spot['id']}")
    return RenderResponse(ok=True, frame_url=await publish(frame, "frame"), spot_tiles=tiles)


# ---------------------------------------------------------------- Checkout


async def quote(req: QuoteRequest) -> QuoteResponse:
    try:
        mandate = await strata.get_mandate(req.member_id)
    except StrataError as exc:
        return QuoteResponse(ok=False, reason=str(exc))
    asset = _asset(req.asset_id)
    amount = asset["prices"].get(req.licence)
    if amount is None:
        return QuoteResponse(ok=False, reason=f"No {req.licence} licence for this asset")
    remaining = mandate["limit_cents"] - mandate["spent_cents"]
    allowed = req.licence in mandate["allowed_licences"]
    within = allowed and amount <= remaining
    resp = QuoteResponse(
        ok=True, within_mandate=within, amount_cents=amount,
        remaining_after_cents=remaining - amount, limit_cents=mandate["limit_cents"],
    )
    if not within:
        resp.reason = (
            f"{req.licence.title()} licences need the lead's approval" if not allowed
            else f"${amount / 100:.2f} is more than the ${remaining / 100:.2f} left this month"
        )
        for lic in ("commercial", "personal"):
            price = asset["prices"].get(lic)
            if lic in mandate["allowed_licences"] and price is not None and price <= remaining and lic != req.licence:
                resp.cheaper_licence, resp.cheaper_amount_cents = lic, price
                break
    return resp


async def create_checkout(req: CheckoutRequest) -> CheckoutResponse:
    if not settings.stripe_secret_key:
        # Demo-safe simulation, clearly labelled; never used once a test key is configured.
        return CheckoutResponse(ok=True, checkout_session_id=f"cs_sim_{uuid.uuid4().hex[:12]}")
    import stripe

    stripe.api_key = settings.stripe_secret_key
    params = dict(
        mode="payment",
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "usd",
                "product_data": {"name": req.description},
                "unit_amount": req.amount_cents,
            },
            "quantity": 1,
        }],
        redirect_on_completion="if_required",
        return_url=f"{settings.public_base_url}/paid?session_id={{CHECKOUT_SESSION_ID}}",
        metadata={"reference": req.reference, "member_id": req.member_id, "asset_id": req.asset_id},
    )
    try:
        try:
            session = await asyncio.to_thread(stripe.checkout.Session.create, ui_mode="embedded_page", **params)
        except stripe.InvalidRequestError:  # older Stripe API versions call it "embedded"
            session = await asyncio.to_thread(stripe.checkout.Session.create, ui_mode="embedded", **params)
        link = await asyncio.to_thread(
            stripe.checkout.Session.create,
            mode="payment",
            line_items=params["line_items"],
            success_url=f"{settings.public_base_url}/paid",
            metadata=params["metadata"],
        )
    except Exception as exc:  # stripe errors, network
        return CheckoutResponse(ok=False, error=f"Stripe: {exc}")
    return CheckoutResponse(
        ok=True,
        checkout_session_id=session.id,
        client_secret=session.client_secret,
        publishable_key=settings.stripe_publishable_key,
        checkout_url=link.url,
        link_session_id=link.id,
    )


async def verify_payment(checkout_session_id: str) -> VerifyPaymentResponse:
    if checkout_session_id.startswith("cs_sim_"):
        return VerifyPaymentResponse(paid=True, status="simulated")
    import stripe

    stripe.api_key = settings.stripe_secret_key
    try:
        s = await asyncio.to_thread(stripe.checkout.Session.retrieve, checkout_session_id)
    except Exception as exc:
        return VerifyPaymentResponse(paid=False, status="error", error=str(exc))
    return VerifyPaymentResponse(paid=s.payment_status == "paid", status=str(s.payment_status))


# ---------------------------------------------------------------- Ledger


async def fulfil(req: FulfilRequest) -> FulfilResponse:
    try:
        record = await strata.fulfil(req.file_id, {
            "member_id": req.member_id, "asset_id": req.asset_id, "licence": req.licence,
            "spot_ids": req.spot_ids, "amount_cents": req.amount_cents, "payment_ref": req.payment_ref,
        })
        f = await strata.get_file(req.file_id)
    except StrataError as exc:
        return FulfilResponse(ok=False, error=str(exc))
    img = await asyncio.to_thread(render.render_frame, f["heading"], f["placements"])
    return FulfilResponse(ok=True, licence_id=record["licence_id"], final_image_url=await publish(img, "placed"))
