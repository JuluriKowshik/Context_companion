import json
from pathlib import Path

from app.services.classifier import classify


def _load_cases(path: str) -> list[dict]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return payload["cases"]


def test_common_and_rare_vocab_are_ranked_consistently():
    cases = _load_cases("tests/data/benchmark_cases.json")
    positives = 0
    negatives = 0
    expected_positive = sum(1 for case in cases if case["expected"])
    expected_negative = len(cases) - expected_positive
    for case in cases:
        verdict = classify(case["text"], [])
        expected = case["expected"]
        if verdict.is_candidate == expected:
            if expected:
                positives += 1
            else:
                negatives += 1
    assert positives >= max(1, expected_positive * 0.8)
    assert negatives >= max(1, expected_negative * 0.8)


def test_common_dialogue_is_rejected_even_with_long_words():
    assert not classify("The important thing is to remember what happened.", []).is_candidate
    assert not classify("We need to know what happened before we go.", []).is_candidate


def test_short_domain_terms_remain_candidates():
    assert classify("The debt is due and the covenant is under pressure.", []).is_candidate
    assert classify("This is a fiduciary duty under the statute.", []).is_candidate
