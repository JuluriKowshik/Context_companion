"""Provider boundary. Everything outside this package sees only LLMProvider."""
from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.M)


@dataclass
class LLMResult:
    useful: bool
    term: Optional[str] = None
    normalized_concept: Optional[str] = None
    aliases: list[str] = field(default_factory=list)
    category: str = "other"
    explanation: Optional[str] = None
    confidence: float = 0.0
    already_explained: bool = False
    error: Optional[str] = None  # set when the call itself failed

    @property
    def failed(self) -> bool:
        return self.error is not None


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def explain(self, current_cue: str, previous_context: str, known_concepts: list[str]) -> LLMResult:
        """Never raises. Returns LLMResult with .error set on failure."""


def parse_llm_json(raw: str) -> LLMResult:
    """Strict server-side validation. Anything malformed becomes useful=false."""
    cleaned = _FENCE.sub("", (raw or "").strip())
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        log.warning("Model returned non-JSON: %r", raw[:200])
        return LLMResult(useful=False, error="non_json_output")

    if not isinstance(data, dict) or not data.get("useful"):
        return LLMResult(useful=False)

    term = str(data.get("term") or data.get("title") or "").strip()
    explanation = str(data.get("explanation") or "").strip()
    if not term or not explanation:
        return LLMResult(useful=False)

    aliases = data.get("aliases") or []
    if not isinstance(aliases, list):
        aliases = []

    try:
        confidence = float(data.get("confidence", 0.7))
    except (TypeError, ValueError):
        confidence = 0.7

    return LLMResult(
        useful=True,
        term=term[:60],
        normalized_concept=str(data.get("normalized_concept") or term).strip()[:80],
        aliases=[str(a).strip()[:60] for a in aliases if str(a).strip()][:10],
        category=str(data.get("category") or "other"),
        explanation=explanation[:240],
        confidence=max(0.0, min(1.0, confidence)),
        already_explained=bool(data.get("already_explained", False)),
    )
