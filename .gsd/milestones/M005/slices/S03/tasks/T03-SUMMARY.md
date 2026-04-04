---
id: T03
parent: S03
milestone: M005
key_files:
  - src/scc_cli/application/compute_effective_config.py
  - src/scc_cli/application/personal_profile_policy.py
  - src/scc_cli/ports/config_models.py
  - src/scc_cli/adapters/config_normalizer.py
key_decisions:
  - Union type (dict | NormalizedOrgConfig) with isinstance guard at function boundaries for backward compatibility
  - SessionSettings.auto_resume changed to bool|None=None for explicit-False override semantics
  - NormalizedTeamConfig.network_policy added as str|None=None
  - Team MCP servers re-serialized to dicts for existing match/block helpers
duration: 
verification_result: passed
completed_at: 2026-04-04T17:52:29.613Z
blocker_discovered: false
---

# T03: Converted compute_effective_config and 4 helpers from dict[str,Any] to NormalizedOrgConfig with backward-compatible union signatures, eliminating ~15 raw .get() navigations

**Converted compute_effective_config and 4 helpers from dict[str,Any] to NormalizedOrgConfig with backward-compatible union signatures, eliminating ~15 raw .get() navigations**

## What Happened

Converted the highest-ROI dict[str, Any] flow — compute_effective_config and its 4 helper functions (validate_stdio_server, is_team_delegated_for_plugins, is_team_delegated_for_mcp, is_project_delegated) — plus 2 personal_profile_policy filter functions to accept NormalizedOrgConfig typed field access. All functions use union signatures (dict[str, Any] | NormalizedOrgConfig) with isinstance auto-conversion at entry points for backward compatibility. Body changes replaced ~15 dict .get() chain navigations with typed field access. Required two model-layer fixes: added network_policy field to NormalizedTeamConfig, and changed SessionSettings.auto_resume from bool=False to bool|None=None to preserve explicit-False override semantics.

## Verification

All 4 slice verification commands pass: ruff check (all passed), mypy (285 files clean), characterization tests (63 passed), full suite (4117 passed). Profiles.py re-exports verified working via direct import test.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 2000ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4000ms |
| 3 | `uv run pytest tests/test_compute_effective_config_characterization.py -v` | 0 | ✅ pass | 1400ms |
| 4 | `uv run pytest --rootdir "$PWD" -q` | 0 | ✅ pass | 65800ms |
| 5 | `uv run pytest tests/test_governed_artifact_models.py -v` | 0 | ✅ pass | 1400ms |

## Deviations

Added network_policy to NormalizedTeamConfig (required for typed access). Changed SessionSettings.auto_resume to bool|None (discovered via test failure). Did not update test fixtures to use from_dict() wrappers since auto-conversion makes it unnecessary.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/application/compute_effective_config.py`
- `src/scc_cli/application/personal_profile_policy.py`
- `src/scc_cli/ports/config_models.py`
- `src/scc_cli/adapters/config_normalizer.py`
