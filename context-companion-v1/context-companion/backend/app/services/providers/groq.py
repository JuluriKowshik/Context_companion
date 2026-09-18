"""Groq provider using the OpenAI-compatible chat completions API."""
import logging

import httpx

from ...config import Settings
from .base import LLMProvider, LLMResult, parse_llm_json
from .prompts import SYSTEM_PROMPT, build_user_prompt

log = logging.getLogger(__name__)

_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider(LLMProvider):
    name = "groq"

    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self._key = settings.groq_api_key
        self._max_tokens = settings.llm_max_output_tokens
        self._client = client
        self._models = self._candidate_models(settings.groq_model)

    @staticmethod
    def _candidate_models(primary: str) -> list[str]:
        fallback = [
            "groq/compound",
            "groq/compound-mini",
            "qwen/qwen3.8-27b",
        ]
        seen = set()
        out = []
        for model in [primary, *fallback]:
            if model and model not in seen:
                out.append(model)
                seen.add(model)
        return out

    async def explain(self, current_cue: str, previous_context: str, known_concepts: list[str]) -> LLMResult:
        last_error = None
        for model in self._models:
            payload = {
                "model": model,
                "temperature": 0.2,
                "max_tokens": self._max_tokens,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(current_cue, previous_context, known_concepts)},
                ],
            }
            try:
                resp = await self._client.post(
                    _ENDPOINT,
                    headers={
                        "Authorization": f"Bearer {self._key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            except httpx.HTTPError as exc:
                log.error("Groq request failed with %s for model %s", exc, model)
                last_error = f"network: {exc}"
                continue

            if resp.status_code == 200:
                try:
                    text = resp.json()["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError, ValueError):
                    log.warning("Unexpected Groq response shape for %s: %s", model, resp.text[:300])
                    return LLMResult(useful=False, error="unexpected_response_shape")
                return parse_llm_json(text)

            detail = f"HTTP {resp.status_code} from Groq with model {model}: {resp.text[:300]}"
            last_error = detail
            # Only a missing/retired model merits trying a fallback. Retrying
            # an invalid request or credential against four models wastes API
            # calls and can turn one user action into a rate-limit burst.
            if resp.status_code == 404:
                log.warning("Groq model %s unavailable: %s", model, detail)
                continue
            if resp.status_code in {400, 401, 403}:
                log.warning("Groq request rejected: %s", detail)
                return LLMResult(useful=False, error=detail)
            log.error(detail)
            return LLMResult(useful=False, error=detail)

        return LLMResult(useful=False, error=last_error or "Groq model unavailable")
