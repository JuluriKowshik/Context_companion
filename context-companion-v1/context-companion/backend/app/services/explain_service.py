"""One /explain request, start to finish.

    knowledge (bundled + learned)  ->  session checks  ->  classifier gate  ->  LLM  ->  remember

Every stage is timed. The response carries the timings so the extension
can log a full breakdown without anyone tailing server logs.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from ..config import Settings
from ..schemas import Category, ExplainRequest, ExplainResponse, ExplanationItem, Timings
from . import classifier, context
from .knowledge import ConceptEntry, ConceptIndex
from .learned_cache import LearnedCache
from .lexical_dictionary import LexicalDictionary
from .providers import LLMProvider, LLMResult
from .session_store import SessionStore
from .textnorm import normalize

log = logging.getLogger(__name__)

MIN_LLM_CONFIDENCE = 0.5
_RETRYABLE = ("HTTP 429", "HTTP 503", "HTTP 502")


@dataclass
class Services:
    settings: Settings
    index: ConceptIndex
    learned: LearnedCache
    lexical: LexicalDictionary
    sessions: SessionStore
    provider: LLMProvider
    _inflight: dict[str, asyncio.Task] = field(default_factory=dict)


def _ms(since: float) -> float:
    return round((time.perf_counter() - since) * 1000, 1)


def _category(name: str) -> Category:
    return Category(name) if name in Category.__members__ else Category.other


def _from_entry(entry: ConceptEntry, term: str, timings: Timings) -> ExplainResponse:
    return ExplainResponse(
        useful=True,
        term=term,
        title=entry.concept,
        normalized_concept=entry.concept,
        aliases=entry.aliases,
        category=_category(entry.category),
        explanation=entry.explanation,
        confidence=entry.confidence,
        source="dictionary",
        stage="dictionary",
        timings=timings,
    )


def _item_from_entry(entry: ConceptEntry, term: str, source: str | None = None, usefulness_score: float = 1.0) -> ExplanationItem:
    return ExplanationItem(
        term=term,
        normalized_concept=entry.concept,
        aliases=entry.aliases,
        category=_category(entry.category),
        explanation=entry.explanation[:240],
        confidence=entry.confidence,
        source=source or ("dictionary" if entry.source in {"bundled", "learned"} else entry.source),
        usefulness_score=usefulness_score,
    )


def _response_from_items(items: list[ExplanationItem], timings: Timings, stage: str = "dictionary") -> ExplainResponse:
    """Make v0.3 response fields mirror item zero for wire compatibility."""
    first = items[0]
    return ExplainResponse(
        useful=True, term=first.term, title=first.normalized_concept,
        normalized_concept=first.normalized_concept, aliases=first.aliases,
        category=first.category, explanation=first.explanation,
        confidence=first.confidence, source=first.source, stage=stage,
        items=items, timings=timings,
    )


async def explain(req: ExplainRequest, svc: Services) -> ExplainResponse:
    t_start = time.perf_counter()
    timings = Timings()
    settings = svc.settings

    current = req.current_subtitle.strip()[: settings.max_subtitle_chars]
    window = context.build_window(req.context, current, settings.context_window_size)
    video_id = req.video_id or "anonymous"
    cue_start = req.cue_start if req.cue_start is not None else (window[-1].timestamp + 0.001 if window else 0.0)

    # Everything we have seen is remembered with its timestamp. Decisions below
    # only ever look at cues strictly before cue_start, so prefetching a future
    # cue cannot leak into the explanation of an earlier one.
    for seg in window:
        svc.sessions.record_cue(video_id, seg.timestamp, seg.text)
    svc.sessions.record_cue(video_id, cue_start, current)

    # ---- Layer 1: cheap precision gate (manual Alt+X skips it) -------------
    # A local definition is still an interruption, so a dictionary hit alone
    # must not bypass the candidate gate in proactive mode.
    if not req.force:
        t = time.perf_counter()
        verdict = classifier.classify(current, [s.text for s in window])
        timings.classifier_ms = _ms(t)
        if not verdict.is_candidate:
            timings.total_ms = _ms(t_start)
            return ExplainResponse(
                useful=False,
                source="classifier",
                stage="gate",
                diagnostics={"candidate_score": verdict.score, "reasons": verdict.reasons, "decision": "rejected_candidate"},
                timings=timings,
            )
        log.info("classifier candidate score=%.2f reasons=%s", verdict.score, verdict.reasons)

    # ---- Layer 2: local dictionary / learned knowledge ---------------------
    t = time.perf_counter()
    matches = svc.index.find_in_text(current)
    timings.knowledge_ms = _ms(t)

    if matches:
        # ConceptIndex yields non-overlapping matches in subtitle occurrence
        # order. Preserve that order after final eligibility checks.
        t = time.perf_counter()
        items: list[ExplanationItem] = []
        suppressed = 0
        for match in matches:
            entry = match.entry
            explained_by_us = svc.sessions.was_explained_by_us(video_id, entry.key, cue_start) or svc.sessions.recently_shown_anywhere(entry.key)
            defined_in_video = not explained_by_us and svc.sessions.was_defined_in_video(video_id, [entry.concept, *entry.aliases], cue_start)
            if (explained_by_us or defined_in_video) and not req.force:
                suppressed += 1
                continue
            if entry.source == "learned":
                svc.learned.record_hit(entry.key)
            items.append(_item_from_entry(entry, match.matched_text))
            if len(items) == settings.max_cards_per_cue:
                break
        timings.session_ms = _ms(t)
        if items:
            timings.total_ms = _ms(t_start)
            response = _response_from_items(items, timings)
            response.diagnostics = {"candidate_score": 1.0, "decision": "dictionary_hits", "matched_count": len(matches), "suppressed": suppressed}
            return response
        timings.total_ms = _ms(t_start)
        return ExplainResponse(useful=False, already_explained=bool(suppressed), source="session", stage="dictionary", timings=timings)

    # ---- Layer 3: broad offline dictionary for difficult ordinary words ----
    lexical_matches = svc.lexical.difficult_words(current, settings.max_cards_per_cue)
    if lexical_matches:
        timings.total_ms = _ms(t_start)
        items = [ExplanationItem(term=entry.word, normalized_concept=entry.word, category=Category.concept,
            explanation=entry.definition[:240], confidence=0.9, source="dictionary", usefulness_score=candidate.score)
            for entry, candidate in lexical_matches]
        response = _response_from_items(items, timings)
        response.diagnostics = {"candidate_score": items[0].usefulness_score, "decision": "validated_wordnet_fallback", "matched_terms": [item.term for item in items]}
        return response

    # ---- Layer 4: LLM, deduplicated across concurrent identical requests ----
    known = [svc.index.get(k).concept for k in svc.sessions.get(video_id).explained if svc.index.get(k)]
    formatted = context.format_window(window)

    t = time.perf_counter()
    result = await _call_llm_deduped(svc, normalize(current), current, formatted, known)
    timings.llm_ms = _ms(t)
    timings.total_ms = _ms(t_start)

    if result.failed and not result.useful:
        log.warning("llm failed: %s", result.error)
        return ExplainResponse(
            useful=False,
            source="error",
            stage="error",
            error_detail=result.error,
            diagnostics={"decision": "model_failed", "error": result.error},
            timings=timings,
        )

    if not result.useful or result.confidence < MIN_LLM_CONFIDENCE:
        return ExplainResponse(
            useful=False,
            already_explained=result.already_explained,
            source="llm",
            stage="model",
            diagnostics={"decision": "model_rejected", "confidence": result.confidence, "reason": "low_confidence"},
            timings=timings,
        )

    entry = svc.learned.remember(
        result.normalized_concept or result.term,
        [result.term, *result.aliases],
        result.category if result.category in Category.__members__ else "other",
        result.explanation,
        result.confidence,
    )
    log.info("llm useful term=%r concept=%r %.0fms", result.term, entry.concept, timings.llm_ms)

    item = _item_from_entry(entry, result.term, source="llm", usefulness_score=result.confidence)
    item.confidence = result.confidence
    response = _response_from_items([item], timings, stage="model")
    response.diagnostics = {"decision": "llm_used", "confidence": result.confidence, "term": result.term}
    return response


async def _call_llm_deduped(svc: Services, key: str, current: str, formatted: str, known: list[str]) -> LLMResult:
    """If the same cue is already being explained (two prefetch paths racing), share the call."""
    task = svc._inflight.get(key)
    if task is None:
        task = asyncio.create_task(_call_llm_with_retry(svc.provider, current, formatted, known))
        svc._inflight[key] = task
        task.add_done_callback(lambda _t: svc._inflight.pop(key, None))
    return await asyncio.shield(task)


async def _call_llm_with_retry(provider: LLMProvider, current: str, formatted: str, known: list[str]) -> LLMResult:
    result = await provider.explain(current, formatted, known)
    if result.failed and result.error and result.error.startswith(_RETRYABLE):
        await asyncio.sleep(0.4)
        result = await provider.explain(current, formatted, known)
    return result
