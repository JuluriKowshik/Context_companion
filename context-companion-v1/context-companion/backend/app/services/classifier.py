"""High-recall candidate gating for subtitle explanation.

The goal is not to decide final usefulness here; it is to decide whether a cue is
worth passing to the more expensive contextual checks and optional LLM call.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from wordfreq import zipf_frequency

from ..config import Settings
from .textnorm import is_valid_lexical_token, normalize_lexical_term, tokenize_lexical_units

# Heavily common conversational words are almost never worth interrupting on.
_COMMON_WORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "than", "that", "this",
    "those", "these", "there", "here", "what", "when", "where", "who", "why", "how",
    "because", "while", "before", "after", "into", "onto", "over", "under", "around",
    "through", "without", "with", "from", "for", "about", "between", "among", "your",
    "you", "yourself", "we", "they", "them", "their", "our", "us", "i", "me", "my",
    "mine", "he", "she", "it", "his", "her", "hers", "its", "is", "are", "was", "were",
    "be", "been", "being", "am", "do", "does", "did", "have", "has", "had", "can",
    "could", "should", "would", "will", "shall", "may", "might", "must", "not", "no",
    "yes", "yeah", "okay", "ok", "go", "come", "say", "said", "says", "tell", "told",
    "know", "known", "think", "thought", "want", "wanted", "need", "needed", "look",
    "looked", "use", "used", "make", "made", "take", "taken", "put", "give", "gave",
    "get", "got", "good", "great", "little", "big", "small", "people", "person", "thing",
    "things", "time", "day", "week", "month", "year", "work", "working", "live", "lives",
    "life", "world", "home", "house", "money", "man", "woman", "child", "children",
    "way", "find", "found", "call", "called", "story", "stories", "start", "started", "talk",
    "talked", "right", "left", "last", "first", "next", "also", "very", "really", "just",
    "more", "most", "less", "even", "still", "already", "never", "always", "much", "many",
    "some", "any", "all", "none", "other", "another", "same", "different", "important",
    "actually", "probably", "something", "everything", "anything", "nothing", "someone",
    "anyone", "everyone", "beautiful", "wonderful", "elegant", "intricate", "intricately",
    "notation", "dragon", "moonlight", "sunlight", "novel", "chapter", "room", "hallway",
    "painting", "paintings", "art", "town", "valley", "field", "forest", "storyline",
    "understand", "remember", "tomorrow", "yesterday", "charming", "gorgeous", "splendid",
    "vivid", "poetic", "lyrical", "dramatic", "glorious", "gentle", "bright", "quiet",
    "simple", "complex", "difficult", "easy", "hard", "large", "small", "sunrise", "rain",
    "storm", "sky", "crimson", "firelight", "long", "short", "wide", "narrow", "warm",
    "cold", "lonely", "strange", "gentle", "peaceful", "beautifully", "furniture",
}

_NOT_ENTITIES = {
    "i", "i'm", "i've", "i'll", "i'd", "ok", "okay", "yeah", "yes", "no", "oh",
    "hey", "hi", "hello", "well", "god", "jesus", "christ", "mr", "mrs", "ms",
    "dr", "sir", "ma'am", "mom", "dad", "monday", "tuesday", "wednesday",
    "thursday", "friday", "saturday", "sunday", "january", "february", "march",
    "april", "may", "june", "july", "august", "september", "october",
    "november", "december", "english", "american", "tv", "dna", "fbi", "cia",
}

_DOMAIN_TERMS = {
    "financial": {
        "short", "shorting", "shorted", "hedge", "hedged", "leverage", "derivative", "bond",
        "yield", "yields", "collateral", "default", "liquidity", "margin", "futures", "option",
        "options", "swap", "swaps", "tranche", "subprime", "ipo", "equity", "dividend",
        "arbitrage", "cdo", "cds", "fed", "inflation", "recession", "bailout", "mortgage",
        "securities", "bubble", "capitalization", "debt", "asset", "assets", "covenant",
        "merger", "selloff", "spread", "volatility", "capital", "market", "rates", "rate",
        "credit", "lender", "borrow", "ratio", "portfolio", "bank", "investor", "security",
        "insurer", "valuation", "yield", "shorts"},
    "legal": {"amendment", "subpoena", "indictment", "plea", "felony", "misdemeanor",
        "habeas", "warrant", "injunction", "deposition", "perjury", "acquittal", "parole",
        "probation", "verdict", "tort", "jurisdiction", "affidavit", "arraignment", "bail",
        "miranda", "statute", "liability", "contract", "liquidation", "ordinance", "council",
        "constitutional", "liquidation", "settlement", "hearing", "testimony", "evidence",
        "trial", "appeal", "brief", "charge", "plaintiff", "defendant", "complaint", "remedy",
        "penalty", "sanction", "sanctions", "regime", "writ", "fiduciary", "duty", "standard",
        "due", "obligation", "arbitration", "clause", "clauses", "jurisdiction", "federal",
        "board"},
    "political": {"filibuster", "caucus", "impeach", "impeachment", "senate", "congress",
        "parliament", "coalition", "sanctions", "treaty", "referendum", "gerrymander",
        "electoral", "cabinet", "bill", "veto", "government", "regime", "diplomacy"},
    "scientific": {"quantum", "entropy", "genome", "protein", "enzyme", "isotope",
        "fusion", "fission", "neutron", "photon", "relativity", "mitosis", "antibody",
        "vaccine", "mutation", "algorithm", "encryption", "bandwidth", "neural", "plutonium",
        "uranium", "centrifuge", "molecule", "microbe", "genetic", "vector", "protocol",
        "sequence", "arrhythmia", "cell", "variant", "checksum", "hash", "buffer",
        "nonce", "security", "analysis", "neurological", "deficit", "clinical", "trial",
        "patient", "infection", "medical"},
    "military": {"battalion", "regiment", "platoon", "flank", "ordnance", "sortie",
        "recon", "artillery", "insurgent", "extraction", "casevac", "strategy", "tactic",
        "battlefield", "intelligence"},
}

_MONEY_OR_NUMBER = re.compile(r"[$€£¥]\s?\d|\d+(\.\d+)?\s?(%|percent|million|billion|trillion|bps)", re.I)
_YEAR = re.compile(r"\b(1[5-9]\d\d|20\d\d)\b")
_QUOTED = re.compile(r"[\"“']([^\"”']{3,40})[\"”']")


@dataclass
class ClassifierResult:
    is_candidate: bool
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CandidateTerm:
    term: str
    score: float
    position: int
    zipf: float
    domain: bool


def classify(current: str, context_texts: list[str]) -> ClassifierResult:
    """Score the subtitle for candidate status and keep the gate conservative but broad."""
    text = (current or "").strip()
    if not text:
        return ClassifierResult(False, 0.0, ["empty"])

    raw_words = tokenize_lexical_units(text)
    words = [normalize_lexical_term(word) for word in raw_words if normalize_lexical_term(word)]
    if len(words) < 2:
        return ClassifierResult(False, 0.0, ["too_short"])

    score = 0.0
    reasons: list[str] = []
    strongest_signal = 0.0
    candidate_terms: list[str] = []

    for token in words:
        if token in _COMMON_WORDS:
            continue
        zipf = zipf_frequency(token, "en")
        signal = _term_signal(token, zipf)
        if signal <= 0:
            continue
        strongest_signal = max(strongest_signal, signal)
        candidate_terms.append(token)
        score += signal

    if candidate_terms:
        score = min(score, 2.2)
    else:
        score = 0.0

    if _MONEY_OR_NUMBER.search(text) or _YEAR.search(text):
        score += 0.35
        reasons.append("number_or_year")

    if _QUOTED.search(text):
        score += 0.15
        reasons.append("quoted_phrase")

    entities = _capitalised_mid_sentence(raw_words)
    if entities:
        score += 0.25
        reasons.append(f"entities:{','.join(entities[:3])}")

    hits = _domain_hits(words)
    if hits:
        score += 0.7
        reasons.append(f"domain:{','.join(hits[:3])}")

    if len(words) <= 4 and not hits and strongest_signal < 0.4:
        score *= 0.6

    if reasons:
        reasons = reasons[:4]
    if candidate_terms:
        reasons.insert(0, f"candidate:{','.join(candidate_terms[:2])}")

    min_score = Settings().candidate_min_score
    decision = score >= min_score
    return ClassifierResult(decision, round(score, 2), reasons)


def candidate_terms(text: str, limit: int = 3) -> list[CandidateTerm]:
    """Rank valid lexical candidates for local definitions.

    This is deliberately narrower than ``classify``: WordNet membership alone
    cannot create a card, and likely proper names are excluded unless a domain
    cue explicitly makes the token technical.
    """
    raw = tokenize_lexical_units(text)
    out: list[CandidateTerm] = []
    seen: set[str] = set()
    for pos, original in enumerate(raw):
        term = normalize_lexical_term(original)
        if not term or term in seen or term in _COMMON_WORDS:
            continue
        seen.add(term)
        zipf = zipf_frequency(term, "en")
        domain = term in _domain_hits([term])
        signal = _term_signal(term, zipf)
        # Mid-sentence capitalisation is normally a name, not vocabulary.
        if pos > 0 and original[:1].isupper() and not domain:
            continue
        # Avoid turning an arbitrary WordNet entry into a card.  Domain terms
        # may be common in general English; non-domain vocabulary must carry a
        # meaningful rarity signal.
        if not domain and (zipf >= 4.0 or signal < 0.35):
            continue
        out.append(CandidateTerm(term, signal, pos, zipf, domain))
    return sorted(out, key=lambda item: (-item.score, item.position))[:limit]


def _capitalised_mid_sentence(words: list[str]) -> list[str]:
    found = []
    for i, w in enumerate(words):
        if i == 0 or not w or not w[0].isupper():
            continue
        if w.lower() in _NOT_ENTITIES or len(w) < 3:
            continue
        found.append(w)
    return found


def _domain_hits(words: list[str]) -> list[str]:
    lowered = {w.lower() for w in words}
    hits = []
    for terms in _DOMAIN_TERMS.values():
        hits.extend(sorted(lowered & terms))
    return hits


def _term_signal(token: str, zipf: float) -> float:
    if not token or not is_valid_lexical_token(token):
        return 0.0
    if token in _COMMON_WORDS:
        return 0.0
    domain_hits = _domain_hits([token])
    if token.lower() not in domain_hits and zipf >= 3.7:
        return 0.0
    score = 0.0
    if zipf < 3.0:
        score += 0.55
    elif zipf < 4.0:
        score += 0.35
    elif zipf < 4.5:
        score += 0.15
    if len(token) >= 8:
        score += 0.12
    if len(token) <= 3 and zipf < 3.0:
        score += 0.2
    if "-" in token:
        score += 0.15
    if token.lower() in domain_hits:
        score += 0.65
    return round(score, 3)
