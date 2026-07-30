"""Tests for GAP_SYSTEM's plausibility-signal mandate (GAP 2).

Every ``framing_guidance`` the Gap Analyzer emits must supply a non-obvious
implementation detail - the signal that separates a defensible reframe from a
bare keyword sprinkle. This is enforced at the prompt level: the spec for the
field states the requirement, the anti-pattern is stated plainly, and the
Salesforce worked example models the bar rather than just describing it.
"""
from src.prompts.extraction import GAP_SYSTEM


def test_gap_system_mandates_non_obvious_detail_in_framing_guidance():
    assert "non-obvious implementation detail" in GAP_SYSTEM
    assert "partition key" in GAP_SYSTEM
    assert "idempotency" in GAP_SYSTEM.lower()
    assert "scaling bound" in GAP_SYSTEM


def test_gap_system_states_anti_pattern():
    assert "INSUFFICIENT" in GAP_SYSTEM
    assert "must be rewritten before" in GAP_SYSTEM


def test_gap_system_salesforce_example_carries_concrete_detail():
    """The STRONG worked example must model the bar, not just name Salesforce."""
    assert "external ID" in GAP_SYSTEM
    assert "duplicate" in GAP_SYSTEM.lower()

    strategy_pos = GAP_SYSTEM.index("STRATEGY - the Salesforce case extended")
    detail_pos = GAP_SYSTEM.index("external ID")
    assert strategy_pos < detail_pos, "concrete detail must live inside the worked example"


def test_gap_system_existing_hard_rules_untouched():
    """Framing-target contract fields must remain intact."""
    assert "host_role_index" in GAP_SYSTEM
    assert "no_evidence: ALWAYS false" in GAP_SYSTEM
    assert "NEVER use -1" in GAP_SYSTEM
