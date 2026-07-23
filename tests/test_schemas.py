"""Tests for src.pipeline.schemas — Pydantic models and integrity guarantees."""
import json

from src.pipeline.schemas import (
    IdentityLedger,
    JDVector,
    PanelScore,
    ReframingTarget,
    ResumeRole,
    ResumeStruct,
    Role,
    RoleBullets,
    SkillWeight,
    WriterOutput,
)

ALL_MODELS = [
    Role,
    IdentityLedger,
    ResumeRole,
    ResumeStruct,
    SkillWeight,
    JDVector,
    ReframingTarget,
    RoleBullets,
    WriterOutput,
    PanelScore,
]

IDENTITY_KEYS = {"company", "title", "start", "end"}


def _make_role():
    return Role(company="Acme", title="Engineer", start="2020", end="2022")


def _make_ledger():
    return IdentityLedger(
        name="Jane Doe",
        contact="jane@example.com",
        roles=[_make_role(), Role(company="Beta", title="Lead", start="2022", end="2024")],
    )


def test_every_model_instantiates():
    assert _make_role().company == "Acme"
    assert _make_ledger().name == "Jane Doe"
    ResumeRole(
        company="Acme", title="Engineer", start="2020", end="2022",
        source_evidence=["Built X", "Shipped Y"],
    )
    ResumeStruct(
        roles=[ResumeRole(
            company="Acme", title="Engineer", start="2020", end="2022",
            source_evidence=["Built X"],
        )],
        education=["BS CS, MIT"],
        skills=["Python", "Go"],
    )
    SkillWeight(name="Python", weight=0.9)
    JDVector(
        weighted_skills=[SkillWeight(name="Python", weight=0.9)],
        ats_keywords=["Python", "REST"],
        seniority="senior",
        must_mirror=["distributed systems"],
    )
    ReframingTarget(
        competency="observability", weight=0.8, host_role_index=0,
        real_evidence=["Added logging"], framing_guidance="Emphasize scale",
        no_evidence=False,
    )
    RoleBullets(index=0, bullets=["Did a thing"])
    WriterOutput(
        roles=[RoleBullets(index=0, bullets=["Did a thing"])],
        skills=["Python"], summary="A summary.",
    )
    PanelScore(
        persona="skeptic", keyword_match=80, impact_quality=75,
        coherence=90, plausibility=85, formatting=70, notes="ok",
    )


def test_identity_ledger_round_trip_byte_stable():
    ledger = _make_ledger()
    dumped = ledger.model_dump()
    restored = IdentityLedger.model_validate(dumped)
    assert restored == ledger
    # JSON byte-stability
    assert json.dumps(ledger.model_dump(), sort_keys=True) == json.dumps(
        restored.model_dump(), sort_keys=True
    )


_SCHEMA_METADATA_KEYS = {"title", "description", "type", "default"}


def _property_names(obj) -> set:
    """Collect every declared property/field name in a JSON schema.

    Walks ``properties`` blocks (and ``$defs`` recursively). Deliberately does
    NOT treat JSON-schema metadata keys (``title``, ``description``, ...) as
    property names — those are annotations Pydantic emits for display, not
    fields a model can carry.
    """
    names: set = set()
    if isinstance(obj, dict):
        props = obj.get("properties")
        if isinstance(props, dict):
            names.update(props.keys())
        for k, v in obj.items():
            if k in _SCHEMA_METADATA_KEYS and not isinstance(v, (dict, list)):
                continue
            names.update(_property_names(v))
    elif isinstance(obj, list):
        for item in obj:
            names.update(_property_names(item))
    return names


def test_writer_output_has_no_identity_fields():
    """Integrity guarantee #1: WriterOutput cannot carry identity fields.

    No identity field (company/title/start/end) may appear as a declared
    property anywhere in the WriterOutput schema (including nested $defs).
    """
    schema = WriterOutput.model_json_schema()
    declared = _property_names(schema)
    leaked = IDENTITY_KEYS & declared
    assert not leaked, f"WriterOutput schema leaks identity fields: {leaked}"

    # Cross-check: a schema that DOES carry identity fields (ResumeRole) is
    # correctly detected by the same helper, proving the assertion has teeth.
    resume_role_props = _property_names(ResumeRole.model_json_schema())
    assert IDENTITY_KEYS <= resume_role_props


def _all_additional_properties_false(obj) -> list:
    """Collect every additionalProperties value found anywhere in the schema."""
    found = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "additionalProperties":
                found.append(v)
            found.extend(_all_additional_properties_false(v))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(_all_additional_properties_false(item))
    return found


def test_every_model_forbids_additional_properties():
    for model in ALL_MODELS:
        schema = model.model_json_schema()
        values = _all_additional_properties_false(schema)
        assert values, f"{model.__name__} schema exposes no additionalProperties"
        assert all(v is False for v in values), (
            f"{model.__name__} must set additionalProperties: false everywhere"
        )
