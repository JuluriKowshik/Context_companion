from pathlib import Path

import pytest

from app.config import Settings
from app.routes.explain import stats
from app.services.learned_cache import LearnedCache
from app.services.knowledge import ConceptIndex


def test_runtime_paths_are_portable_and_absolute():
    cfg = Settings(
        learned_cache_path="data/learned_concepts.db",
        lexical_dictionary_path="data/wordnet_dictionary.db",
        nltk_data_path="data/nltk_data",
    )
    assert Path(cfg.learned_cache_path).is_absolute()
    assert Path(cfg.lexical_dictionary_path).is_absolute()
    assert Path(cfg.nltk_data_path).is_absolute()
    assert any(cfg.learned_cache_path.startswith(prefix) for prefix in ("/", "C:\\"))


@pytest.mark.asyncio
async def test_stats_does_not_expose_internal_file_paths(tmp_path):
    index = ConceptIndex.from_bundled_dir(Path("app/data/concepts"))
    learned = LearnedCache(tmp_path / "learned.db", index)
    result = await stats(type("Svc", (), {"index": index, "learned": learned, "sessions": type("Sessions", (), {"stats": lambda self: {"session_keys": 0}})()})())
    assert "path" not in result
    assert "learned_concepts" in result
