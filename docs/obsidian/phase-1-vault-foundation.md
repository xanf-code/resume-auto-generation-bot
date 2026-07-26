# Phase 1 - Vault foundation (config + notes I/O)

## Goal
A `src/vault/` package that knows where the vault is and can read/write Markdown notes with YAML
frontmatter. Everything is a **graceful no-op when the vault is disabled** (env unset / dir absent),
so no run ever breaks.

**Prereq:** none. **Blocks:** Phases 2, 4, 6, 8.

## Why
The learning brain is file-based. All later phases read/write vault notes; this phase provides the
single, tested I/O layer and the enable/disable switch, mirroring the existing config-object pattern
in `src/web/config.py` and `src/db/config.py`.

## Design
1. **`src/vault/config.py`** — `VaultSettings` (frozen): `dir: Path | None` from env
   `RESUME_VAULT_DIR` (default `<repo>/vault`), `enabled: bool` (true iff `dir` resolves to an
   existing/creatable directory). `VaultSettings.load()` classmethod. Absent/invalid → `enabled=False`.
2. **`src/vault/notes.py`** — thin, pure helpers over **`python-frontmatter`** (new dependency):
   - `read_note(path) -> Note` / `write_note(path, frontmatter: dict, body: str)` (atomic write).
   - `load_all_runs(settings) -> list[Note]` — iterate `runs/*.md`; `[]` when disabled.
   - `Note` exposes `.frontmatter: dict`, `.body: str`, `.path: Path`.
3. **Dependency** — add `python-frontmatter` to `pyproject.toml` (battle-tested; per "prefer libraries").
4. **`.gitignore`** — add `vault/` (data dir, not code).

## Tests (write first) — `tests/vault/test_notes.py`, `tests/vault/test_config.py`
- `write_note` → `read_note` round-trips frontmatter (incl. lists/nested) and body exactly.
- `VaultSettings.load()`: env set to a tmp dir → `enabled=True`; unset → `enabled=False`.
- `load_all_runs` returns notes sorted deterministically; **disabled → `[]`** (no filesystem touch).
- Atomic write leaves no partial file on simulated failure.

## Acceptance
- `pytest tests/vault/ -q` green.
- Importing `src.vault` has zero effect on the pipeline; CLI unchanged.

## Files
- `src/vault/__init__.py`, `src/vault/config.py`, `src/vault/notes.py` (new)
- `tests/vault/test_config.py`, `tests/vault/test_notes.py` (new)
- `pyproject.toml`, `.gitignore` (edit)
</content>
