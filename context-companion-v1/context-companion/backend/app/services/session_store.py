"""Per-video memory for one viewing session. In-process, TTL-evicted.

Two jobs:
1. Remember which concepts we already surfaced, so the same term is not
   explained twice in one video.
2. Remember every cue we have seen with its timestamp, so we can check
   whether the video itself already defined a term BEFORE the current cue.
   Only cues with start < current cue are ever consulted. Prefetch may store
   future cues, but the timestamp gate keeps them out of any decision.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from .textnorm import normalize

# Patterns a video uses when it defines a term for the viewer.
_DEFINITION_PATTERNS = (
    r"\b{t}\b (is|are|was|were) (a|an|the|when|what|basically|essentially|just)\b",
    r"\b{t}\b means\b",
    r"\b{t}\b,? (which|that) (is|means|refers)\b",
    r"\b(called|known as|term for|word for|what we call|they call it|refer to as) \b{t}\b",
    r"\bdefine\w* \b{t}\b",
    r"\bwhat (is|are) \b{t}\b",
)


@dataclass
class Session:
    cues: list[tuple[float, str]] = field(default_factory=list)  # (start, normalised text)
    explained: dict[str, float] = field(default_factory=dict)  # concept key -> cue_start
    last_seen: float = field(default_factory=time.time)
    _seen_starts: set[float] = field(default_factory=set)


class SessionStore:
    def __init__(self, ttl_seconds: int, recent_ttl_seconds: int = 1800):
        self._ttl = ttl_seconds
        self._recent_ttl = recent_ttl_seconds
        self._sessions: dict[str, Session] = {}
        self._recent_global: dict[str, float] = {}  # concept key -> wall-clock time shown

    def get(self, video_id: str) -> Session:
        self._evict()
        session = self._sessions.setdefault(video_id, Session())
        session.last_seen = time.time()
        return session

    def _evict(self) -> None:
        cutoff = time.time() - self._ttl
        for vid in [v for v, s in self._sessions.items() if s.last_seen < cutoff]:
            del self._sessions[vid]

    # ---------------------------------------------------------------- record
    def record_cue(self, video_id: str, start: float, text: str) -> None:
        session = self.get(video_id)
        start = round(start, 2)
        if start in session._seen_starts:
            return
        session._seen_starts.add(start)
        session.cues.append((start, normalize(text)))
        if len(session.cues) > 4000:
            session.cues = session.cues[-3000:]

    def mark_explained(self, video_id: str, concept_key: str, cue_start: float) -> None:
        self.get(video_id).explained.setdefault(concept_key, cue_start)
        self._recent_global[concept_key] = time.time()

    def recently_shown_anywhere(self, concept_key: str) -> bool:
        at = self._recent_global.get(concept_key)
        if at is None:
            return False
        if time.time() - at > self._recent_ttl:
            del self._recent_global[concept_key]
            return False
        return True

    # ----------------------------------------------------------------- query
    def was_explained_by_us(self, video_id: str, concept_key: str, before: float) -> bool:
        at = self.get(video_id).explained.get(concept_key)
        return at is not None and at < before

    def was_defined_in_video(self, video_id: str, terms: list[str], before: float) -> bool:
        """Did any earlier cue define one of these terms? Cheap regex, prior cues only."""
        session = self.get(video_id)
        prior = [text for start, text in session.cues if start < before]
        if not prior:
            return False
        haystack = " ".join(prior[-200:])
        for term in terms:
            t = re.escape(normalize(term))
            if not t:
                continue
            for pattern in _DEFINITION_PATTERNS:
                if re.search(pattern.format(t=t), haystack):
                    return True
        return False

    def stats(self) -> dict:
        return {"active_sessions": len(self._sessions)}
