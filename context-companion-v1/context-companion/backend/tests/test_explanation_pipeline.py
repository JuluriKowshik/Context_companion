import asyncio
from pathlib import Path
from uuid import uuid4

from app.config import BUNDLED_CONCEPTS_DIR, Settings
from app.schemas import ExplainRequest
from app.services.classifier import classify
from app.services.explain_service import Services, explain
from app.services.knowledge import ConceptIndex
from app.services.learned_cache import LearnedCache
from app.services.lexical_dictionary import LexicalDictionary
from app.services.providers.base import LLMProvider, LLMResult
from app.services.session_store import SessionStore

LEXICAL = LexicalDictionary("data/wordnet_dictionary.db", "data/nltk_data")

class UsefulProvider(LLMProvider):
    name = "test"

    async def explain(self, current_cue, previous_context, known_concepts):
        return LLMResult(
            useful=True,
            term="Merkle tree",
            normalized_concept="merkle tree",
            aliases=["merkle trees"],
            category="technical",
            explanation="A hash tree that lets systems verify large sets of data efficiently.",
            confidence=0.9,
        )


class FailedProvider(LLMProvider):
    name = "test"

    async def explain(self, current_cue, previous_context, known_concepts):
        return LLMResult(useful=False, error="network unavailable")


def services(provider):
    tmp_path = Path.cwd() / ".test-data" / uuid4().hex
    tmp_path.mkdir(parents=True)
    index = ConceptIndex.from_bundled_dir(BUNDLED_CONCEPTS_DIR)
    return Services(
        Settings(learned_cache_path=str(tmp_path / "learned.db")),
        index,
        LearnedCache(str(tmp_path / "learned.db"), index),
        LEXICAL,
        SessionStore(3600, 1800),
        provider,
    )


def test_classifier_rejects_ordinary_dialogue_and_accepts_domain_term():
    assert not classify("Come here, we need to go.", []).is_candidate
    assert classify("They are shorting the housing market.", []).is_candidate


def test_local_dictionary_answer_precedes_llm():
    result = asyncio.run(explain(
        ExplainRequest(current_subtitle="They are shorting the housing market.", force=True),
        services(FailedProvider()),
    ))
    assert result.useful
    assert result.source == "dictionary"
    assert result.stage == "dictionary"
    assert result.normalized_concept == "short selling"


def test_multiple_local_terms_are_returned_in_subtitle_order():
    result = asyncio.run(explain(
        ExplainRequest(current_subtitle="Liquidity and a liquidity crisis can trigger short selling.", force=True),
        services(FailedProvider()),
    ))
    assert result.useful
    assert 1 <= len(result.items) <= 3
    assert result.items[0].term.lower().startswith("liquidity")
    # Legacy clients retain exactly the first batch item.
    assert result.term == result.items[0].term
    assert result.explanation == result.items[0].explanation


def test_wordnet_fallback_does_not_accept_common_domain_noun_without_contextual_model():
    result = asyncio.run(explain(
        ExplainRequest(current_subtitle="The protocol uses Merkle trees for integrity.", force=True),
        services(FailedProvider()),
    ))
    assert not result.useful
    assert result.stage == "error"


def test_gate_prevents_ordinary_automatic_requests():
    result = asyncio.run(explain(
        ExplainRequest(current_subtitle="Come here, we need to go.", force=False),
        services(UsefulProvider()),
    ))
    assert not result.useful
    assert result.stage == "gate"


def test_unknown_term_uses_llm_and_is_remembered():
    svc = services(UsefulProvider())
    result = asyncio.run(explain(
        ExplainRequest(current_subtitle="The protocol uses Merkle trees for integrity.", force=True), svc,
    ))
    assert result.useful
    assert result.source == "llm"
    assert result.stage == "model"
    assert svc.index.get("merkle tree") is not None


def test_provider_error_is_not_reported_as_no_explanation():
    result = asyncio.run(explain(
        ExplainRequest(current_subtitle="The protocol uses Merkle trees for integrity.", force=True),
        services(FailedProvider()),
    ))
    assert not result.useful
    assert result.stage == "error"
    assert result.error_detail == "network unavailable"
