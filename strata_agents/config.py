"""Environment-driven settings shared by every agent and the mock Strata API."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def env(name: str, default: str = "") -> str:
    """Like os.getenv, but an empty value in .env falls back to the default."""
    return os.getenv(name) or default


PACKAGE_DIR = Path(__file__).parent
DATA_DIR = Path(env("STRATA_DATA_DIR", PACKAGE_DIR.parent / "data"))
PREVIEW_DIR = DATA_DIR / "previews"


@dataclass(frozen=True)
class Settings:
    # ASI:One is OpenAI-compatible; the planner and curator both use it.
    asi1_api_key: str = os.getenv("ASI_ONE_API_KEY") or env("ASI1_API_KEY", "")
    asi1_base_url: str = env("ASI1_BASE_URL", "https://api.asi1.ai/v1")
    asi1_model: str = env("ASI1_MODEL", "asi1")

    # "mock" = local FastAPI stand-in; "base44" = the live Base44 app's agentApi function.
    strata_backend: str = env("STRATA_BACKEND", "mock")
    base44_app_url: str = env("BASE44_APP_URL", "")  # e.g. https://strata-xyz.base44.app
    base44_app_id: str = env("BASE44_APP_ID", "")
    base44_pat: str = env("BASE44_PAT", "")  # personal access token, only for scripts/seed_base44.py

    # Strata API: the mock server today, the Base44 function URLs later.
    strata_api_url: str = env("STRATA_API_URL", "http://127.0.0.1:8090")
    strata_api_secret: str = env("STRATA_API_SECRET", "dev-secret")
    # Public HTTPS origin that serves preview images to ASI:One cards (a tunnel in dev).
    public_base_url: str = env("PUBLIC_BASE_URL", "http://127.0.0.1:8090")

    stripe_secret_key: str = env("STRIPE_SECRET_KEY", "")
    stripe_publishable_key: str = env("STRIPE_PUBLISHABLE_KEY", "")

    # Demo mapping: the ASI:One user is treated as this Strata member.
    demo_member_id: str = env("STRATA_DEMO_MEMBER", "alex")
    demo_file_id: str = env("STRATA_DEMO_FILE", "fintech-landing")

    # One seed per agent gives each a stable agent1q... address on Agentverse.
    concierge_seed: str = env("CONCIERGE_SEED", "strata concierge dev seed")
    curator_seed: str = env("CURATOR_SEED", "strata curator dev seed")
    renderer_seed: str = env("RENDERER_SEED", "strata renderer dev seed")
    checkout_seed: str = env("CHECKOUT_SEED", "strata checkout dev seed")
    ledger_seed: str = env("LEDGER_SEED", "strata ledger dev seed")


settings = Settings()
