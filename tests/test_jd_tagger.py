"""Tests for src.agents.jd_tagger - JD -> role/domains classification.

`parse_fast` is mocked to return a scripted ``JDTags``; NO live API calls.
"""
import pytest

from src.agents import jd_tagger
from src.agents.jd_tagger import JdClassification
from src.pipeline.schemas import JDTags
from src.prompts.jd_tagger import (
    DOMAIN_STACK_ENVELOPE,
    DOMAIN_VOCAB,
    JD_TAGGER_SYSTEM,
    ROLE_VOCAB,
    envelope_for,
)

SAMPLE_JD = "Senior Backend Engineer. Own REST APIs and distributed systems."


def test_jd_tags_is_strict():
    """JDTags rejects unknown fields (extra='forbid')."""
    with pytest.raises(Exception):
        JDTags(role="backend", domains=[], bogus="nope")  # type: ignore[call-arg]


def test_jd_tags_requires_role_and_domains():
    with pytest.raises(Exception):
        JDTags(role="backend")  # type: ignore[call-arg]
    with pytest.raises(Exception):
        JDTags(domains=[])  # type: ignore[call-arg]


def test_vocab():
    assert set(ROLE_VOCAB) == {
        "backend",
        "frontend",
        "fullstack",
        "platform",
        "infra",
        "ml",
        "data",
        "mobile",
        "security",
        "product",
        "design",
    }
    assert set(DOMAIN_VOCAB) == {
        "ai",
        "fintech",
        "healthcare",
        "ecommerce",
        "realtime",
        "microservices",
        "distributed-systems",
        "devtools",
        "gaming",
        "crypto",
        "saas",
        "data-platform",
        "embedded",
        "infra-domain",
        "security-domain",
    }
    assert set(ROLE_VOCAB).isdisjoint(set(DOMAIN_VOCAB))


def test_classify_jd_type_returns_role_and_domains(monkeypatch):
    monkeypatch.setattr(
        jd_tagger,
        "parse_fast",
        lambda *a, **k: JDTags(role="product", domains=["ai"]),
    )
    result = jd_tagger.classify_jd_type(SAMPLE_JD)
    assert result == JdClassification(role="product", domains=["ai"])


def test_classify_jd_type_out_of_vocab_role_is_none(monkeypatch):
    monkeypatch.setattr(
        jd_tagger,
        "parse_fast",
        lambda *a, **k: JDTags(role="po", domains=["ai"]),
    )
    result = jd_tagger.classify_jd_type(SAMPLE_JD)
    assert result.role is None
    assert result.domains == ["ai"]


def test_classify_jd_type_domains_filters_dedupes_and_truncates_to_three(monkeypatch):
    monkeypatch.setattr(
        jd_tagger,
        "parse_fast",
        lambda *a, **k: JDTags(
            role="backend",
            domains=["ai", "not-a-real-domain", "fintech", "ai", "healthcare", "ecommerce"],
        ),
    )
    result = jd_tagger.classify_jd_type(SAMPLE_JD)
    assert result.role == "backend"
    assert result.domains == ["ai", "fintech", "healthcare"]


def test_classify_jd_type_model_error_returns_empty_classification(monkeypatch):
    def raise_error(*a, **k):
        raise ValueError("model exploded")

    monkeypatch.setattr(jd_tagger, "parse_fast", raise_error)
    result = jd_tagger.classify_jd_type(SAMPLE_JD)
    assert result == JdClassification(role=None, domains=[])


def test_classify_jd_type_all_out_of_vocab_domains_returns_empty_domains(monkeypatch):
    monkeypatch.setattr(
        jd_tagger,
        "parse_fast",
        lambda *a, **k: JDTags(role="backend", domains=["bogus", "also-bogus"]),
    )
    result = jd_tagger.classify_jd_type(SAMPLE_JD)
    assert result.role == "backend"
    assert result.domains == []


def test_classify_jd_type_passes_jd_raw_and_schema(monkeypatch):
    captured = {}

    def fake_parse_fast(system, user, schema, **kwargs):
        captured["system"] = system
        captured["user"] = user
        captured["schema"] = schema
        return JDTags(role="backend", domains=[])

    monkeypatch.setattr(jd_tagger, "parse_fast", fake_parse_fast)
    jd_tagger.classify_jd_type(SAMPLE_JD)

    assert captured["user"] == SAMPLE_JD
    assert captured["schema"] is JDTags
    assert captured["system"] == JD_TAGGER_SYSTEM


def test_prompt_lists_full_vocabulary():
    for role in ROLE_VOCAB:
        assert role in JD_TAGGER_SYSTEM
    for domain in DOMAIN_VOCAB:
        assert domain in JD_TAGGER_SYSTEM


def test_combined_tags_role_first_then_domains():
    result = JdClassification(role="backend", domains=["ai", "fintech"])
    assert result.combined_tags == ["backend", "ai", "fintech"]


def test_combined_tags_no_role_returns_domains_only():
    result = JdClassification(role=None, domains=["ai"])
    assert result.combined_tags == ["ai"]


def test_combined_tags_dedupes_defensively():
    result = JdClassification(role="backend", domains=["backend", "ai"])
    assert result.combined_tags == ["backend", "ai"]


# --- GAP 5: DOMAIN_STACK_ENVELOPE + envelope_for() ------------------------------


def test_every_domain_vocab_entry_has_a_stack_envelope():
    """Every DOMAIN_VOCAB member must have a non-empty allowlist - no domain is
    left ungoverned, or its fabrications would fall back to un-enforced vibes."""
    for domain in DOMAIN_VOCAB:
        assert domain in DOMAIN_STACK_ENVELOPE, f"{domain!r} missing from DOMAIN_STACK_ENVELOPE"
        assert len(DOMAIN_STACK_ENVELOPE[domain]) > 0, f"{domain!r} has an empty allowlist"


def test_domain_stack_envelope_has_no_extra_keys():
    """No stray keys outside DOMAIN_VOCAB - keeps the two vocabularies in lockstep."""
    assert set(DOMAIN_STACK_ENVELOPE.keys()) == set(DOMAIN_VOCAB)


def test_domain_stack_envelope_seeded_entries():
    assert set(DOMAIN_STACK_ENVELOPE["realtime"]) >= {
        "Kafka", "Redis", "WebSockets", "gRPC", "SSE", "message queues",
    }
    assert set(DOMAIN_STACK_ENVELOPE["microservices"]) >= {
        "Docker", "Kubernetes", "service mesh", "circuit breakers", "gRPC",
    }
    assert set(DOMAIN_STACK_ENVELOPE["fintech"]) >= {
        "idempotency keys", "audit logging", "double-entry", "reconciliation",
        "PCI-scoped services",
    }
    assert set(DOMAIN_STACK_ENVELOPE["data-platform"]) >= {
        "Airflow", "dbt", "CDC", "Parquet", "columnar stores", "partitioning",
    }
    assert set(DOMAIN_STACK_ENVELOPE["ai"]) >= {
        "RAG", "pgvector", "embeddings", "vector search", "LangChain", "model serving",
    }


def test_envelope_for_returns_deduplicated_union():
    result = envelope_for(["realtime", "microservices"])
    assert len(result) == len(set(result)), "envelope_for must not repeat any tool"
    # gRPC appears in both domains' allowlists - must appear exactly once.
    assert result.count("gRPC") == 1
    assert "Kafka" in result
    assert "Docker" in result


def test_envelope_for_empty_domains_returns_empty_tuple():
    assert envelope_for([]) == ()


def test_envelope_for_unknown_domain_is_ignored():
    assert envelope_for(["not-a-real-domain"]) == ()


def test_envelope_for_returns_tuple_type():
    assert isinstance(envelope_for(["ai"]), tuple)
