---
id: T02
parent: S02
milestone: M008-g7jk8d
key_files:
  - src/scc_cli/commands/admin.py
  - src/scc_cli/commands/worktree/container_commands.py
  - tests/test_doctor_provider_errors.py
  - tests/test_docs_truthfulness.py
  - tests/test_lifecycle_inventory_consistency.py
key_decisions:
  - Docker Desktop references allowed only in docker/, adapters/, core/errors.py, doctor/
  - prune_cmd intentionally keeps broader image-based inventory for orphan cleanup
duration: 
verification_result: passed
completed_at: 2026-04-06T13:10:36.551Z
blocker_discovered: false
---

# T02: Removed Docker Desktop from active user-facing paths; added lifecycle inventory consistency and Docker Desktop boundary guardrails

**Removed Docker Desktop from active user-facing paths; added lifecycle inventory consistency and Docker Desktop boundary guardrails**

## What Happened

Fixed 2 Docker Desktop references in commands/ (admin.py error message and container_commands.py comment). Fixed 2 stale test assertions in test_doctor_provider_errors.py that T01 broke by changing wording without updating tests. Added Docker Desktop boundary guardrail to test_docs_truthfulness.py. Created 7-test lifecycle inventory consistency guardrail verifying command surfaces use correct inventory functions.

## Verification

All 5005 tests pass (0 failures, 23 skipped, 2 xfailed). Ruff check clean. Task-specific tests (39 in test_docs_truthfulness.py + test_lifecycle_inventory_consistency.py) all pass.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_docs_truthfulness.py tests/test_lifecycle_inventory_consistency.py -v` | 0 | ✅ pass | 6600ms |
| 2 | `uv run ruff check` | 0 | ✅ pass | 15100ms |
| 3 | `uv run pytest --tb=short` | 0 | ✅ pass | 60900ms |

## Deviations

Fixed 2 broken test assertions in test_doctor_provider_errors.py that were left stale by T01's wording change.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/commands/admin.py`
- `src/scc_cli/commands/worktree/container_commands.py`
- `tests/test_doctor_provider_errors.py`
- `tests/test_docs_truthfulness.py`
- `tests/test_lifecycle_inventory_consistency.py`
