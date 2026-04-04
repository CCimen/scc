---
id: T02
parent: S04
milestone: M002
key_files:
  - src/scc_cli/commands/launch/dependencies.py
  - src/scc_cli/bootstrap.py
  - src/scc_cli/commands/launch/flow.py
  - src/scc_cli/commands/worktree/worktree_commands.py
  - tests/fakes/__init__.py
  - tests/conftest.py
  - tests/test_bootstrap.py
  - tests/test_cli.py
  - tests/test_integration.py
  - .gsd/KNOWLEDGE.md
key_decisions:
  - Kept `bootstrap.py` as the only adapter composition root and exposed the durable audit sink there instead of importing adapters directly from command modules.
  - Centralized live launch wiring in `src/scc_cli/commands/launch/dependencies.py` so large command files reuse one dependency/plan builder instead of recreating `StartSessionDependencies` inline.
  - Made worktree auto-start derive its team from `selected_profile` and go through `finalize_launch(...)` so org-policy preflight and JSONL audit behave the same as direct start.
duration: 
verification_result: passed
completed_at: 2026-04-03T20:25:45.464Z
blocker_discovered: false
---

# T02: Wired direct start and worktree auto-start through one shared preflight and audit dependency builder.

**Wired direct start and worktree auto-start through one shared preflight and audit dependency builder.**

## What Happened

Added `src/scc_cli/commands/launch/dependencies.py` to centralize live launch dependency construction and shared plan preparation, including provider and durable audit sink enforcement. Updated `bootstrap.py` so `DefaultAdapters` exposes `audit_event_sink` via `LocalAuditEventSink()`, then switched both live start call sites in `src/scc_cli/commands/launch/flow.py` to the shared helper. Updated `src/scc_cli/commands/worktree/worktree_commands.py` so worktree auto-start now derives team context from `selected_profile`, prepares the plan through the same helper, and finishes through `finalize_launch(...)` instead of bypassing preflight and audit with `start_session(...)`. Extended focused tests and shared fixtures so malformed wiring is caught early, direct start appends canonical launch audit events, JSON-mode blocked preflight still renders through the SCC error boundary, and worktree auto-start now emits or blocks on the same preflight/audit seam.

## Verification

Focused task verification passed with `uv run pytest ./tests/test_bootstrap.py ./tests/test_cli.py ./tests/test_integration.py ./tests/test_worktree_cwd.py -q`. The repo-wide gate passed with `uv run ruff check && uv run mypy src/scc_cli && uv run pytest --tb=short -q`. The exact task-plan verification command also passed verbatim: `uv run pytest ./tests/test_bootstrap.py ./tests/test_cli.py ./tests/test_integration.py ./tests/test_worktree_cwd.py -q && uv run ruff check && uv run mypy src/scc_cli && uv run pytest --tb=short -q`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest ./tests/test_bootstrap.py ./tests/test_cli.py ./tests/test_integration.py ./tests/test_worktree_cwd.py -q` | 0 | ✅ pass | 6800ms |
| 2 | `uv run ruff check && uv run mypy src/scc_cli && uv run pytest --tb=short -q` | 0 | ✅ pass | 46000ms |
| 3 | `uv run pytest ./tests/test_bootstrap.py ./tests/test_cli.py ./tests/test_integration.py ./tests/test_worktree_cwd.py -q && uv run ruff check && uv run mypy src/scc_cli && uv run pytest --tb=short -q` | 0 | ✅ pass | 40100ms |

## Deviations

Expanded the planned dependency-builder extraction slightly by also centralizing the repeated live-plan preparation and sync gating in `src/scc_cli/commands/launch/dependencies.py`, which reduced duplicated wiring in `flow.py` more than a constructor-only helper would have.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/commands/launch/dependencies.py`
- `src/scc_cli/bootstrap.py`
- `src/scc_cli/commands/launch/flow.py`
- `src/scc_cli/commands/worktree/worktree_commands.py`
- `tests/fakes/__init__.py`
- `tests/conftest.py`
- `tests/test_bootstrap.py`
- `tests/test_cli.py`
- `tests/test_integration.py`
- `.gsd/KNOWLEDGE.md`
