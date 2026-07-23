"""Mechanical identity tripwire — integrity guarantee #2.

``check_identity`` diffs rendered LaTeX against the ledger:

1. Every ``(company, title, start, end)`` value from every ledger role must
   appear VERBATIM in the rendered LaTeX, after applying the SAME escaping the
   renderer used. Missing values → the field was renamed/altered/dropped.
2. The number of role-header markers in the rendered LaTeX must EXACTLY equal
   the number of ledger roles. Extra markers → the writer smuggled in a role;
   fewer → a role was dropped.

Any violation returns ``ok=False`` with human-readable messages. The caller
hard-aborts the draft and bounces the violation text back to the writer.
"""
from src.compiler.renderer import ROLE_HEADER_MARKER, latex_escape
from src.pipeline.schemas import IdentityLedger


def check_identity(
    rendered_latex: str, ledger: IdentityLedger
) -> tuple[bool, list[str]]:
    """Verify rendered LaTeX faithfully reflects the locked ledger.

    Args:
        rendered_latex: The output of ``renderer.render``.
        ledger: The immutable identity source of truth.

    Returns:
        ``(ok, violations)`` — ``ok`` is True only when zero violations found.
    """
    violations: list[str] = []

    # (1) Every identity value must appear verbatim (post-escape).
    for idx, role in enumerate(ledger.roles):
        for field_name, raw_value in (
            ("company", role.company),
            ("title", role.title),
            ("start", role.start),
            ("end", role.end),
        ):
            escaped = latex_escape(raw_value)
            if escaped not in rendered_latex:
                violations.append(
                    f"Identity field missing/altered: role[{idx}].{field_name} "
                    f"= {raw_value!r} not found verbatim in rendered LaTeX."
                )

    # (2) No extra (or missing) role headers beyond the ledger's roles.
    expected_roles = len(ledger.roles)
    found_headers = rendered_latex.count(ROLE_HEADER_MARKER)
    if found_headers != expected_roles:
        if found_headers > expected_roles:
            violations.append(
                f"Extra role header(s) detected: found {found_headers} role "
                f"headers but ledger has {expected_roles}. The writer cannot "
                f"add a job that is not in the ledger."
            )
        else:
            violations.append(
                f"Missing role header(s): found {found_headers} role headers "
                f"but ledger has {expected_roles}."
            )

    return (len(violations) == 0, violations)
