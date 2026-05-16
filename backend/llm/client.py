"""Tiny LLM helper.

If OPENAI_API_KEY is set we call an OpenAI-compatible Chat Completions API.
Otherwise `complete_json` returns None and callers fall back to deterministic
heuristics — so the entire pipeline runs offline.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from ..config import get_settings

log = logging.getLogger(__name__)


async def complete_json(system: str, user: str) -> dict[str, Any] | None:
    s = get_settings()
    if not s.openai_api_key:
        return None
    try:
        from openai import AsyncOpenAI  # type: ignore
    except Exception:
        log.warning("openai SDK not installed")
        return None

    client = AsyncOpenAI(api_key=s.openai_api_key, base_url=s.openai_base_url)
    try:
        resp = await client.chat.completions.create(
            model=s.openai_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        text = resp.choices[0].message.content or "{}"
        return json.loads(text)
    except Exception as e:  # pragma: no cover
        log.warning("LLM call failed: %s", e)
        return None
