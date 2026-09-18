"""Rolling context handling.

The extension already trims the buffer, but the backend re-trims so the
window policy has one source of truth. Today the window is count-based;
`build_window` is the only place to change when it becomes time/token based.
"""
from ..schemas import ContextSegment


def build_window(context: list[ContextSegment], current: str, size: int) -> list[ContextSegment]:
    """Return the last `size` segments, oldest first, excluding the current line."""
    prior = [seg for seg in context if seg.text.strip() and seg.text.strip() != current.strip()]
    prior.sort(key=lambda s: s.timestamp)
    return _dedupe_adjacent(prior)[-size:]


def _dedupe_adjacent(segments: list[ContextSegment]) -> list[ContextSegment]:
    out: list[ContextSegment] = []
    for seg in segments:
        if out and out[-1].text.strip() == seg.text.strip():
            continue
        out.append(seg)
    return out


def format_window(window: list[ContextSegment]) -> str:
    """Plain text block the model can read. One line per segment."""
    if not window:
        return "(no earlier dialogue)"
    return "\n".join(f"[{seg.timestamp:.1f}s] {seg.text.strip()}" for seg in window)
