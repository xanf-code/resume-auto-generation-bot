"""Tests for src.pipeline.llm — importability and callables, no live API call."""
import importlib


def test_llm_imports_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    import src.pipeline.llm as llm

    importlib.reload(llm)
    assert llm is not None


def test_helpers_are_callable():
    import src.pipeline.llm as llm

    assert callable(llm.client)
    assert callable(llm.parse_fast)
    assert callable(llm.parse_strong)


def test_client_is_cached():
    """client() must be lru_cache-wrapped (lazy singleton)."""
    import src.pipeline.llm as llm

    assert hasattr(llm.client, "cache_clear")
