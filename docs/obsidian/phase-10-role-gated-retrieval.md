# Phase 10 - Role-gated retrieval (retrieval gate)

## Goal
Change retrieval from "any tag overlap" to **hard-filter on `role`, then rank on `domains`**. Only
past wins whose `role` *exactly equals* the current run's `role` are eligible; among those, rank by
domain-tag Jaccard overlap, then `internal_score`, take top `k`. This is the *gate* half of the fix
for the production bad-match bug. Also updates the run-note frontmatter to record `role`/`domains`
and wires the split through the runner.

**Prereq:** Phase 9. **Blocks:** —. **Refines:** Phase 4.

## Why
The old overlap match let a Backend Engineer win leak into a Product Owner resume because they shared
`infra`+`platform`. Role is the job function — disagreeing on it means the win is simply irrelevant,
so it must be an **exclusion, not a demotion** (no partial credit). Domains are secondary flavor, so
they only *rank* within an already-correct role bucket. Deterministic Jaccard, no embeddings — same
philosophy as Phase 4.

## Design

### Retrieval — `src/vault/retrieval.py`
Old signature:
```python
def retrieve_examples(tags: Iterable[str], *, settings: VaultSettings, k: int = 3) -> str | None
```
New signature:
```python
def retrieve_examples(
    role: str | None, domains: Iterable[str], *, settings: VaultSettings, k: int = 3
) -> str | None
```

Logic:
- If `role is None` → return `None` immediately (an unclassifiable run has nothing to gate on; cold
  behaviour, writer runs as today).
- `domain_set = set(domains)`.
- For each note from `load_all_runs(settings)`:
  - `_resolve_outcome(note)` must be in `_WIN_OUTCOMES` (unchanged: `pending` >30d → `no_response`,
    excluded).
  - **Legacy-note exclusion (see below):** read `note.frontmatter.get("role")`. If it is missing/
    falsy, **skip the note** (legacy flat-`jd_type` notes are not eligible under the new gate).
  - **Hard role filter:** `note.frontmatter.get("role") == role` — else skip. Exact equality, no
    subset, no overlap.
  - Compute `score = (_jaccard(domain_set, note_domains), note.frontmatter.get("internal_score", 0))`
    where `note_domains = set(note.frontmatter.get("domains") or [])`.
  - Append `(jaccard, internal_score, note)`.
- If nothing eligible → `None`.
- Sort by `(jaccard, internal_score)` desc; take top `k`; format exactly as today
  (`_PROVEN_EXAMPLES_HEADER` + each note's `## Final bullets` block, joined by `\n\n`).

Add a pure helper:
```python
def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    return len(a & b) / len(union) if union else 0.0
```
Ranking is stable: two notes with equal `(jaccard, internal_score)` keep `load_all_runs` order
(filename sort) because Python's sort is stable — no tie-break flakiness.

### Legacy-note fallback (decision — justified)
**Rule: exclude any run note that has no `role` frontmatter field.** Legacy notes (the real
Vestwell/BCBS examples that predate this change) carry only the old flat `jd_type: [...]`. We do
**not** infer a `role` from that flat list. Justification: inferring `role` from the old flavor-mixed
list is exactly what produced the bad match in the first place (an `[ml, infra, platform]` note has
no reliable function signal). This is a single-user, low-volume tool; the win set naturally refreshes
as new role-tagged notes accumulate, and any note whose outcome the user still cares about can be
re-classified by hand (add `role:`/`domains:` in Obsidian). Simplicity and correctness beat
cleverness here. Retrieval **never crashes** on a legacy note — it is simply skipped.

### Run-note writer — `src/vault/writer.py`
`write_run_note` signature changes from `(job, final_state, tags, *, settings)` to
`(job, final_state, role, domains, *, settings)`:
```python
def write_run_note(
    job: Any, final_state: dict, role: str | None, domains: list[str], *, settings: VaultSettings
) -> Path | None
```
Frontmatter changes (everything else — `job_id`, `label`, `jd_name`, `created`, `internal_score`,
`passed`, `threshold_used`, `rubric_weights_used`, `bullet_shapes_used`, `learning_used`, `outcome`,
`outcome_date` — is unchanged and still preserves an existing note's `outcome`/`outcome_date`):
- Add `"role": role` (a string or `None`).
- Add `"domains": list(domains)`.
- Keep `"jd_type"` for human/Dataview display, derived as `[role, *domains]` when `role` is set,
  else `list(domains)` (dedupe defensively). This keeps existing dashboards/notes readable while
  `role`/`domains` become the machine source of truth for retrieval. (Do **not** drop `jd_type`;
  Phase 2's note contract and any dashboard queries still reference it.)

### Runner wiring — `src/web/runner.py` `run_job`
Replace the tags-based block (currently ~`runner.py:120-149`, `216`) with the role/domains split:
```python
vault_settings = VaultSettings.load()
classification = classify_jd_type(job.jd_raw)   # Phase 9: JdClassification; never raises
job.role = classification.role
job.domains = classification.domains

proven_examples: str | None = None
tuning = job.tuning
if job.obsidian_learn:
    try:
        proven_examples = retrieve_examples(
            classification.role, classification.domains, settings=vault_settings
        )
        if vault_settings.enabled:
            manager._emit(job, _vault_retrieval_event(job, classification, found=proven_examples is not None))
        # Loop B UNCHANGED: resolve_tuning still takes one flat list. combined_tags = [role, *domains].
        tuning, diff = resolve_tuning(classification.combined_tags, job.tuning, settings=vault_settings)
        if diff:
            manager._emit(job, _tuning_diff_event(job, classification.combined_tags, diff))
    except Exception:
        log.exception("Vault retrieval/tuning failed for job %s - continuing without", job.job_id)
        proven_examples, tuning = None, job.tuning
...
# success path, replacing write_run_note(job, final_state, tags, ...):
note_path = write_run_note(
    job, final_state, classification.role, classification.domains, settings=vault_settings
)
```
- `_vault_retrieval_event` / `_tuning_diff_event` helpers: update their `tags` param. Simplest is to
  keep passing a flat label — pass `classification.combined_tags` for the tuning-diff event (label
  unchanged) and pass `classification` (or its `combined_tags`) to the retrieval event so the
  `[tag_label]` detail still renders. Keep the event `stage`/`pct`/`human_label` values identical so
  the frontend and existing event-stream assertions don't move.

### Constraint validation — `resolve_tuning` is NOT touched (VALIDATED)
Confirmed against `src/vault/tuning.py` and `tests/vault/test_tuning_resolver.py`: `resolve_tuning`
takes `tags: list[str]`, and `_best_match` matches a `+`-joined key iff `set(key.split("+")) <=
set(tags)`. Feeding `combined_tags = [role, *domains]` is a **flat superset**, exactly like the old
combined list — subset matching is order-independent and role-vs-domain-agnostic, so every existing
`by_tag` key (`"backend"`, `"backend+senior"`, etc.) still resolves identically. No change to
`tuning.py` or `tests/vault/test_tuning_resolver.py` is required. The only care point: `by_tag` keys
authored by the Phase 8 proposer will now be drawn from the union of `ROLE_VOCAB ∪ DOMAIN_VOCAB`
rather than the old flat vocab, but that is data, not code, and Phase 8's grouping is out of scope
here.

## Tests (write first)

### `tests/vault/test_retrieval.py` (rewrite the `tags`-based tests)
Helper `_note(...)` gains `role=` and `domains=` params (drop/keep `jd_type` — set both for realism).
Update all call sites to pass `role`/`domains` to `retrieve_examples`.
- **Win-only filter** still holds: `rejected`/`no_response`/stale-`pending` excluded;
  `interview`/`offer` included (role must match).
- **Hard role filter:** a win with `role="backend"` is **excluded** when querying `role="product"`,
  even if `domains` fully overlap (this is the bug's regression test — name it explicitly, e.g.
  `test_role_mismatch_excluded_even_with_full_domain_overlap`).
- **Role match required:** querying `role=None` → `None` regardless of notes present.
- **Domain ranking within a role bucket:** three `role="backend"` wins with domains
  `{ai,fintech}` / `{ai}` / `{}` queried against `{ai,fintech}` rank by Jaccard desc; assert order
  and that `internal_score` breaks ties (two equal-Jaccard notes ordered by score).
- **`k` respected** within the role bucket.
- **Legacy-note exclusion:** a winning note with `jd_type=["backend"]` and **no `role` field** is
  excluded (does not crash, does not match) when querying `role="backend"`.
- **Stale `pending` >30d** still excluded (unchanged path).
- **Cold start / disabled vault** → `None`.
- **Labelled header** unchanged: output starts with `## PROVEN EXAMPLES (bullets that earned...`.
- `_jaccard` unit cases: disjoint → 0.0; identical non-empty → 1.0; both empty → 0.0;
  partial → correct ratio.

### `tests/vault/test_writer.py` (adapt to the new signature)
- Update `write_run_note(job, state, role, domains, settings=...)` at all call sites.
- Frontmatter now has `role` (string or `None`) and `domains` (list); `jd_type` derived as
  `[role, *domains]` (assert e.g. `role="backend", domains=["ai"]` → `jd_type == ["backend","ai"]`).
- `role=None, domains=[]` → `role` is `None`, `domains == []`, `jd_type == []`.
- All existing invariants (bullets verbatim, outcome preservation on rewrite, slug stability,
  latex-fallback, disabled→`None`) unchanged.

### `tests/web/test_runner_vault.py` (adapt to Phase 9 return + Phase 10 args)
- All `patch.object(runner_module, "classify_jd_type", return_value=["backend"])` become
  `return_value=JdClassification(role="backend", domains=[])` (import `JdClassification`).
- `_seed_winning_backend_notes` writes `role: "backend"`, `domains: []` (plus legacy `jd_type` if
  desired) so the seeded wins pass the new role gate.
- Assertions `job.jd_type == ["backend"]` become `job.role == "backend"` and `job.domains == []`.
- Note-frontmatter assertions read `note.frontmatter["role"]` / `["domains"]`.
- Learn-ON still asserts the seeded bullet reaches `captured["proven_examples"]` and the tuning
  override (`threshold == 91`) still applies — proving `combined_tags` keeps Loop B working.
- Add one integration test: a seeded **product** win + a seeded **backend** win; run a `product` JD
  → `proven_examples` contains only the product win's bullet, never the backend one.
- Retrieval error / write-note error / disabled-vault paths: adapt argument shapes only; behaviour
  (run never fails, tags still computed) unchanged.

### `tests/web/conftest.py` (MUST update — flagged)
The autouse fixture `_no_real_jd_tagging` currently sets
`src.web.runner.classify_jd_type` to `lambda jd_raw: []`. That return type is now wrong (`run_job`
calls `.role` / `.domains` / `.combined_tags` on it). Change it to return a neutral classification:
```python
from src.agents.jd_tagger import JdClassification
monkeypatch.setattr("src.web.runner.classify_jd_type",
                    lambda jd_raw: JdClassification(role=None, domains=[]))
```
This keeps every existing manager-driven web test hermetic while satisfying the new attribute access.

## Acceptance
- `pytest tests/vault/test_retrieval.py tests/vault/test_writer.py tests/web/test_runner_vault.py -q`
  green.
- `pytest tests/ -q` green overall, incl. `tests/vault/test_tuning_resolver.py` **unchanged**
  (proves the "don't touch `resolve_tuning`" constraint held).
- Vault remains a no-op when `RESUME_VAULT_DIR` is unset; CLI unchanged.
- Manual: a Product Owner JD no longer retrieves Backend Engineer bullets; a same-role JD with
  overlapping domains ranks the closest-domain win first.

## Files
- `src/vault/retrieval.py` (edit: new signature, role hard-filter, `_jaccard` ranking, legacy skip)
- `src/vault/writer.py` (edit: new signature, `role`/`domains` frontmatter, derived `jd_type`)
- `src/web/runner.py` (edit: consume `JdClassification`, split retrieval args, `combined_tags` →
  `resolve_tuning`, new `write_run_note` args; visibility-event helper params)
- `tests/vault/test_retrieval.py`, `tests/vault/test_writer.py`, `tests/web/test_runner_vault.py`
  (rewrite/adapt)
- `tests/web/conftest.py` (edit: fixture returns `JdClassification`)
- **Unchanged (validated):** `src/vault/tuning.py`, `tests/vault/test_tuning_resolver.py`
</content>
