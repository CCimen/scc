---
id: T02
parent: S05
milestone: M003
key_files:
  - tests/test_docs_truthfulness.py
key_decisions:
  - Used regex for string-literal and README scanning (sufficient for content matching), tokenize pattern reserved for code identifier scanning
  - Validated example JSON network_policy values against canonical NetworkPolicy enum to prevent drift
duration: 
verification_result: passed
completed_at: 2026-04-04T11:06:43.966Z
blocker_discovered: false
---

# T02: Added 5 guardrail tests in test_docs_truthfulness.py preventing stale network-mode vocabulary and README truthfulness regression

**Added 5 guardrail tests in test_docs_truthfulness.py preventing stale network-mode vocabulary and README truthfulness regression**

## What Happened

Created tests/test_docs_truthfulness.py with 5 test functions that scan source blocked_by strings, command warning messages, README claims, and example JSON files for stale network-mode vocabulary (unrestricted, corp-proxy-only, corp-proxy, isolated) and Docker Desktop hard-dependency violations. Tests import the canonical NetworkPolicy enum from scc_cli.core.enums for membership validation. All 5 tests pass against the T01-fixed codebase. Full exit gate passes: ruff clean, mypy clean, 3464 total tests.

## Verification

All 5 new tests pass (uv run pytest tests/test_docs_truthfulness.py -v). Ruff check clean, mypy 0 issues in 249 files. Full suite: 3437 passed + 23 skipped + 4 xfailed = 3464 total (≥3464 threshold met). All 5 slice-level verification checks pass.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest --rootdir "$PWD" tests/test_docs_truthfulness.py -v` | 0 | ✅ pass | 820ms |
| 2 | `uv run ruff check` | 0 | ✅ pass | 4000ms |
| 3 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4000ms |
| 4 | `uv run pytest --rootdir "$PWD" -q (full suite, 3464 total)` | 0 | ✅ pass | 40310ms |
| 5 | `Slice verification: all 5 checks pass (config_explain tests, no stale isolated/corp-proxy-only/unrestricted, no Docker Desktop hard req)` | 0 | ✅ pass | 2320ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `tests/test_docs_truthfulness.py`
