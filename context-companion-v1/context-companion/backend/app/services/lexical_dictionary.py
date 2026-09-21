"""Offline WordNet definitions, indexed in SQLite for constant-time lookup."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import nltk
from nltk.corpus import wordnet
from wordfreq import zipf_frequency

from .classifier import CandidateTerm, candidate_terms
from .textnorm import normalize, stem_variants


@dataclass(frozen=True)
class LexicalEntry:
    word: str
    part_of_speech: str
    definition: str
    zipf: float


class LexicalDictionary:
    def __init__(self, path: str, nltk_data_path: str, build_on_startup: bool = True):
        base_dir = Path(__file__).resolve().parents[2]
        self.path = Path(path)
        if not self.path.is_absolute():
            self.path = base_dir / self.path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        nltk_path = Path(nltk_data_path)
        if not nltk_path.is_absolute():
            nltk_path = base_dir / nltk_path
        nltk.data.path.insert(0, str(nltk_path.resolve()))
        self._build_on_startup = build_on_startup
        if self._build_on_startup:
            self._ensure_index()

    def _connect(self):
        return sqlite3.connect(self.path)

    def _ensure_index(self):
        with self._connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS entries (word TEXT PRIMARY KEY, pos TEXT NOT NULL, definition TEXT NOT NULL)")
            count = db.execute("SELECT count(*) FROM entries").fetchone()[0]
            if count:
                return
            rows = {}
            for synset in wordnet.all_synsets():
                definition = synset.definition().strip()
                if not definition:
                    continue
                for lemma in synset.lemma_names():
                    word = normalize(lemma.replace("_", " "))
                    if word and word not in rows:
                        rows[word] = (synset.pos(), definition)
            db.executemany("INSERT INTO entries(word, pos, definition) VALUES (?, ?, ?)", ((word, *value) for word, value in rows.items()))

    def _lazy_ensure_index(self):
        if not self._build_on_startup:
            self._build_on_startup = True
            self._ensure_index()

    def lookup(self, word: str) -> LexicalEntry | None:
        normalized = normalize(word)
        if not normalized or " " in normalized:
            return None
        self._lazy_ensure_index()
        with self._connect() as db:
            for form in stem_variants(normalized):
                row = db.execute("SELECT pos, definition FROM entries WHERE word = ?", (form,)).fetchone()
                if row:
                    return LexicalEntry(form, row[0], row[1], zipf_frequency(form, "en"))
        return None

    def difficult_words(self, text: str, limit: int = 3) -> list[tuple[LexicalEntry, CandidateTerm]]:
        """Validated local vocabulary candidates, ranked by final local value."""
        found: list[tuple[LexicalEntry, CandidateTerm]] = []
        for candidate in candidate_terms(text, limit=limit * 3):
            if len(candidate.term) < 3:
                continue
            # Common domain nouns ("protocol", "market") need context; do
            # not let a generic WordNet gloss bypass the model for them.
            if candidate.zipf >= 4.0:
                continue
            entry = self.lookup(candidate.term)
            if entry:
                found.append((entry, candidate))
        return sorted(found, key=lambda pair: (-pair[1].score, pair[1].position))[:limit]

    def difficult_word(self, text: str) -> LexicalEntry | None:
        entries = self.difficult_words(text, 1)
        return entries[0][0] if entries else None
