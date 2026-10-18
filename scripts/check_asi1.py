"""Check the ASI:One key in .env: one intent extraction and one fit explanation.

    uv run python scripts/check_asi1.py
"""

import asyncio
import sys

sys.path.insert(0, ".")
from strata_agents.config import settings  # noqa: E402
from strata_agents.graph import understand  # noqa: E402
from strata_agents.llm import ask_text  # noqa: E402


async def main() -> None:
    if not settings.asi1_api_key:
        print("No ASI_ONE_API_KEY in .env")
        return
    print("model:", settings.asi1_model)
    print("intent:", await understand({"user_text": "Find art for our landing page hero, under $40"}))
    print("why:", await ask_text(
        "One plain sentence, max 16 words, on why a design asset fits a team's rules.",
        "Seedling jar: flat, 2 colours, navy and sage. Team rules: flat two-colour illustration; navy kept.",
        "(model call failed, fallback used)",
    ))


asyncio.run(main())
