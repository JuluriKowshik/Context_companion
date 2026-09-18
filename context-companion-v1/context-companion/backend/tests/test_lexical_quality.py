from app.services.textnorm import (
    is_valid_lexical_token,
    normalize_lexical_term,
    tokenize_lexical_units,
)


def test_tokenize_preserves_valid_lexical_units_and_rejects_fragments():
    tokens = tokenize_lexical_units("The market's short-selling was red-lining the U.S. economy.")
    assert tokens == [
        "the",
        "market's",
        "short-selling",
        "was",
        "red-lining",
        "the",
        "u.s.",
        "economy",
    ]

    assert not is_valid_lexical_token("...")
    assert not is_valid_lexical_token("-")
    assert is_valid_lexical_token("market's")
    assert is_valid_lexical_token("short-selling")
    assert is_valid_lexical_token("U.S.")


def test_normalize_lexical_term_handles_edge_cases():
    assert normalize_lexical_term("  MARKET’S   ") == "market's"
    assert normalize_lexical_term("red-lining") == "red-lining"
    assert normalize_lexical_term("...") == ""


def test_morphology_does_not_make_artificial_fragments():
    from app.services.textnorm import stem_variants
    assert "run" in stem_variants("running")
    assert "stop" in stem_variants("stopped")
    assert "runn" not in stem_variants("running")
