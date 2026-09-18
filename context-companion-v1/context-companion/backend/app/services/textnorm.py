"""Lexical normalization and tokenization used throughout the pipeline.

The baseline accepted a broad set of punctuation artifacts and could create
invalid fragments from subtitle text. This module keeps the fast local behavior
but validates tokens before they are used as candidate words or dictionary keys.
"""
from __future__ import annotations

import re

_PUNCT = re.compile(r"[^\w\s'\-\.]")
_SPACES = re.compile(r"\s+")
_APOS = re.compile(r"[\u2018\u2019\u201B`]")
_DASH = re.compile(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212-]")
_TOKEN_RE = re.compile(r"[A-Za-z]+(?:['’][A-Za-z]+)?(?:-[A-Za-z]+)?(?:\.[A-Za-z]+)+\.?|[A-Za-z]+(?:['’][A-Za-z]+)?(?:-[A-Za-z]+)?", re.UNICODE)

MAX_NGRAM = 4


def normalize_lexical_term(text: str) -> str:
    """Normalize a single lexical term without manufacturing arbitrary stems."""
    if text is None:
        return ""
    term = str(text).strip().lower()
    if not term:
        return ""
    term = _APOS.sub("'", term)
    term = _DASH.sub("-", term)
    term = term.replace("’", "'")
    term = term.replace("“", "").replace("”", "")
    term = re.sub(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]", "-", term)
    term = _SPUNCT_TO_SPACE.sub(" ", term)
    term = _SPACES.sub(" ", term).strip()
    if not term:
        return ""
    if not is_valid_lexical_token(term):
        cleaned = re.sub(r"[^A-Za-z'\-.]", "", term)
        cleaned = cleaned.strip("-'.")
        if not cleaned or not is_valid_lexical_token(cleaned):
            return ""
        term = cleaned
    if "." in term and not re.fullmatch(r"[A-Za-z]+(?:\.[A-Za-z]+)+\.?", term):
        term = term.rstrip(".")
    return term


def is_valid_lexical_token(token: str) -> bool:
    """Reject punctuation artifacts and malformed fragments before they reach ranking."""
    if token is None:
        return False
    value = str(token).strip()
    if not value or len(value) < 2:
        return False
    if value in {".", "..", "...", "-", "--", "'", "''", "\"", "\u2014"}:
        return False
    if re.search(r"[^A-Za-z'\-.]", value):
        return False
    if value.startswith("-") or value.endswith("-"):
        return False
    if value.count("..") > 0:
        return False
    if value.startswith("'") or value.endswith("'"):
        return False
    return bool(re.fullmatch(r"(?:[A-Za-z]+(?:['’][A-Za-z]+)?(?:-[A-Za-z]+)?(?:\.[A-Za-z]+)+\.?|[A-Za-z]+(?:['’][A-Za-z]+)?(?:-[A-Za-z]+)?)", value))


def tokenize_lexical_units(text: str) -> list[str]:
    """Collect valid lexical units while preserving contractions, hyphenated compounds and acronyms."""
    if text is None:
        return []
    cleaned = _APOS.sub("'", str(text))
    cleaned = _DASH.sub("-", cleaned)
    cleaned = cleaned.replace("\u2019", "'")
    cleaned = cleaned.replace("\u2013", "-")
    results = []
    for match in _TOKEN_RE.finditer(cleaned):
        token = match.group(0).strip()
        if not token or not is_valid_lexical_token(token):
            continue
        normalized = normalize_lexical_term(token)
        if normalized:
            results.append(normalized)
    return results


def normalize(text: str) -> str:
    """Return a normalized subtitle string suitable for concept matching."""
    parts = [normalize_lexical_term(tok) for tok in tokenize_lexical_units(text)]
    return " ".join(part for part in parts if part)


def tokens(text: str) -> list[str]:
    return tokenize_lexical_units(text)


def stem_variants(word: str) -> list[str]:
    """Return linguistically plausible morphological variants without inventing arbitrary stems."""
    value = normalize_lexical_term(word)
    if not value:
        return []
    out = [value]
    if len(value) > 4 and value.endswith("ies"):
        out.append(value[:-3] + "y")
    if len(value) > 4 and value.endswith("ing"):
        stem = value[:-3]
        doubled = len(value) > 5 and value[-4] == value[-5]
        if not doubled:
            out.append(stem)
            out.append(stem + "e")
        # doubled consonant: running -> run, stopping -> stop
        if doubled:
            out.append(value[:-4])
    if len(value) > 3 and value.endswith("ed"):
        doubled = len(value) > 4 and value[-3] == value[-4]
        if not doubled:
            out.append(value[:-2])
            out.append(value[:-1])
        if doubled:
            out.append(value[:-3])
    if len(value) > 3 and value.endswith("es"):
        out.append(value[:-2])
    if len(value) > 3 and value.endswith("s") and not value.endswith("ss"):
        out.append(value[:-1])
    return list(dict.fromkeys(out))


def ngrams(toks: list[str], max_n: int = MAX_NGRAM):
    """Yield (start_index, n, phrase) for every n-gram, longest first at each position."""
    for i in range(len(toks)):
        for n in range(min(max_n, len(toks) - i), 0, -1):
            yield i, n, " ".join(toks[i : i + n])


_PUNCT = _PUNCT
_SPUNCT_TO_SPACE = re.compile(r"[^A-Za-z0-9'\-\.] +")
_SPUNCT_TO_SPACE = re.compile(r"[^A-Za-z0-9'\-\.]")
