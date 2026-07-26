# Phase 9 - Role/Domain tagger split (emitter)

## Goal
Replace the single flat `jd_type` classification with two **orthogonal** fields: a single, exclusive
`role` (the job function) and a list of secondary `domains` (tech/industry flavor). This is the
*emitter* half of the fix for the production bad-match bug (an "AI Product Owner" JD tagged
`[ml, infra, platform]` matched a Backend Engineer win on shared `infra`+`platform`).

**Prereq:** none. **Blocks:** Phase 10. **Refines:** Phase 3.

## Why
The old flat vocabulary conflated *what the job is* (function) with *what tech/industry it touches*
(flavor). Retrieval then matched on flavor while disagreeing on function. Splitting the two lets
Phase 10 **hard-filter on `role`** (never match a Product Owner against a Backend Engineer) and only
**rank on `domains`**. Exactly one `role` per JD makes the filter a clean equality test — no partial
credit, no embeddings. Reuses the existing `parse_fast`/`MODEL_FAST` plumbing; no new infrastructure.

## Design

### Vocabularies — `src/prompts/jd_tagger.py`
Replace `JD_TYPE_VOCAB` with two closed tuples:

```python
ROLE_VOCAB: tuple[str, ...] = (
    "backend", "frontend", "fullstack", "platform", "infra",
    "ml", "data", "mobile", "security", "product", "design",
)

DOMAIN_VOCAB: tuple[str, ...] = (
    "ai", "fintech", "healthcare", "ecommerce", "realtime",
    "microservices", "distributed-systems", "devtools", "gaming",
    "crypto", "saas", "data-platform", "embedded", "infra-domain",
    "security-domain",
)
```

- `ROLE_VOCAB` is the **job function** (mutually exclusive; exactly one is chosen). `product` replaces
  the old `pm` and covers PM / Product Owner / Product Manager. `design` is added as a distinct
  function. All other members carry over from the old flat vocab.
- `DOMAIN_VOCAB` is tech/industry **flavor** (0–3 chosen). Note `infra-domain` / `security-domain`
  exist so a *backend role at an infra/security company* can carry that flavor **without** stealing
  the `role` slot from `infra`/`security` proper. Keep `DOMAIN_VOCAB` a closed set (filter out
  anything else), matching the deterministic, no-embeddings design philosophy.

### Prompt — `src/prompts/jd_tagger.py`
Rewrite `JD_TAGGER_SYSTEM` to instruct the model to return **exactly one** `role` from `ROLE_VOCAB`
and **0–3** `domains` from `DOMAIN_VOCAB`. It must:
1. List the full `ROLE_VOCAB` and full `DOMAIN_VOCAB` inline (verbatim members).
2. State: `role` = the primary job **function** (what the person *does*), chosen even if the JD is
   ambiguous — pick the single best fit; a product/ownership role is `product`, not the engineering
   flavor of the product. `domains` = secondary tech/industry flavor only, never the function.
3. Return only the structured object, no commentary.

### Schema — `src/pipeline/schemas.py`
Replace `class JDTags` (keep the name; it is imported by `jd_tagger.py` and its tests). New shape,
`model_config = _STRICT`, mirroring `JDVector` conventions (plain fields, no ge/le):

```python
class JDTags(BaseModel):
    """The JD Tagger's role/domain classification of a raw JD."""
    model_config = _STRICT
    role: str
    domains: list[str]
```

### Result carrier — `src/agents/jd_tagger.py`
Introduce a small immutable result type so callers get both fields with one call. Add above
`classify_jd_type`:

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class JdClassification:
    role: str | None            # exactly one ROLE_VOCAB member, or None on failure/out-of-vocab
    domains: list[str] = field(default_factory=list)  # deduped, in-vocab, order-preserved, ≤3

    @property
    def combined_tags(self) -> list[str]:
        """Flat tag list for Loop B tuning (`[role, *domains]`); role first, deduped."""
        tags = [self.role] if self.role else []
        for d in self.domains:
            if d not in tags:
                tags.append(d)
        return tags
```

New signature (was `classify_jd_type(jd_raw: str) -> list[str]`):

```python
def classify_jd_type(jd_raw: str) -> JdClassification:
```

Logic:
- `result = parse_fast(JD_TAGGER_SYSTEM, jd_raw, JDTags)` (unchanged call).
- `role`: take `result.role` iff it is in `ROLE_VOCAB`, else `None`.
- `domains`: keep only members of `DOMAIN_VOCAB`, dedupe preserving order, **truncate to 3**.
- On any exception → `JdClassification(role=None, domains=[])` (never fails the run).

The `combined_tags` property is the single seam that keeps Phase 6 `resolve_tuning` **untouched**
(see the constraint note in Phase 10): the runner feeds `classification.combined_tags` to
`resolve_tuning`, which still receives one flat `list[str]` and matches subsets exactly as before.

### Threading forward (specified here, wired in Phase 10)
- `src/web/job.py` `Job`: replace `jd_type: list[str] | None = None` with two fields —
  `role: str | None = None` and `domains: list[str] = field(default_factory=list)`. The run note's
  human-facing `jd_type` display value is derived at write time as `combined_tags`
  (`[role, *domains]`), so no separate `job.jd_type` field is needed.

## Tests (write first) — `tests/test_jd_tagger.py`
Rewrite the existing suite against the new contract (`parse_fast` monkeypatched; NO live calls):
- `JDTags` is strict: rejects unknown fields; requires both `role` and `domains`.
- `test_vocab` (replaces `test_vocab_matches_expected_set`): `ROLE_VOCAB` equals the exact 11-member
  set above; `DOMAIN_VOCAB` equals the exact set above; the two are disjoint on shared spellings
  (e.g. `infra` in roles vs `infra-domain` in domains).
- `classify_jd_type` returns a `JdClassification` with `role="product"`, `domains=["ai"]` when the
  model returns `JDTags(role="product", domains=["ai"])`.
- Out-of-vocab `role` (e.g. `"po"`) → `role=None`.
- `domains` filters out-of-vocab entries, dedupes preserving order, and **truncates to 3**
  (feed 5 valid domains → assert length 3, first-three-by-order).
- Model error / exception → `JdClassification(role=None, domains=[])`.
- `combined_tags`: `role="backend", domains=["ai","fintech"]` → `["backend","ai","fintech"]`;
  `role=None, domains=["ai"]` → `["ai"]`; dedupe when a domain equals the role spelling is a no-op
  here (disjoint vocabs) but the property still de-dupes defensively.
- `classify_jd_type` passes `jd_raw`, `JDTags`, and `JD_TAGGER_SYSTEM` through to `parse_fast`
  (keep the existing capture test, adapted).
- Prompt text lists every `ROLE_VOCAB` and every `DOMAIN_VOCAB` member.

## Acceptance
- `pytest tests/test_jd_tagger.py -q` green.
- `classify_jd_type` callable standalone; no import cycle.
- `JdClassification.combined_tags` produces a flat list byte-compatible with what old callers passed
  to `resolve_tuning` (a `list[str]` of controlled tags).

## Files
- `src/prompts/jd_tagger.py` (edit: `ROLE_VOCAB`, `DOMAIN_VOCAB`, rewrite `JD_TAGGER_SYSTEM`; remove
  `JD_TYPE_VOCAB`)
- `src/pipeline/schemas.py` (edit: replace `JDTags` fields)
- `src/agents/jd_tagger.py` (edit: `JdClassification`, new `classify_jd_type` signature/logic)
- `src/web/job.py` (edit: `Job.role` / `Job.domains` fields — the wiring that *uses* them is Phase 10)
- `tests/test_jd_tagger.py` (rewrite against the new contract)
</content>
</invoke>
