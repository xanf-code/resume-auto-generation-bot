"""Tests for src.pipeline.llm — importability, callables, and model_context."""
import importlib


def test_llm_imports_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    import src.pipeline.llm as llm

    importlib.reload(llm)
    assert llm is not None


def test_helpers_are_callable():
    import src.pipeline.llm as llm

    assert callable(llm.client)
    assert callable(llm.parse_fast)
    assert callable(llm.parse_strong)
    assert callable(llm.model_context)


def test_client_is_cached():
    """client() must be lru_cache-wrapped (lazy singleton)."""
    import src.pipeline.llm as llm

    assert hasattr(llm.client, "cache_clear")


def test_model_context_injects_and_resets():
    """model_context must override context vars for its block then restore them."""
    from src.pipeline.llm import _ctx_model_fast, _ctx_model_strong, model_context

    with model_context(fast="fast-test", strong="strong-test"):
        assert _ctx_model_fast.get() == "fast-test"
        assert _ctx_model_strong.get() == "strong-test"

    # Vars restored to default (None) after exiting.
    assert _ctx_model_fast.get() is None
    assert _ctx_model_strong.get() is None


def test_model_context_yields_usage_list():
    """model_context yields a mutable list that accumulates usage records."""
    from src.pipeline.llm import model_context

    with model_context(fast="f", strong="s") as usage:
        assert isinstance(usage, list)
        usage.append({"model": "f", "input_tokens": 10, "output_tokens": 5})

    assert len(usage) == 1


def test_model_context_resets_on_exception():
    """Context vars are reset even when the body raises."""
    from src.pipeline.llm import _ctx_model_fast, model_context

    try:
        with model_context(fast="boom-fast", strong="boom-strong"):
            raise RuntimeError("intentional")
    except RuntimeError:
        pass

    assert _ctx_model_fast.get() is None
