"""Grok (xAI) via its OpenAI-compatible chat completions endpoint.

Default model is the non-reasoning variant: a definition does not need a
chain of thought, and reasoning adds seconds.
"""
import logging

import httpx

from ...config import Settings
from .base import LLMProvider, LLMResult, parse_llm_json
from .prompts import SYSTEM_PROMPT, build_user_prompt

log = logging.getLogger(__name__)

_ENDPOINT = "https://api.x.ai/v1/chat/completions"


class GrokProvider(LLMProvider):
    name = "grok"

    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self._model = settings.grok_model
        self._key = settings.grok_api_key
        self._max_tokens = settings.llm_max_output_tokens
        self._client = client

    async def explain(self, current_cue: str, previous_context: str, known_concepts: list[str]) -> LLMResult:
        payload = {
            "model": self._model,
            "temperature": 0.2,
            "max_tokens": self._max_tokens,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_user_prompt(current_cue, previous_context, known_concepts)},
            ],
        }
        try:
            resp = await self._client.post(_ENDPOINT, headers={"Authorization": f"Bearer {self._key}"}, json=payload)
        except httpx.HTTPError as exc:
            log.error("Grok request failed: %s", exc)
            return LLMResult(useful=False, error=f"network: {exc}")

        if resp.status_code != 200:
            detail = f"HTTP {resp.status_code} from Grok: {resp.text[:300]}"
            log.error(detail)
            return LLMResult(useful=False, error=detail)

        try:
            text = resp.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError):
            log.warning("Unexpected Grok response shape: %s", resp.text[:300])
            return LLMResult(useful=False, error="unexpected_response_shape")
        return parse_llm_json(text)
