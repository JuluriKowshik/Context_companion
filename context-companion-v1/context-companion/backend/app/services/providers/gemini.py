"""Gemini via REST. Only file that knows Gemini's wire format.

Latency note: Gemini 3 models think before answering and default to a high
thinking level. For a 20-word definition that is pure delay, so we set the
level explicitly (default: minimal).
"""
import logging

import httpx

from ...config import Settings
from .base import LLMProvider, LLMResult, parse_llm_json
from .prompts import SYSTEM_PROMPT, build_user_prompt

log = logging.getLogger(__name__)

_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self._url = _ENDPOINT.format(model=settings.gemini_model)
        self._key = settings.gemini_api_key
        self._thinking_level = settings.gemini_thinking_level
        self._max_tokens = settings.llm_max_output_tokens
        self._client = client

    async def explain(self, current_cue: str, previous_context: str, known_concepts: list[str]) -> LLMResult:
        generation_config: dict = {
            "temperature": 0.2,
            "maxOutputTokens": self._max_tokens,
            "responseMimeType": "application/json",
        }
        if self._thinking_level:
            generation_config["thinkingConfig"] = {"thinkingLevel": self._thinking_level}

        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": build_user_prompt(current_cue, previous_context, known_concepts)}]}],
            "generationConfig": generation_config,
        }
        try:
            resp = await self._client.post(self._url, headers={"x-goog-api-key": self._key}, json=payload)
        except httpx.HTTPError as exc:
            log.error("Gemini request failed: %s", exc)
            return LLMResult(useful=False, error=f"network: {exc}")

        if resp.status_code != 200:
            detail = f"HTTP {resp.status_code} from Gemini: {resp.text[:300]}"
            log.error(detail)
            return LLMResult(useful=False, error=detail)

        try:
            text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError, ValueError):
            log.warning("Unexpected Gemini response shape: %s", resp.text[:300])
            return LLMResult(useful=False, error="unexpected_response_shape")
        return parse_llm_json(text)
