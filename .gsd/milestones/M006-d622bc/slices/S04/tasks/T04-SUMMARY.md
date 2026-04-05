---
id: T04
parent: S04
milestone: M006-d622bc
key_files:
  - tests/test_provider_coexistence.py
  - tests/test_doctor_image_check.py
  - tests/test_provider_machine_readable.py
key_decisions:
  - Test coexistence at the data-structure level rather than requiring Docker — fast, deterministic, proves hash/naming isolation
duration: 
verification_result: passed
completed_at: 2026-04-05T01:20:48.443Z
blocker_discovered: false
---

# T04: Created 16 coexistence proof tests and passed zero-regression gate (4643 tests, 0 failures, ruff clean, mypy clean)

**Created 16 coexistence proof tests and passed zero-regression gate (4643 tests, 0 failures, ruff clean, mypy clean)**

## What Happened

Created tests/test_provider_coexistence.py with 16 tests in 5 classes proving Claude and Codex containers, volumes, config dirs, sessions, and SandboxSpec fields don't collide for the same workspace. Fixed 3 inherited ruff lint errors in test_doctor_image_check.py and test_provider_machine_readable.py. Full regression suite passes with 4643 tests.

## Verification

All 7 verification checks pass: coexistence tests (16/16), ruff check (clean), mypy (292 files, no issues), full regression (4643 passed), plus all 3 slice-level checks (session provider_id tests, targeted ruff, targeted mypy).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_provider_coexistence.py -v --no-cov` | 0 | ✅ pass | 5400ms |
| 2 | `uv run ruff check` | 0 | ✅ pass | 5400ms |
| 3 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 69000ms |
| 4 | `uv run pytest --rootdir "$PWD" -q --no-cov` | 0 | ✅ pass | 63000ms |
| 5 | `uv run pytest tests/test_session_provider_id.py -v --no-cov` | 0 | ✅ pass | 4000ms |
| 6 | `uv run ruff check src/scc_cli/ports/session_models.py src/scc_cli/sessions.py src/scc_cli/commands/launch/flow_session.py` | 0 | ✅ pass | 2000ms |
| 7 | `uv run mypy src/scc_cli/ports/session_models.py src/scc_cli/sessions.py src/scc_cli/commands/launch/flow_session.py` | 0 | ✅ pass | 5000ms |

## Deviations

Fixed 3 ruff lint errors from prior S04 tasks (unused import pytest in two files, unused mock_git variable) that were causing ruff check to fail.

## Known Issues

None.

## Files Created/Modified

- `tests/test_provider_coexistence.py`
- `tests/test_doctor_image_check.py`
- `tests/test_provider_machine_readable.py`
