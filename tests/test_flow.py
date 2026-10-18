"""End-to-end run of the seven-card flow, offline: mock Strata over ASGI, no LLM, no Stripe."""

import asyncio
import json
import os

import httpx
import pytest

os.environ["ASI1_API_KEY"] = ""
os.environ["STRIPE_SECRET_KEY"] = ""
os.environ["STRATA_DATA_DIR"] = os.path.join(os.path.dirname(__file__), ".data")

from strata_agents import cards, mock_strata, services  # noqa: E402
from strata_agents.bus_local import LocalBus  # noqa: E402
from strata_agents.graph import Command, build_graph, initial_state  # noqa: E402
from strata_agents.strata_client import StrataClient  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_world():
    mock_strata.STATE.clear()
    mock_strata.STATE.update(mock_strata._fresh_state())
    services.strata = StrataClient(base_url="http://mock", transport=httpx.ASGITransport(app=mock_strata.app))
    yield


def _interrupt(result):
    return result["__interrupt__"][0].value


async def _run_flow(licence_reply="commercial", budget="40"):
    graph = build_graph()
    cfg = {"configurable": {"thread_id": "t1", "bus": LocalBus()}}
    seen = []

    r = await graph.ainvoke(initial_state("Find art for our landing page, under $40"), cfg)
    step = _interrupt(r); seen.append(step["kind"])
    assert step["kind"] == "custom"
    grid = [c for c in step["payload"]["root"]["children"] if c["type"] == "choice_grid"][0]
    assert {c["value"] for c in grid["choices"]} == {"hero-art", "feature-icons", "mobile-hero"}
    cards.to_message(step)  # metadata must serialise

    # Planner-style prose reply, not JSON
    r = await graph.ainvoke(Command(resume=cards.parse_reply("User picked spot hero-art via pick_spot")), cfg)
    step = _interrupt(r); seen.append(step["kind"])
    assert step["kind"] == "form"

    r = await graph.ainvoke(Command(resume=cards.parse_reply(json.dumps(
        {"step": "brief", "style": "Flat, two colours", "budget_usd": budget, "licence": "commercial",
         "also_mobile": "true"}))), cfg)
    step = _interrupt(r); seen.append(step["kind"])
    assert step["kind"] == "carousel"
    items = step["payload"]["items"]
    assert items[0]["id"] == "seedling-jar"  # fits both rules, cheapest of the two that do
    assert all(i.get("image", "").endswith(".png") for i in items)
    assert any("Breaks" in b["label"] for i in items for b in i["badges"])

    r = await graph.ainvoke(Command(resume={"step": "choose", "asset": "seedling-jar"}), cfg)
    step = _interrupt(r); seen.append(step["kind"])
    assert step["kind"] == "detail"

    r = await graph.ainvoke(Command(resume={"step": "detail", "action": "add_to_cart", "licence": licence_reply}), cfg)
    step = _interrupt(r); seen.append(step["kind"])
    return graph, cfg, r, step, seen


def test_happy_path_places_and_licenses():
    async def go():
        graph, cfg, r, step, seen = await _run_flow()
        assert step["kind"] == "review"
        r = await graph.ainvoke(Command(resume={"step": "review", "action": "approve"}), cfg)
        pay = _interrupt(r)
        assert pay["type"] == "payment" and pay["payment"]["amount_cents"] == 2400
        r = await graph.ainvoke(Command(resume={"transaction_id": pay["payment"]["checkout_session_id"]}), cfg)
        assert "__interrupt__" not in r and r["done"]
        rc = cards.receipt(r)
        assert rc["kind"] == "custom"
        assert r["receipt"]["spot_ids"] == ["hero-art", "mobile-hero"]
        assert r["receipt"]["next_spot"]["id"] == "feature-icons"
        f = mock_strata.STATE["files"]["fintech-landing"]
        assert f["placements"] == {"hero-art": "seedling-jar", "mobile-hero": "seedling-jar"}
        assert mock_strata.STATE["mandates"]["alex"]["spent_cents"] == 2400
        assert seen == ["custom", "form", "carousel", "detail", "review"]

    asyncio.run(go())


def test_over_mandate_offers_cheaper_licence():
    async def go():
        graph, cfg, r, step, _ = await _run_flow(licence_reply="extended")
        # extended is not allowed for Alex: back to detail with an explanation
        assert step["kind"] == "detail"
        assert "personal" in step["narration"].lower() or "commercial" in step["narration"].lower()
        r = await graph.ainvoke(Command(resume={"step": "detail", "action": "add_to_cart", "licence": "commercial"}), cfg)
        assert _interrupt(r)["kind"] == "review"

    asyncio.run(go())


def test_rejected_payment_returns_to_review_without_charging():
    async def go():
        graph, cfg, r, step, _ = await _run_flow()
        r = await graph.ainvoke(Command(resume={"step": "review", "action": "approve"}), cfg)
        r = await graph.ainvoke(Command(resume={"rejected": True}), cfg)
        assert _interrupt(r)["kind"] == "review"
        assert mock_strata.STATE["mandates"]["alex"]["spent_cents"] == 0

    asyncio.run(go())
