# Phase 3 - JD tagging

## Goal
Classify a raw JD into a small, controlled set of `jd_type` tags via one fast LLM call. Tags drive
retrieval matching (Phase 4) and tuning segmentation (Phase 6), and are recorded on every note.

**Prereq:** none. **Blocks:** Phase 7.

## Why
"Similar role" needs no embeddings at this volume — tag overlap is enough. A **controlled
vocabulary** keeps tags consistent enough to match on. This reuses the existing fast-model plumbing
(`parse_fast`, `MODEL_FAST`) — no new infrastructure.

## Design
1. **`src/prompts/jd_tagger.py`** — `JD_TAGGER_SYSTEM`: instruct the model to return 1–3 tags **only**
   from a fixed vocabulary, e.g. `backend, frontend, fullstack, ml, data, platform, infra, mobile,
   security, pm`. Define `JD_TYPE_VOCAB: tuple[str, ...]`.
2. **`src/pipeline/schemas.py`** — `class JDTags(BaseModel)` (`model_config = _STRICT`): `tags: list[str]`.
3. **`src/agents/jd_tagger.py`** — `classify_jd_type(jd_raw: str) -> list[str]`:
   `parse_fast(JD_TAGGER_SYSTEM, jd_raw, JDTags)`; drop any tag not in `JD_TYPE_VOCAB`; dedupe,
   preserve order. On any error → `[]` (never fails the run).

## Tests (write first) — `tests/test_jd_tagger.py`
- `JDTags` is strict (rejects unknown fields).
- `classify_jd_type` filters out-of-vocab tags and dedupes (monkeypatch `parse_fast` to return a
  scripted `JDTags`).
- Empty / error from the model → `[]`.
- Prompt text lists the full vocabulary.

## Acceptance
- `pytest tests/test_jd_tagger.py -q` green.
- No import cycle; `classify_jd_type` callable standalone.

## Files
- `src/prompts/jd_tagger.py`, `src/agents/jd_tagger.py` (new)
- `src/pipeline/schemas.py` (edit: add `JDTags`)
- `tests/test_jd_tagger.py` (new)
</content>
