"""Central configuration, loaded from .env in the working directory."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

APP_DIR = Path(__file__).resolve().parent
BUNDLED_CONCEPTS_DIR = APP_DIR / "data" / "concepts"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "groq"  # gemini | groq | grok | mock

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    gemini_thinking_level: str = "minimal"

    groq_api_key: str = ""
    groq_model: str = "groq/compound"

    grok_api_key: str = ""
    grok_model: str = "grok-4.1-fast-non-reasoning"

    llm_timeout_seconds: float = 6.0
    llm_max_output_tokens: int = 300

    context_window_size: int = 3
    max_subtitle_chars: int = 400

    candidate_min_score: float = 0.6
    zipf_rare_threshold: float = 4.0
    zipf_borderline_threshold: float = 4.5
    lexical_validity_required: bool = True
    max_candidate_terms_per_cue: int = 3
    max_cards_per_cue: int = 3

    learned_cache_path: str = "data/learned_concepts.db"
    lexical_dictionary_path: str = "data/wordnet_dictionary.db"
    nltk_data_path: str = "data/nltk_data"
    session_ttl_seconds: int = 3 * 60 * 60

    # Automatic display policy. The extension fetches these from GET /config.
    prefetch_window_seconds: float = 6.0
    auto_show_confidence: float = 0.85
    auto_hint_cooldown_seconds: float = 8.0
    max_hints_per_minute: int = 4
    # A concept shown in any video is not shown again for this long.
    recent_concept_ttl_seconds: int = 30 * 60
    # How long after a cue ends a late result may still be displayed.
    late_display_grace_seconds: float = 2.5
    card_lifetime_seconds: float = 5.0
    max_card_queue_size: int = 12

    cors_origins: list[str] = ["*"]
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
