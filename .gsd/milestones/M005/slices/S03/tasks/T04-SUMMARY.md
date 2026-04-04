---
id: T04
parent: S03
milestone: M005
key_files:
  - src/scc_cli/application/start_session.py
  - src/scc_cli/commands/launch/flow_types.py
  - src/scc_cli/commands/launch/flow.py
  - src/scc_cli/commands/launch/flow_interactive.py
  - src/scc_cli/commands/launch/flow_session.py
  - src/scc_cli/commands/launch/team_settings.py
  - src/scc_cli/commands/config.py
  - src/scc_cli/commands/config_validate.py
  - src/scc_cli/commands/launch/render.py
  - src/scc_cli/commands/launch/sandbox.py
  - src/scc_cli/commands/exceptions.py
  - src/scc_cli/commands/worktree/worktree_commands.py
  - src/scc_cli/ui/dashboard/orchestrator_handlers.py
  - tests/test_application_start_session.py
key_decisions:
  - Added raw_org_config field to StartSessionRequest for downstream consumers that still need raw dicts
  - Used is-not-None instead of truthiness for NormalizedOrgConfig.from_dict guard to preserve empty-dict semantics
  - Replaced UserConfig alias with inline dict[str, Any] rather than NormalizedUserConfig
duration: 
verification_result: passed
completed_at: 2026-04-04T18:16:06.256Z
blocker_discovered: false
---

# T04: Typed StartSessionRequest.org_config as NormalizedOrgConfig | None, eliminated UserConfig alias, and normalized all 8 independent compute_effective_config call sites at their outermost boundary

**Typed StartSessionRequest.org_config as NormalizedOrgConfig | None, eliminated UserConfig alias, and normalized all 8 independent compute_effective_config call sites at their outermost boundary**

## What Happened

Pushed the typed NormalizedOrgConfig boundary outward through the launch pipeline. Changed StartSessionRequest.org_config from dict[str,Any]|None to NormalizedOrgConfig|None with a raw_org_config companion field for downstream consumers still needing raw dicts. Updated all 7 StartSessionRequest construction sites and 5 independent compute_effective_config callers to normalize at the outermost call boundary. Eliminated the UserConfig TypeAlias from flow_types.py, replacing it with inline dict[str,Any] in 3 consumer files. Fixed a subtle bug where truthiness-based normalization guards silently converted empty dicts to None, breaking 2 preflight tests.

## Verification

All four verification commands pass: ruff check (0 errors), mypy (0 errors in 285 files), pytest governed artifact tests (20 passed), full suite (4117 passed, 0 failures).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 4000ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4000ms |
| 3 | `uv run pytest tests/test_governed_artifact_models.py -v` | 0 | ✅ pass | 1300ms |
| 4 | `uv run pytest --rootdir "$PWD" -q` | 0 | ✅ pass | 71000ms |

## Deviations

Plan listed 11 files; touched 14 due to 3 additional callers found via mypy. Added raw_org_config dual-field instead of converting all downstream consumers. Used is-not-None guards instead of truthiness.

## Known Issues

SandboxSpec.org_config and sync_marketplace_settings still use raw dict[str,Any] — these are candidates for future typed migration but require changes in docker-layer code.

## Files Created/Modified

- `src/scc_cli/application/start_session.py`
- `src/scc_cli/commands/launch/flow_types.py`
- `src/scc_cli/commands/launch/flow.py`
- `src/scc_cli/commands/launch/flow_interactive.py`
- `src/scc_cli/commands/launch/flow_session.py`
- `src/scc_cli/commands/launch/team_settings.py`
- `src/scc_cli/commands/config.py`
- `src/scc_cli/commands/config_validate.py`
- `src/scc_cli/commands/launch/render.py`
- `src/scc_cli/commands/launch/sandbox.py`
- `src/scc_cli/commands/exceptions.py`
- `src/scc_cli/commands/worktree/worktree_commands.py`
- `src/scc_cli/ui/dashboard/orchestrator_handlers.py`
- `tests/test_application_start_session.py`
