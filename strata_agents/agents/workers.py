"""Curator, Renderer, Checkout and Ledger: one uAgent each, answering only the Concierge."""

from __future__ import annotations

import json
from pathlib import Path

from uagents import Agent, Context, Protocol
from uagents.crypto import Identity

from .. import services
from ..config import settings
from ..messages import (
    CheckoutRequest,
    CheckoutResponse,
    CurateRequest,
    CurateResponse,
    FileRequest,
    FileResponse,
    FulfilRequest,
    FulfilResponse,
    QuoteRequest,
    QuoteResponse,
    RenderRequest,
    RenderResponse,
    SpotsRequest,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
)
from ..strata_client import StrataError

README_DIR = Path(__file__).parent / "readmes"
CONCIERGE_ADDRESS = Identity.from_seed(settings.concierge_seed, 0).address


def _guard(ctx: Context, sender: str) -> bool:
    """Workers spend money and edit files, so they only take orders from our Concierge."""
    if sender != CONCIERGE_ADDRESS:
        ctx.logger.warning(f"ignoring request from {sender}")
        return False
    return True


PORTS = {"curator": 8002, "renderer": 8003, "checkout": 8004, "ledger": 8005}


def _agent(name: str, seed: str, description: str) -> Agent:
    readme = README_DIR / f"{name}.md"
    return Agent(
        name=f"strata-{name}",
        seed=seed,
        port=PORTS[name],  # used when each agent runs in its own process
        mailbox=True,
        description=description,
        readme_path=str(readme) if readme.exists() else None,
        publish_agent_details=True,
    )


# ---------------------------------------------------------------- Curator

curator = _agent("curator", settings.curator_seed,
                 "Ranks design assets against a team's learned taste rules and explains each fit.")
curate_proto = Protocol(name="StrataCurate", version="0.1.0")


@curate_proto.on_message(CurateRequest, replies={CurateResponse})
async def on_curate(ctx: Context, sender: str, msg: CurateRequest):
    if _guard(ctx, sender):
        await ctx.send(sender, await services.curate(msg))


curator.include(curate_proto, publish_manifest=True)

# ---------------------------------------------------------------- Renderer

renderer = _agent("renderer", settings.renderer_seed,
                  "Draws a team's real design file with a candidate asset in place, as a watermarked preview.")
render_proto = Protocol(name="StrataRender", version="0.1.0")


@render_proto.on_message(RenderRequest, replies={RenderResponse})
async def on_render(ctx: Context, sender: str, msg: RenderRequest):
    if _guard(ctx, sender):
        await ctx.send(sender, await services.render_options(msg))


@render_proto.on_message(SpotsRequest, replies={RenderResponse})
async def on_spots(ctx: Context, sender: str, msg: SpotsRequest):
    if _guard(ctx, sender):
        await ctx.send(sender, await services.render_spots(msg.file_id))


renderer.include(render_proto, publish_manifest=True)

# ---------------------------------------------------------------- Checkout

checkout = _agent("checkout", settings.checkout_seed,
                  "Checks a member's spending mandate, opens Stripe checkout, and verifies payment.")
checkout_proto = Protocol(name="StrataCheckout", version="0.1.0")


@checkout_proto.on_message(QuoteRequest, replies={QuoteResponse})
async def on_quote(ctx: Context, sender: str, msg: QuoteRequest):
    if _guard(ctx, sender):
        await ctx.send(sender, await services.quote(msg))


@checkout_proto.on_message(CheckoutRequest, replies={CheckoutResponse})
async def on_checkout(ctx: Context, sender: str, msg: CheckoutRequest):
    if _guard(ctx, sender):
        await ctx.send(sender, await services.create_checkout(msg))


@checkout_proto.on_message(VerifyPaymentRequest, replies={VerifyPaymentResponse})
async def on_verify(ctx: Context, sender: str, msg: VerifyPaymentRequest):
    if _guard(ctx, sender):
        await ctx.send(sender, await services.verify_payment(msg.checkout_session_id))


checkout.include(checkout_proto, publish_manifest=True)

# ---------------------------------------------------------------- Ledger

ledger = _agent("ledger", settings.ledger_seed,
                "Places licensed assets on a Strata design file and records the licence in its history.")
ledger_proto = Protocol(name="StrataLedger", version="0.1.0")


@ledger_proto.on_message(FileRequest, replies={FileResponse})
async def on_file(ctx: Context, sender: str, msg: FileRequest):
    if not _guard(ctx, sender):
        return
    try:
        f = await services.strata.get_file(msg.file_id)
        await ctx.send(sender, FileResponse(ok=True, file_json=json.dumps(f)))
    except StrataError as exc:
        await ctx.send(sender, FileResponse(ok=False, error=str(exc)))


@ledger_proto.on_message(FulfilRequest, replies={FulfilResponse})
async def on_fulfil(ctx: Context, sender: str, msg: FulfilRequest):
    if _guard(ctx, sender):
        await ctx.send(sender, await services.fulfil(msg))


ledger.include(ledger_proto, publish_manifest=True)

WORKERS = [curator, renderer, checkout, ledger]
