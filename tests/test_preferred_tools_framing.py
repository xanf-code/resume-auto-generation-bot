"""Tests for GAP 7 - preferred (not required) JD tools must get portable/
exposure-level framing, never a false primary claim.

A JD line like "cloud platforms (Azure preferred)" is a PREFERRED signal, not a
hard requirement. When the candidate's real depth is elsewhere (e.g. AWS-heavy),
both the Gap Analyzer and the Writer must avoid manufacturing a deep-
specialization claim on the preferred-but-absent tool - that collapses the
moment an interviewer asks "walk me through your Azure setup." The correct move
is portable/agnostic framing, a low-stakes adjacent detail (CI/CD or container
layer), or an explicit exposure-level claim.
"""
from src.prompts.extraction import GAP_SYSTEM
from src.prompts.writer import WRITER_SYSTEM


# --- GAP_SYSTEM (Gap Analyzer) ------------------------------------------------


def test_gap_system_distinguishes_preferred_from_required():
    assert "PREFERRED VS REQUIRED" in GAP_SYSTEM
    assert "hard-requirement band" in GAP_SYSTEM


def test_gap_system_forbids_deep_specialization_for_preferred_absent():
    assert "must NOT claim primary" in GAP_SYSTEM
    assert "deep specialization" in GAP_SYSTEM.lower()


def test_gap_system_preferred_absent_offers_portable_or_exposure_framing():
    lowered = GAP_SYSTEM.lower()
    assert "portable" in lowered
    assert "agnostic" in lowered
    assert "exposure" in lowered


def test_gap_system_preferred_absent_azure_worked_example():
    assert "Azure" in GAP_SYSTEM
    assert "AWS and Azure" in GAP_SYSTEM
    assert "AKS" in GAP_SYSTEM or "Azure DevOps" in GAP_SYSTEM


def test_gap_system_preferred_absent_real_evidence_states_defensive_intent():
    """real_evidence/framing_guidance must make the defensive intent explicit."""
    section_pos = GAP_SYSTEM.index("PREFERRED VS REQUIRED")
    strategy_pos = GAP_SYSTEM.index("STRATEGY - the Salesforce case extended")
    section = GAP_SYSTEM[section_pos:strategy_pos]
    assert "real_evidence" in section
    assert "framing_guidance" in section
    assert "Writer" in section


def test_gap_system_preferred_vs_required_ordering():
    """New rule sits after DUTY-VERB ANCHORING, before the worked STRATEGY example."""
    duty_pos = GAP_SYSTEM.index("DUTY-VERB ANCHORING")
    preferred_pos = GAP_SYSTEM.index("PREFERRED VS REQUIRED")
    strategy_pos = GAP_SYSTEM.index("STRATEGY - the Salesforce case extended")
    assert duty_pos < preferred_pos < strategy_pos


def test_gap_system_existing_contract_fields_untouched():
    assert "host_role_index" in GAP_SYSTEM
    assert "no_evidence: ALWAYS false" in GAP_SYSTEM
    assert "NEVER use -1" in GAP_SYSTEM
    assert "non-obvious implementation detail" in GAP_SYSTEM


# --- WRITER_SYSTEM rule 4 (Writer) -------------------------------------------


def _rule_4_block() -> str:
    start = WRITER_SYSTEM.index("4. For tools and technologies")
    end = WRITER_SYSTEM.index("5. Metrics")
    return WRITER_SYSTEM[start:end]


def test_writer_system_rule4_has_preferred_sub_rule():
    rule_4 = _rule_4_block()
    assert "PREFERRED" in rule_4
    assert "portable" in rule_4.lower() or "agnostic" in rule_4.lower()
    assert "exposure" in rule_4.lower()


def test_writer_system_rule4_never_frames_preferred_absent_as_primary():
    rule_4 = _rule_4_block()
    assert "NEVER" in rule_4
    assert "own" in rule_4.lower()


def test_writer_system_rule4_azure_worked_example():
    rule_4 = _rule_4_block()
    assert "Azure preferred" in rule_4
    assert "containerized services deployable across AWS and Azure" in rule_4
    assert "built and owned our Azure infrastructure" in rule_4.lower() or (
        "built and owned our azure infrastructure" in rule_4.lower()
    )


def test_writer_system_rule4_keeps_existing_guidance_intact():
    rule_4 = _rule_4_block()
    assert "framing_guidance" in rule_4
    assert '"Salesforce CRM platform" over bare "Salesforce"' in rule_4
    assert "Prioritize must_mirror phrases first" in rule_4


def test_writer_system_rule_numbering_untouched():
    assert "4. For tools and technologies" in WRITER_SYSTEM
    assert "5. Metrics" in WRITER_SYSTEM
    assert "6. Use strong action verbs" in WRITER_SYSTEM
