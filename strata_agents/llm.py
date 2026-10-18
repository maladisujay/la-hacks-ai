"""ASI:One chat model through its OpenAI-compatible API, with a JSON helper that never throws."""

from __future__ import annotations

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .config import settings


def get_llm(temperature: float = 0.2) -> ChatOpenAI | None:
    if not settings.asi1_api_key:
        return None
    return ChatOpenAI(
        model=settings.asi1_model,
        base_url=settings.asi1_base_url,
        api_key=settings.asi1_api_key,
        temperature=temperature,
        timeout=20,
        max_retries=2,
    )


def _first_json_object(text: str) -> dict | None:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        value = json.loads(match.group(0))
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        return None


async def ask_json(system: str, user: str) -> dict | None:
    """Ask ASI:One for a JSON object. Returns None on any failure so callers can fall back."""
    llm = get_llm()
    if llm is None:
        return None
    try:
        reply = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
        return _first_json_object(str(reply.content))
    except Exception:  # network, auth, rate limit: the caller has a deterministic fallback
        return None


async def ask_text(system: str, user: str, fallback: str) -> str:
    llm = get_llm(temperature=0.4)
    if llm is None:
        return fallback
    try:
        reply = await llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)])
        text = str(reply.content).strip()
        return text or fallback
    except Exception:
        return fallback
