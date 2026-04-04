---
estimated_steps: 16
estimated_files: 10
skills_used: []
---

# T04: Decompose commands/launch/flow.py, commands/team.py, and commands/config.py

Extract three commands-layer modules into smaller focused files.

## Steps

1. **commands/launch/flow.py (1447 lines — HARD-FAIL):** Read fully. Extract `interactive_start` (534L) + `run_start_wizard_flow` (121L) into `src/scc_cli/commands/launch/flow_interactive.py`. Extract `_resolve_session_selection` (212L) + session helper functions into `src/scc_cli/commands/launch/flow_session.py`. Keep `start` (293L) and remaining orchestration in `flow.py`. Re-export public names. Update `src/scc_cli/commands/launch/__init__.py` which re-exports `interactive_start` and `run_start_wizard_flow` from `flow`.

2. **commands/team.py (1036 lines):** Read fully. Extract `team_validate` (198L) + `_render_validation_result` (93L) into `src/scc_cli/commands/team_validate.py` (~290 lines). Extract `team_info` (149L) + `team_list` (107L) into `src/scc_cli/commands/team_info.py` (~260 lines). Keep `team_switch` + `team_callback` + small helpers in `team.py`. Re-export public names.

3. **commands/config.py (1029 lines):** Read fully. Extract `_config_validate` (166L) + `_render_config_decisions` (99L) + `_render_blocked_items` + `_render_denied_additions` into `src/scc_cli/commands/config_validate.py` (~400 lines). Extract `_config_paths` (76L) + `_render_active_exceptions` (71L) into `src/scc_cli/commands/config_inspect.py` (~200 lines). Keep `config_cmd` + `setup_cmd` + `_config_explain` in `config.py`. Re-export if any public names moved.

4. Update test imports in `tests/test_launch_flow_characterization.py`, `tests/test_team_commands_characterization.py`, `tests/test_config_commands_characterization.py`.

5. Run verification: `uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_launch_flow_characterization.py tests/test_team_commands_characterization.py tests/test_config_commands_characterization.py tests/test_import_boundaries.py -q`

## Must-Haves

- [ ] `commands/launch/flow.py` under 800 lines (from 1447 HARD-FAIL)
- [ ] `commands/team.py` under 800 lines
- [ ] `commands/config.py` under 800 lines
- [ ] All 17 launch flow characterization tests pass
- [ ] All 17 team commands characterization tests pass
- [ ] All 8 config commands characterization tests pass
- [ ] Import boundary tests pass
- [ ] `uv run ruff check && uv run mypy src/scc_cli` clean

## Inputs

- ``src/scc_cli/commands/launch/flow.py` — 1447-line HARD-FAIL module to decompose`
- ``src/scc_cli/commands/team.py` — 1036-line module to decompose`
- ``src/scc_cli/commands/config.py` — 1029-line module to decompose`
- ``tests/test_launch_flow_characterization.py` — 17 characterization tests`
- ``tests/test_team_commands_characterization.py` — 17 characterization tests`
- ``tests/test_config_commands_characterization.py` — 8 characterization tests`
- ``tests/test_import_boundaries.py` — 31 boundary tests`

## Expected Output

- ``src/scc_cli/commands/launch/flow.py` — residual under 800 lines with re-exports`
- ``src/scc_cli/commands/launch/flow_interactive.py` — extracted interactive wizard flow (~650 lines)`
- ``src/scc_cli/commands/launch/flow_session.py` — extracted session resolution helpers (~250 lines)`
- ``src/scc_cli/commands/team.py` — residual under 800 lines with re-exports`
- ``src/scc_cli/commands/team_validate.py` — extracted validation logic (~290 lines)`
- ``src/scc_cli/commands/team_info.py` — extracted info/list commands (~260 lines)`
- ``src/scc_cli/commands/config.py` — residual under 800 lines with re-exports`
- ``src/scc_cli/commands/config_validate.py` — extracted config validation (~400 lines)`
- ``src/scc_cli/commands/config_inspect.py` — extracted config inspect/paths (~200 lines)`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_launch_flow_characterization.py tests/test_team_commands_characterization.py tests/test_config_commands_characterization.py tests/test_import_boundaries.py -q
