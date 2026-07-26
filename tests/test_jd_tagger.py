"""Tests for src.agents.jd_tagger - JD -> jd_type tags.

`parse_fast` is mocked to return a scripted ``JDTags``; NO live API calls.
"""
import pytest

from src.agents import jd_tagger
from src.pipeline.schemas import JDTags
from src.prompts.jd_tagger import JD_TAGGER_SYSTEM, JD_TYPE_VOCAB

SAMPLE_JD = "Senior Backend Engineer. Own REST APIs and distributed systems."


def test_jd_tags_is_strict():
    """JDTags rejects unknown fields (extra='forbid')."""
    with pytest.raises(Exception):
        JDTags(tags=["backend"], bogus="nope")  # type: ignore[call-arg]


def test_classify_jd_type_filters_out_of_vocab_tags(monkeypatch):
    monkeypatch.setattr(
        jd_tagger,
        "parse_fast",
        lambda *a, **k: JDTags(tags=["backend", "not-a-real-tag", "infra"]),
    )
    tags = jd_tagger.classify_jd_type(SAMPLE_JD)
    assert tags == ["backend", "infra"]


def test_classify_jd_type_dedupes_preserving_order(monkeypatch):
    monkeypatch.setattr(
        jd_tagger,
        "parse_fast",
        lambda *a, **k: JDTags(tags=["backend", "infra", "backend"]),
    )
    tags = jd_tagger.classify_jd_type(SAMPLE_JD)
    assert tags == ["backend", "infra"]


def test_classify_jd_type_empty_tags_returns_empty_list(monkeypatch):
    monkeypatch.setattr(jd_tagger, "parse_fast", lambda *a, **k: JDTags(tags=[]))
    assert jd_tagger.classify_jd_type(SAMPLE_JD) == []


def test_classify_jd_type_model_error_returns_empty_list(monkeypatch):
    def raise_error(*a, **k):
        raise ValueError("model exploded")

    monkeypatch.setattr(jd_tagger, "parse_fast", raise_error)
    assert jd_tagger.classify_jd_type(SAMPLE_JD) == []


def test_classify_jd_type_all_out_of_vocab_returns_empty_list(monkeypatch):
    monkeypatch.setattr(
        jd_tagger, "parse_fast", lambda *a, **k: JDTags(tags=["bogus", "also-bogus"])
    )
    assert jd_tagger.classify_jd_type(SAMPLE_JD) == []


def test_classify_jd_type_passes_jd_raw_and_schema(monkeypatch):
    captured = {}

    def fake_parse_fast(system, user, schema, **kwargs):
        captured["system"] = system
        captured["user"] = user
        captured["schema"] = schema
        return JDTags(tags=["backend"])

    monkeypatch.setattr(jd_tagger, "parse_fast", fake_parse_fast)
    jd_tagger.classify_jd_type(SAMPLE_JD)

    assert captured["user"] == SAMPLE_JD
    assert captured["schema"] is JDTags
    assert captured["system"] == JD_TAGGER_SYSTEM


def test_prompt_lists_full_vocabulary():
    for tag in JD_TYPE_VOCAB:
        assert tag in JD_TAGGER_SYSTEM


def test_vocab_matches_expected_set():
    assert set(JD_TYPE_VOCAB) == {
        "backend",
        "frontend",
        "fullstack",
        "ml",
        "data",
        "platform",
        "infra",
        "mobile",
        "security",
        "pm",
    }
