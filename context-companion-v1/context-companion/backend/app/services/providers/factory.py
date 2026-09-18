import logging

import httpx

from ...config import Settings
from .base import LLMProvider
from .mock import MockProvider

log = logging.getLogger(__name__)


def get_llm_provider(settings: Settings, client: httpx.AsyncClient) -> LLMProvider:
    name = settings.llm_provider.lower().strip()
    if name == "gemini":
        if settings.gemini_api_key:
            from .gemini import GeminiProvider
            return GeminiProvider(settings, client)
        log.warning("LLM_PROVIDER=gemini but GEMINI_API_KEY is empty. Using MockProvider.")
    elif name == "groq":
        if settings.groq_api_key:
            from .groq import GroqProvider
            return GroqProvider(settings, client)
        log.warning("LLM_PROVIDER=groq but GROQ_API_KEY is empty. Using MockProvider.")
    elif name == "grok":
        if settings.grok_api_key:
            from .grok import GrokProvider
            return GrokProvider(settings, client)
        log.warning("LLM_PROVIDER=grok but GROK_API_KEY is empty. Using MockProvider.")
    elif name != "mock":
        log.warning("Unknown LLM_PROVIDER=%r. Using MockProvider.", name)
    return MockProvider()
