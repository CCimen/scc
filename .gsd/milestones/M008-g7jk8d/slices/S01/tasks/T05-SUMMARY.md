---
id: T05
parent: S01
milestone: M008-g7jk8d
key_files:
  - tests/test_launch_preflight_guardrail.py
key_decisions:
  - Guardrail scoped to migrated files only (flow.py, flow_interactive.py) per T03 decision
  - Display name allowlist includes adapter modules and legacy render/sandbox defaults as tracked debt
duration: 
verification_result: passed
completed_at: 2026-04-06T12:48:59.450Z
blocker_discovered: false
---

# T05: Created structural guardrail tests preventing inline provider resolution drift and verifying single-source provider metadata

**Created structural guardrail tests preventing inline provider resolution drift and verifying single-source provider metadata**

## What Happened

Built tests/test_launch_preflight_guardrail.py with 7 structural tests in three classes: (1) TestProviderResolutionAntiDrift — tokenize-based scanning of flow.py and flow_interactive.py to prevent choose_start_provider/resolve_active_provider from reappearing after T03 migration, plus verification that preflight.py is the sole wrapper within commands/launch/. (2) TestProviderMetadataSingleSource — AST-based string literal extraction to verify image refs and display names only exist in canonical locations (image_contracts.py, provider_registry.py, provider_resolution.py, plus adapter allowlist). Also cross-checks PROVIDER_REGISTRY keys match _PROVIDER_DISPATCH keys. (3) TestPreflightArchitectureGuard — AST top-level import scanning to enforce D046 (only types/errors from core/ at module level).

## Verification

ruff check: 0 errors. mypy src/scc_cli: 0 errors in 303 files. All 7 guardrail tests pass. Full suite: 4993 passed, 23 skipped, 2 xfailed, 0 failures.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 2600ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 2600ms |
| 3 | `uv run pytest tests/test_launch_preflight_guardrail.py -v` | 0 | ✅ pass | 1570ms |
| 4 | `uv run pytest -q` | 0 | ✅ pass | 60870ms |

## Deviations

Guardrail anti-drift scope covers only the two migrated files (flow.py, flow_interactive.py) per T03 decision, not all five entry points. orchestrator_handlers.py and worktree_commands.py still use choose_start_provider directly — the _MIGRATED_FILES tuple should be extended when those are migrated.

## Known Issues

None.

## Files Created/Modified

- `tests/test_launch_preflight_guardrail.py`
