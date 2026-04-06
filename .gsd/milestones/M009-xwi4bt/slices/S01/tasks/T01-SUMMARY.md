---
id: T01
parent: S01
milestone: M009-xwi4bt
key_files:
  - src/scc_cli/commands/launch/preflight.py
  - src/scc_cli/commands/worktree/worktree_commands.py
  - src/scc_cli/ui/dashboard/orchestrator_handlers.py
  - tests/test_launch_preflight.py
  - tests/test_resume_after_drift.py
key_decisions:
  - Deferred import of get_agent_provider inside _ensure_auth() to satisfy D046 architecture guard
duration: 
verification_result: passed
completed_at: 2026-04-06T16:38:23.675Z
blocker_discovered: false
---

# T01: ensure_launch_ready() now calls provider.bootstrap_auth() after showing the auth notice, closing the silent auth gap in dashboard and worktree launch paths

**ensure_launch_ready() now calls provider.bootstrap_auth() after showing the auth notice, closing the silent auth gap in dashboard and worktree launch paths**

## What Happened

The _ensure_auth() helper in preflight.py showed an auth bootstrap notice via show_notice() but never called provider.bootstrap_auth(). Fixed by adding an adapters parameter to ensure_launch_ready() and _ensure_auth(), then calling get_agent_provider(adapters, provider_id).bootstrap_auth() after the notice in interactive mode. Exception handling mirrors auth_bootstrap.py: ProviderNotReadyError passes through, other exceptions get wrapped. Updated all three callers and all test files. Added three new tests proving bootstrap_auth is called, exceptions are wrapped, and ProviderNotReadyError passes through.

## Verification

uv run ruff check — passed. uv run mypy src/scc_cli — no issues in 303 files. uv run pytest tests/test_launch_preflight.py — 53 passed. uv run pytest tests/test_launch_preflight_guardrail.py — 7 passed. uv run pytest tests/test_resume_after_drift.py — 22 passed. uv run pytest — 5116 passed, 23 skipped, 2 xfailed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 5000ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 5000ms |
| 3 | `uv run pytest tests/test_launch_preflight.py -v` | 0 | ✅ pass | 1000ms |
| 4 | `uv run pytest tests/test_launch_preflight_guardrail.py -v` | 0 | ✅ pass | 2000ms |
| 5 | `uv run pytest tests/test_resume_after_drift.py -v` | 0 | ✅ pass | 1000ms |
| 6 | `uv run pytest` | 0 | ✅ pass | 66000ms |

## Deviations

Test mock patches use scc_cli.commands.launch.dependencies.get_agent_provider (definition site) rather than the consumer module path, because _ensure_auth uses a deferred import.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/commands/launch/preflight.py`
- `src/scc_cli/commands/worktree/worktree_commands.py`
- `src/scc_cli/ui/dashboard/orchestrator_handlers.py`
- `tests/test_launch_preflight.py`
- `tests/test_resume_after_drift.py`
