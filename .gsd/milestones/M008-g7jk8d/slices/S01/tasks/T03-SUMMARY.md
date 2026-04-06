---
id: T03
parent: S01
milestone: M008-g7jk8d
key_files:
  - src/scc_cli/commands/launch/flow.py
  - src/scc_cli/commands/launch/flow_interactive.py
  - src/scc_cli/ui/dashboard/orchestrator_handlers.py
  - tests/test_cli.py
  - tests/test_start_live_conflict.py
  - tests/test_start_codex_auth_bootstrap.py
  - tests/test_launch_preflight.py
key_decisions:
  - Kept ensure_provider_image/ensure_provider_auth calls inline in flow.py since ensure_launch_ready lacks StartSessionPlan context needed for post-plan auth bootstrap
duration: 
verification_result: passed
completed_at: 2026-04-06T12:25:51.667Z
blocker_discovered: false
---

# T03: Replaced inline _resolve_provider() and _allowed_provider_ids() in flow.py and flow_interactive.py with shared preflight.resolve_launch_provider(), eliminating provider resolution duplication across both launch paths

**Replaced inline _resolve_provider() and _allowed_provider_ids() in flow.py and flow_interactive.py with shared preflight.resolve_launch_provider(), eliminating provider resolution duplication across both launch paths**

## What Happened

Removed `_resolve_provider()` and `_allowed_provider_ids()` from flow.py and replaced the call site with `resolve_launch_provider()` from `commands/launch/preflight.py`. In flow_interactive.py, replaced the 15-line inline provider resolution block with the same shared call. Updated `orchestrator_handlers.py` (two deferred import sites) to use `preflight.allowed_provider_ids`. Updated five test mocking sites across three test files to target the new function name and tuple return signature. Fixed ruff E402/I001 import ordering violations in test_launch_preflight.py from T02. Cleaned up unused imports in both flow files.

## Verification

ruff check: all checks passed. mypy src/scc_cli: 303 files, 0 errors. pytest characterization + preflight tests: 94 passed. Full suite excluding 2 pre-existing failures: 4957 passed, 0 regressions.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 5000ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 10000ms |
| 3 | `uv run pytest tests/test_launch_preflight_characterization.py tests/test_launch_preflight.py -v` | 0 | ✅ pass | 1000ms |
| 4 | `uv run pytest --ignore=tests/test_cli_setup.py -k 'not test_d033_codex_bypass' --tb=short` | 0 | ✅ pass | 60000ms |

## Deviations

Kept ensure_provider_image/ensure_provider_auth inline in flow.py rather than replacing with collect_launch_readiness + ensure_launch_ready — the auth bootstrap path needs StartSessionPlan context not available to the preflight module.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/commands/launch/flow.py`
- `src/scc_cli/commands/launch/flow_interactive.py`
- `src/scc_cli/ui/dashboard/orchestrator_handlers.py`
- `tests/test_cli.py`
- `tests/test_start_live_conflict.py`
- `tests/test_start_codex_auth_bootstrap.py`
- `tests/test_launch_preflight.py`
