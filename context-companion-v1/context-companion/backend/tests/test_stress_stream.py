from __future__ import annotations

from app.services.classifier import classify


def test_long_stress_stream_remains_stable():
    texts = []
    terms = [
        "liquidity", "default", "statute", "fiduciary", "mortgage", "subpoena",
        "derivative", "fusion", "protocol", "mutation", "covenant", "injunction",
        "arbitration", "volatility", "capital", "interest", "bank", "trade",
        "policy", "squeeze", "equity", "sanctions", "debt", "yield", "asset",
    ]
    for i in range(12000):
        term = terms[i % len(terms)]
        prefix = "we need to go home" if i % 5 == 0 else "the market moved with"
        if i % 11 == 0:
            texts.append(f"The {term} shock changed the market situation.")
        elif i % 7 == 0:
            texts.append(f"{prefix} a {term} question in the hearing.")
        else:
            texts.append(f"The company discussed {term} during the briefing and then left.")

    results = []
    for text in texts:
        results.append(classify(text, []))

    assert len(results) == 12000
    assert all(isinstance(item.is_candidate, bool) for item in results)
    assert sum(1 for item in results if item.is_candidate) > 0
