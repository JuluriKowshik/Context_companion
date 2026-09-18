"""Persistent cache of concepts learned from the LLM.

SQLite over JSON because: atomic writes, UNIQUE constraints handle duplicate
concepts, no full-file rewrite per insert, indexed alias lookup, and it is in
the Python standard library. The hot path still uses the in-memory
ConceptIndex; SQLite is only for durability and startup load.
"""
from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path

from .knowledge import ConceptEntry, ConceptIndex
from .textnorm import normalize

log = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS concepts (
    key         TEXT PRIMARY KEY,
    concept     TEXT NOT NULL,
    category    TEXT NOT NULL,
    explanation TEXT NOT NULL,
    confidence  REAL NOT NULL DEFAULT 0.8,
    hits        INTEGER NOT NULL DEFAULT 0,
    created_at  REAL NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS aliases (
    alias       TEXT PRIMARY KEY,
    concept_key TEXT NOT NULL REFERENCES concepts(key) ON DELETE CASCADE
);
"""


class LearnedCache:
    def __init__(self, path: str | Path, index: ConceptIndex):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._index = index
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._load_into_index()

    def _load_into_index(self) -> None:
        rows = self._conn.execute("SELECT key, concept, category, explanation, confidence FROM concepts").fetchall()
        alias_rows = self._conn.execute("SELECT alias, concept_key FROM aliases").fetchall()
        aliases: dict[str, list[str]] = {}
        for alias, key in alias_rows:
            aliases.setdefault(key, []).append(alias)
        for key, concept, category, explanation, confidence in rows:
            self._index.add(ConceptEntry(key, concept, aliases.get(key, []), category, explanation, "learned", confidence))
        log.info("Loaded %d learned concepts from %s", len(rows), self._path)

    def remember(self, concept: str, aliases: list[str], category: str, explanation: str, confidence: float) -> ConceptEntry:
        """Upsert. Bundled concepts are never overwritten; the LLM does not outrank curation."""
        key = normalize(concept)
        existing = self._index.get(key)
        if existing and existing.source == "bundled":
            return existing

        now = time.time()
        clean_aliases = sorted({normalize(a) for a in aliases if normalize(a) and normalize(a) != key})
        with self._conn:
            self._conn.execute(
                """INSERT INTO concepts (key, concept, category, explanation, confidence, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET
                     explanation=excluded.explanation, category=excluded.category,
                     confidence=excluded.confidence, updated_at=excluded.updated_at""",
                (key, concept, category, explanation, confidence, now, now),
            )
            for alias in clean_aliases:
                # An alias already pointing at a different concept stays where it is.
                self._conn.execute("INSERT OR IGNORE INTO aliases (alias, concept_key) VALUES (?, ?)", (alias, key))

        entry = ConceptEntry(key, concept, clean_aliases, category, explanation, "learned", confidence)
        self._index.add(entry)
        return entry

    def record_hit(self, key: str) -> None:
        with self._conn:
            self._conn.execute("UPDATE concepts SET hits = hits + 1 WHERE key = ?", (key,))

    def stats(self) -> dict:
        (count,) = self._conn.execute("SELECT COUNT(*) FROM concepts").fetchone()
        return {"learned_concepts": count, "path": str(self._path)}
