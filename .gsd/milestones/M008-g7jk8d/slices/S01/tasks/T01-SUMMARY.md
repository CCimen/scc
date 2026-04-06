---
id: T01
parent: S01
milestone: M008-g7jk8d
key_files:
  - tests/test_launch_preflight_characterization.py
key_decisions:
  - Document that 'ask' config suppresses workspace_last_used in resolve_provider_preference
duration: 
verification_result: passed
completed_at: 2026-04-06T12:02:15.875Z
blocker_discovered: false
---

# T01: 43 characterization tests capture provider resolution behavior across all five launch preflight sites and the WorkContext provider_id gap

**43 characterization tests capture provider resolution behavior across all five launch preflight sites and the WorkContext provider_id gap**

## What Happened

Wrote tests/test_launch_preflight_characterization.py with 43 tests in 8 classes. Each class maps to one launch site and documents its specific provider resolution behavior as a regression baseline. Key findings: (1) worktree_commands uses resolve_active_provider() directly with a hardcoded 'claude' default — no workspace_last_used, no connected probing, no ensure_provider_auth; (2) _record_session_and_context forwards provider_id to sessions.record_session() but not to WorkContext; (3) 'ask' config suppresses workspace_last_used entirely because the check precedes it in resolve_provider_preference.

## Verification

All 43 characterization tests pass. ruff check clean. mypy clean. Full pytest suite shows 4921 passed with 26 pre-existing failures in unrelated test_setup_wizard.py and test_start_dryrun.py.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_launch_preflight_characterization.py -v` | 0 | ✅ pass | 1000ms |
| 2 | `uv run ruff check` | 0 | ✅ pass | 1200ms |
| 3 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 75000ms |
| 4 | `uv run pytest` | 1 | ✅ pass (pre-existing failures only) | 68000ms |

## Deviations

Fixed one test assertion: initially assumed 'ask' + workspace_last_used would resolve, but actual code returns None before reaching workspace_last_used branch.

## Known Issues

None.

## Files Created/Modified

- `tests/test_launch_preflight_characterization.py`
