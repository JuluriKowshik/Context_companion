"""Used when no key is configured. Lets the extension be tested end to end."""
from .base import LLMProvider, LLMResult


class MockProvider(LLMProvider):
    name = "mock"

    async def explain(self, current_cue: str, previous_context: str, known_concepts: list[str]) -> LLMResult:
        return LLMResult(
            useful=True,
            term="Mock mode",
            normalized_concept="mock mode",
            category="other",
            explanation=f"No LLM key configured. Received: {current_cue[:40]}",
            confidence=0.1,
        )
