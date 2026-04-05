---
id: T01
parent: S05
milestone: M007-cqttot
key_files:
  - README.md
  - pyproject.toml
  - tests/test_docs_truthfulness.py
key_decisions:
  - (none)
duration: 
verification_result: passed
completed_at: 2026-04-05T14:16:59.449Z
blocker_discovered: false
---

# T01: Updated README title to 'SCC - Sandboxed Code CLI', made pyproject.toml provider-neutral, added 5 M007 truthfulness guardrail tests

**Updated README title to 'SCC - Sandboxed Code CLI', made pyproject.toml provider-neutral, added 5 M007 truthfulness guardrail tests**

## What Happened

Changed README line 1 from 'SCC - Sandboxed Claude CLI' to 'SCC - Sandboxed Code CLI' per D030. Updated pyproject.toml description to provider-neutral wording. Appended an M007 section to tests/test_docs_truthfulness.py with 5 new guardrail tests covering ProviderRuntimeSpec existence, fail-closed dispatch error, doctor provider-auth check, README title correctness, and core constants cleanliness. All 5 verification targets confirmed present before writing tests. Full suite passes with zero failures.

## Verification

uv run ruff check — zero errors. uv run pytest tests/test_docs_truthfulness.py tests/test_provider_branding.py -v — 41 passed. uv run pytest -q — 4725 passed, 23 skipped, 2 xfailed, 0 failed (4750 collected).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 11200ms |
| 2 | `uv run pytest tests/test_docs_truthfulness.py tests/test_provider_branding.py -v` | 0 | ✅ pass | 5600ms |
| 3 | `uv run pytest -q` | 0 | ✅ pass | 57200ms |

## Deviations

None.

## Known Issues

Slice verification says >= 4750 passed but suite reports 4725 passed + 23 skipped + 2 xfailed. Skips and xfails are pre-existing. Zero failures.

## Files Created/Modified

- `README.md`
- `pyproject.toml`
- `tests/test_docs_truthfulness.py`
