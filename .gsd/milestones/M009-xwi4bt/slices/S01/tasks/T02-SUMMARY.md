---
id: T02
parent: S01
milestone: M009-xwi4bt
key_files:
  - src/scc_cli/commands/launch/flow.py
  - src/scc_cli/commands/launch/flow_interactive.py
  - tests/test_launch_preflight_guardrail.py
  - tests/test_start_codex_auth_bootstrap.py
  - tests/test_workspace_provider_persistence.py
  - tests/test_cli.py
  - tests/test_launch_preflight_characterization.py
key_decisions:
  - Readiness check before plan construction (not after conflict resolution) to match dashboard/worktree pattern
  - Resume path skips readiness entirely since original session already authenticated
  - Dry-run path skips readiness entirely since no image/auth needed for preview
duration: 
verification_result: passed
completed_at: 2026-04-06T16:49:02.313Z
blocker_discovered: false
---

# T02: Replaced inline ensure_provider_image + ensure_provider_auth calls in flow.py and flow_interactive.py with shared preflight readiness path, completing the migration of all five launch sites

**Replaced inline ensure_provider_image + ensure_provider_auth calls in flow.py and flow_interactive.py with shared preflight readiness path, completing the migration of all five launch sites**

## What Happened

Removed ensure_provider_image and ensure_provider_auth imports and inline calls from both flow.py (start command) and flow_interactive.py (interactive wizard). Replaced them with collect_launch_readiness() + ensure_launch_ready() from preflight.py, placed after provider resolution but before plan construction. This matches the pattern already established by dashboard and worktree launch paths. Resume and dry-run paths skip readiness entirely. Updated guardrail test to ban the old functions from migrated files. Updated six test files to mock the new preflight functions.

## Verification

uv run ruff check — all checks passed. uv run mypy src/scc_cli — no issues in 303 source files. uv run pytest — 5117 passed, 23 skipped, 2 xfailed. grep confirms ensure_provider_image and ensure_provider_auth are absent from both flow.py and flow_interactive.py.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 7300ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 7800ms |
| 3 | `uv run pytest tests/test_launch_preflight_guardrail.py tests/test_start_codex_auth_bootstrap.py tests/test_workspace_provider_persistence.py -v` | 0 | ✅ pass | 9700ms |
| 4 | `uv run pytest tests/test_cli.py tests/test_launch_preflight_characterization.py -v` | 0 | ✅ pass | 6700ms |
| 5 | `uv run pytest` | 0 | ✅ pass | 62150ms |

## Deviations

Readiness check placed before plan construction rather than after conflict resolution. This is a deliberate improvement that fails faster and avoids unnecessary plan construction when provider isn't ready.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/commands/launch/flow.py`
- `src/scc_cli/commands/launch/flow_interactive.py`
- `tests/test_launch_preflight_guardrail.py`
- `tests/test_start_codex_auth_bootstrap.py`
- `tests/test_workspace_provider_persistence.py`
- `tests/test_cli.py`
- `tests/test_launch_preflight_characterization.py`
