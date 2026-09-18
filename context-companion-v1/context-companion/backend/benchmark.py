#!/usr/bin/env python3
"""Reusable benchmark runner for the candidate gate."""
from __future__ import annotations

import json
from pathlib import Path

from app.services.classifier import classify


def run_benchmark(data_path: str | Path = "tests/data/benchmark_cases.json") -> dict:
    path = Path(data_path)
    cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
    correct = 0
    positive = 0
    negative = 0
    positive_correct = 0
    negative_correct = 0
    for case in cases:
        verdict = classify(case["text"], [])
        expected = case["expected"]
        if verdict.is_candidate == expected:
            correct += 1
            if expected:
                positive_correct += 1
            else:
                negative_correct += 1
        if expected:
            positive += 1
        else:
            negative += 1
    return {
        "total": len(cases),
        "correct": correct,
        "accuracy": round(correct / len(cases), 4),
        "positive": positive,
        "positive_correct": positive_correct,
        "positive_accuracy": round(positive_correct / positive, 4) if positive else 0.0,
        "negative": negative,
        "negative_correct": negative_correct,
        "negative_accuracy": round(negative_correct / negative, 4) if negative else 0.0,
    }


if __name__ == "__main__":
    print(json.dumps(run_benchmark(), indent=2, sort_keys=True))
