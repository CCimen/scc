---
id: T07
parent: S05
milestone: M007-cqttot
key_files:
  - src/scc_cli/application/start_session.py
  - src/scc_cli/commands/launch/dependencies.py
  - src/scc_cli/commands/launch/flow_interactive.py
  - src/scc_cli/commands/worktree/worktree_commands.py
  - tests/test_application_start_session.py
  - tests/test_start_session_image_routing.py
  - tests/test_provider_dispatch.py
  - tests/test_bootstrap.py
key_decisions:
  - D032 fail-closed: three-step provider resolution (request → wired provider → typed error) instead of binary request-or-crash
  - OCI backend without agent_provider raises ProviderNotReadyError rather than InvalidProviderError (more actionable)
  - Legacy Docker Desktop sandbox path preserved as-is — it's a migration boundary, not active dispatch
duration: 
verification_result: passed
completed_at: 2026-04-05T15:21:12.093Z
blocker_discovered: false
---

# T07: Eliminated silent Claude fallback from all active launch paths; missing provider wiring now raises typed errors per D032

**Eliminated silent Claude fallback from all active launch paths; missing provider wiring now raises typed errors per D032**

## What Happened

Searched the codebase for all "claude" references in active launch/runtime paths and classified each as either an active-launch fallback (to fix) or a read/migration boundary (to preserve per D032). Removed silent Claude defaults from prepare_start_session, _build_agent_settings, _build_sandbox_spec, build_start_session_dependencies, prepare_live_start_plan, flow_interactive, and worktree_commands. Added three-step fail-closed provider resolution: request.provider_id → agent_provider.capability_profile().provider_id → InvalidProviderError. OCI backend without agent_provider now raises ProviderNotReadyError. Preserved legacy Docker Desktop sandbox path, session dir defaults, and CLI resolution defaults as read/migration boundaries per D032. Updated 17 test request constructions to include explicit provider_id and converted 4 tests to D032 fail-closed assertions.

## Verification

uv run ruff check — zero errors. uv run mypy src/scc_cli — zero errors. uv run pytest -q — 4761 passed, 0 failed. All targeted tests (113) pass including new fail-closed behavior tests.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 3600ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8400ms |
| 3 | `uv run pytest -q` | 0 | ✅ pass | 51800ms |
| 4 | `uv run pytest tests/test_application_start_session.py tests/test_start_session_image_routing.py tests/test_provider_dispatch.py tests/test_bootstrap.py tests/test_oci_sandbox_runtime.py -v` | 0 | ✅ pass | 3100ms |

## Deviations

Converted existing tests to D032-compliant assertions instead of creating new test files. Plan referenced tests/commands/launch/ which doesn't exist; actual test files are in tests/ root.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/application/start_session.py`
- `src/scc_cli/commands/launch/dependencies.py`
- `src/scc_cli/commands/launch/flow_interactive.py`
- `src/scc_cli/commands/worktree/worktree_commands.py`
- `tests/test_application_start_session.py`
- `tests/test_start_session_image_routing.py`
- `tests/test_provider_dispatch.py`
- `tests/test_bootstrap.py`
