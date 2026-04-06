---
id: T01
parent: S03
milestone: M008-g7jk8d
key_files:
  - tests/test_workspace_provider_persistence.py
key_decisions:
  - Verified all launch sites have correct finalize_launch guard by construction — no code changes needed
  - Worktree launch path intentionally does not persist workspace preference
duration: 
verification_result: passed
completed_at: 2026-04-06T13:31:29.593Z
blocker_discovered: false
---

# T01: Added 17 tests verifying workspace provider persistence edge cases: failed launch guard, KEEP_EXISTING consistency, and ask+last-used preselection

**Added 17 tests verifying workspace provider persistence edge cases: failed launch guard, KEEP_EXISTING consistency, and ask+last-used preselection**

## What Happened

Verified all four active launch sites (flow.py start, flow_interactive.py run_start_wizard_flow, orchestrator_handlers _handle_worktree_start, orchestrator_handlers _handle_session_resume) by code inspection — all place set_workspace_last_used_provider AFTER finalize_launch, so the guard is correct by construction. Created tests/test_workspace_provider_persistence.py with 17 tests across 5 classes covering: successful launch writes preference (with call ordering verification), failed launch skips preference write, cancelled launch skips preference, KEEP_EXISTING path writes preference without finalize_launch, and _resolve_prompt_default preselection behavior for ask+workspace_last_used scenarios.

## Verification

Task-level: uv run pytest tests/test_workspace_provider_persistence.py tests/test_start_provider_choice.py -v → 26 passed. Slice-level: uv run ruff check → clean, uv run mypy src/scc_cli → clean, uv run pytest -q → 5025 passed, 23 skipped, 2 xfailed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_workspace_provider_persistence.py tests/test_start_provider_choice.py -v` | 0 | ✅ pass | 1000ms |
| 2 | `uv run ruff check` | 0 | ✅ pass | 2900ms |
| 3 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 2900ms |
| 4 | `uv run pytest -q` | 0 | ✅ pass | 61400ms |

## Deviations

Initial test assumed prompt would fire with single connected provider; auto-single logic correctly bypasses prompt. Fixed test and added separate test for multi-candidate None-default scenario.

## Known Issues

None.

## Files Created/Modified

- `tests/test_workspace_provider_persistence.py`
