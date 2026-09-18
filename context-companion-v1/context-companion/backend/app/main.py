import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import BUNDLED_CONCEPTS_DIR, get_settings
from .routes.explain import router
from .services.explain_service import Services
from .services.knowledge import ConceptIndex
from .services.learned_cache import LearnedCache
from .services.lexical_dictionary import LexicalDictionary
from .services.providers import get_llm_provider
from .services.session_store import SessionStore

_settings = get_settings()
logging.basicConfig(level=_settings.log_level, format="%(levelname)s %(name)s: %(message)s", force=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One pooled HTTP client for the process. Reusing connections shaves a TLS
    # handshake off every LLM call.
    client = httpx.AsyncClient(timeout=_settings.llm_timeout_seconds)
    index = ConceptIndex.from_bundled_dir(BUNDLED_CONCEPTS_DIR)
    learned = LearnedCache(_settings.learned_cache_path, index)
    lexical = LexicalDictionary(_settings.lexical_dictionary_path, _settings.nltk_data_path)
    app.state.services = Services(
        settings=_settings,
        index=index,
        learned=learned,
        lexical=lexical,
        sessions=SessionStore(_settings.session_ttl_seconds, _settings.recent_concept_ttl_seconds),
        provider=get_llm_provider(_settings, client),
    )
    logging.getLogger(__name__).info("Provider: %s", app.state.services.provider.name)
    yield
    await client.aclose()


app = FastAPI(title="Context Companion", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type"],
)

app.include_router(router)
