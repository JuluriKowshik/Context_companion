"""In-memory alias index with n-gram lookup.

Why not a full English dictionary: 99 percent of English words are not worth
interrupting a viewer for, so a giant dictionary costs memory and produces
false positives while adding almost no value. A few hundred curated
concepts with aliases covers the high-value cases; the LLM covers the tail.

Lookup cost: for a cue of N tokens we do at most N * 4 dictionary probes
plus a few stem variants. Microseconds.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

from ..textnorm import MAX_NGRAM, ngrams, normalize, stem_variants, tokens

log = logging.getLogger(__name__)


@dataclass
class ConceptEntry:
    key: str  # normalised concept name, unique
    concept: str
    aliases: list[str]
    category: str
    explanation: str
    source: str  # "bundled" | "learned"
    confidence: float = 0.95
    # False for concepts whose bare name is ambiguous ("stroke", "cabinet"):
    # only the explicit aliases match, never the name itself.
    match_name: bool = True
    # Words that veto a match when they immediately follow it ("stroke" + "of").
    block_next: frozenset[str] = frozenset()


@dataclass
class Match:
    entry: ConceptEntry
    matched_text: str
    start: int
    length: int


@dataclass
class ConceptIndex:
    _by_key: dict[str, ConceptEntry] = field(default_factory=dict)
    _alias_to_key: dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------ build
    @classmethod
    def from_bundled_dir(cls, directory: Path) -> "ConceptIndex":
        index = cls()
        count = 0
        for path in sorted(directory.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            default_category = data.get("category", "other")
            for raw in data.get("concepts", []):
                index.add(
                    ConceptEntry(
                        key=normalize(raw["concept"]),
                        concept=raw["concept"],
                        aliases=raw.get("aliases", []),
                        category=raw.get("category", default_category),
                        explanation=raw["explanation"],
                        source="bundled",
                        match_name=raw.get("match_name", True),
                        block_next=frozenset(raw.get("block_next", [])),
                    )
                )
                count += 1
        log.info("Loaded %d bundled concepts (%d aliases)", count, len(index._alias_to_key))
        return index

    def add(self, entry: ConceptEntry) -> None:
        """Insert or replace. Later adds win, so learned entries can refine bundled ones."""
        self._by_key[entry.key] = entry
        for alias in self._alias_forms(entry):
            self._alias_to_key[alias] = entry.key

    def _alias_forms(self, entry: ConceptEntry) -> Iterable[str]:
        if entry.match_name:
            yield entry.key
        for alias in entry.aliases:
            norm = normalize(alias)
            if norm:
                yield norm

    def __len__(self) -> int:
        return len(self._by_key)

    def get(self, key: str) -> Optional[ConceptEntry]:
        return self._by_key.get(normalize(key))

    # ----------------------------------------------------------------- lookup
    def find_in_text(self, text: str) -> list[Match]:
        """Return non-overlapping matches, preferring longer phrases."""
        toks = tokens(text)
        matches: list[Match] = []
        consumed_until = -1
        for start, n, phrase in ngrams(toks, MAX_NGRAM):
            if start < consumed_until:
                continue
            key = self._probe(phrase, toks[start : start + n])
            if key is None:
                continue
            following = toks[start + n] if start + n < len(toks) else ""
            if following in self._by_key[key].block_next:
                continue
            matches.append(Match(self._by_key[key], phrase, start, n))
            consumed_until = start + n
        return matches

    def _probe(self, phrase: str, phrase_tokens: list[str]) -> Optional[str]:
        hit = self._alias_to_key.get(phrase)
        if hit:
            return hit
        # Cheap morphology: try stem variants of the last word only.
        head = phrase_tokens[:-1]
        for variant in stem_variants(phrase_tokens[-1])[1:]:
            hit = self._alias_to_key.get(" ".join(head + [variant]))
            if hit:
                return hit
        return None
