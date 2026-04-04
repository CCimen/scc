---
id: T03
parent: S01
milestone: M006-d622bc
key_files:
  - src/scc_cli/commands/launch/dependencies.py
  - src/scc_cli/commands/launch/flow.py
  - tests/test_provider_dispatch.py
key_decisions:
  - Used dict-based _PROVIDER_DISPATCH table for provider→adapter field mapping with claude fallback for unknown providers
  - Extracted _resolve_provider() helper to keep start() under 300-line guardrail
  - Normalized typer OptionInfo to None with isinstance check for direct-call test compatibility
duration: 
verification_result: passed
completed_at: 2026-04-04T23:10:53.930Z
blocker_discovered: false
---

# T03: Wired provider resolution into the launch path with dict-based adapter dispatch, team policy validation, and _resolve_provider helper extraction

**Wired provider resolution into the launch path with dict-based adapter dispatch, team policy validation, and _resolve_provider helper extraction**

## What Happened

Updated build_start_session_dependencies() to accept provider_id and dispatch the correct agent_provider from DefaultAdapters using a _PROVIDER_DISPATCH dict-based lookup table. Wired resolve_active_provider() into flow.py's start() before request building, extracting allowed_providers from team config. Extracted _resolve_provider() helper to keep start() under the 300-line guardrail. Added isinstance guard to normalize typer OptionInfo objects. Wrote 11 tests covering dispatch and policy validation.

## Verification

All 4529 tests pass (23 skipped, 2 xfailed). mypy clean on both modified files. ruff check clean. Function size guardrail passes (start() at 297 lines). Focused test run: 11/11 passed in test_provider_dispatch.py.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_provider_dispatch.py -v` | 0 | ✅ pass | 1300ms |
| 2 | `uv run mypy src/scc_cli/commands/launch/dependencies.py src/scc_cli/commands/launch/flow.py` | 0 | ✅ pass | 4400ms |
| 3 | `uv run ruff check` | 0 | ✅ pass | 4600ms |
| 4 | `uv run pytest --rootdir "$PWD" -q` | 0 | ✅ pass | 70300ms |

## Deviations

Extracted _resolve_provider() helper from start() (not in plan) to satisfy 300-line function size guardrail. Added isinstance(provider, str) guard to normalize typer OptionInfo defaults. Safety adapter dispatch recorded in table but not threaded into StartSessionDependencies (deferred to S04).

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/commands/launch/dependencies.py`
- `src/scc_cli/commands/launch/flow.py`
- `tests/test_provider_dispatch.py`
