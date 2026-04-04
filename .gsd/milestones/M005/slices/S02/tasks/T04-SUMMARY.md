---
id: T04
parent: S02
milestone: M005
key_files:
  - src/scc_cli/commands/launch/flow.py
  - src/scc_cli/commands/launch/flow_interactive.py
  - src/scc_cli/commands/launch/flow_session.py
  - src/scc_cli/commands/team.py
  - src/scc_cli/commands/team_info.py
  - src/scc_cli/commands/team_validate.py
  - src/scc_cli/commands/config.py
  - src/scc_cli/commands/config_validate.py
  - src/scc_cli/commands/config_inspect.py
key_decisions:
  - Used deferred imports in flow_session.py to break circular dependency with flow_interactive.py
  - Registered extracted team commands as plain functions decorated by team.py to maintain Typer CLI structure
  - Updated test patch targets to follow functions to new module locations rather than adding backward-compat re-imports
duration: 
verification_result: passed
completed_at: 2026-04-04T16:07:15.325Z
blocker_discovered: false
---

# T04: Decomposed three HARD-FAIL/MANDATORY-SPLIT command modules (1447, 1036, 1029 lines) into nine focused files all under 800 lines

**Decomposed three HARD-FAIL/MANDATORY-SPLIT command modules (1447, 1036, 1029 lines) into nine focused files all under 800 lines**

## What Happened

Extracted three oversized command-layer modules into focused sub-modules: flow.py (1447→338) split into flow_interactive.py (718) and flow_session.py (405); team.py (1036→416) split into team_info.py (292) and team_validate.py (318); config.py (1029→628) split into config_validate.py (234) and config_inspect.py (167). Updated 10 test files to redirect mock patch targets to the new module locations.

## Verification

All verification gates pass: ruff check clean, mypy clean (275 files), full pytest suite 4079 passed. All 73 targeted characterization + boundary tests pass (17 launch flow + 17 team + 8 config + 31 boundary).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 8000ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 13000ms |
| 3 | `uv run pytest -q` | 0 | ✅ pass | 66000ms |
| 4 | `uv run pytest tests/test_launch_flow_characterization.py tests/test_team_commands_characterization.py tests/test_config_commands_characterization.py tests/test_import_boundaries.py -q` | 0 | ✅ pass | 2300ms |

## Deviations

Test patch updates were more extensive than planned — 10 test files needed fixing beyond the 3 characterization tests listed in the plan. Used plain-function + decorator registration pattern for team commands.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/commands/launch/flow.py`
- `src/scc_cli/commands/launch/flow_interactive.py`
- `src/scc_cli/commands/launch/flow_session.py`
- `src/scc_cli/commands/team.py`
- `src/scc_cli/commands/team_info.py`
- `src/scc_cli/commands/team_validate.py`
- `src/scc_cli/commands/config.py`
- `src/scc_cli/commands/config_validate.py`
- `src/scc_cli/commands/config_inspect.py`
