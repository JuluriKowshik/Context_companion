from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Category(str, Enum):
    concept = "concept"
    historical_reference = "historical_reference"
    cultural_reference = "cultural_reference"
    legal = "legal"
    political = "political"
    financial = "financial"
    scientific = "scientific"
    medical = "medical"
    military = "military"
    technical = "technical"
    person = "person"
    place = "place"
    organization = "organization"
    idiom = "idiom"
    slang = "slang"
    internet_culture = "internet_culture"
    plot_context = "plot_context"
    other = "other"


class ContextSegment(BaseModel):
    text: str = Field(..., max_length=1000)
    timestamp: float = Field(..., ge=0)


class ExplainRequest(BaseModel):
    current_subtitle: str = Field(..., min_length=1, max_length=1000)
    context: list[ContextSegment] = Field(default_factory=list, max_length=20)
    # True for manual Alt+X: user asked, so the candidate gate is skipped.
    force: bool = False
    # Identifies the viewing session for session memory and "already explained" checks.
    video_id: Optional[str] = Field(default=None, max_length=64)
    # Start time of the cue being explained. Session memory only uses cues before this.
    cue_start: Optional[float] = Field(default=None, ge=0)
    # "manual" | "prefetch" | "live". Debug aid, affects nothing else.
    mode: str = "manual"
    selected_text: Optional[str] = None


class Timings(BaseModel):
    knowledge_ms: float = 0
    session_ms: float = 0
    classifier_ms: float = 0
    llm_ms: float = 0
    total_ms: float = 0


class ExplanationItem(BaseModel):
    term: str
    normalized_concept: str
    aliases: list[str] = Field(default_factory=list)
    category: Category = Category.other
    explanation: str
    confidence: float
    source: str = "llm"
    usefulness_score: float = 0.0


class ExplainResponse(BaseModel):
    useful: bool
    term: Optional[str] = None
    normalized_concept: Optional[str] = None
    aliases: list[str] = Field(default_factory=list)
    category: Optional[Category] = None
    explanation: Optional[str] = None
    confidence: Optional[float] = None
    already_explained: bool = False
    # Presentation source for useful responses: dictionary | llm.  Non-useful
    # responses may use an internal diagnostic value (session/classifier/error).
    source: str = "llm"
    # Backwards compatibility with the first extension build.
    title: Optional[str] = None
    stage: str = "model"
    error_detail: Optional[str] = None
    diagnostics: dict = Field(default_factory=dict)
    timings: Timings = Field(default_factory=Timings)
    # `items` is the multi-card contract. Legacy top-level fields mirror its
    # first item so older extension builds remain usable.
    items: list[ExplanationItem] = Field(default_factory=list, max_length=3)


class ShownRequest(BaseModel):
    """The extension reports what it actually displayed, so session memory
    reflects what the viewer saw rather than what the backend returned."""
    video_id: str = Field(..., max_length=64)
    concept: str = Field(..., max_length=120)
    cue_start: float = Field(..., ge=0)
