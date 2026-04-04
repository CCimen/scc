# S02: Decompose oversized modules and repair boundaries

**Goal:** Reduce all 15 HARD-FAIL (>1100 lines) and MANDATORY-SPLIT (>800 lines) files below 800 lines through mechanical code extraction, and repair 3 concrete architecture boundary violations (application→docker, core→marketplace, docker→presentation), while preserving all 315 characterization tests and public API surfaces.
**Demo:** After this: TBD

## Tasks
- [x] **T01: Decomposed 1084-line dashboard.py into three focused modules (models/loaders/residual) and replaced docker.core.ContainerInfo boundary violation with application-layer ContainerSummary** — Extract the application/dashboard.py module (1084 lines) into three focused files: models, loaders, and residual event/effect logic. Fix the docker.core.ContainerInfo boundary violation in the loaders by introducing a local TypeAlias.

## Steps

1. Read `src/scc_cli/application/dashboard.py` fully. Identify the 33 dataclass/enum model definitions (roughly L17–L368, ~380 lines) and the 4 tab data loaders (`load_status_tab_data`, `load_containers_tab_data`, `load_sessions_tab_data`, `load_worktrees_tab_data`, totaling ~360 lines).

2. Create `src/scc_cli/application/dashboard_models.py`. Move all dataclass and enum definitions there. Keep the same imports they need. Add `from __future__ import annotations` at the top.

3. Create `src/scc_cli/application/dashboard_loaders.py`. Move the 4 `load_*_tab_data` functions there. For the `docker.core.ContainerInfo` boundary violation: in the loaders file, use `from typing import Any` and accept container data as `dict[str, Any]` or create a minimal `ContainerSummary = dict[str, Any]` TypeAlias instead of importing `ContainerInfo` directly from docker.core. The loaders should import models from `dashboard_models.py`.

4. Update `src/scc_cli/application/dashboard.py` to import and re-export all public names from `dashboard_models` and `dashboard_loaders`. The residual file should contain event handler and effect logic (~340 lines). All symbols previously importable from `scc_cli.application.dashboard` must remain importable from the same path.

5. Update any test files that import internals from `application/dashboard.py` — check `tests/test_app_dashboard_characterization.py` imports.

6. Run verification: `uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_app_dashboard_characterization.py tests/test_import_boundaries.py -q`

## Must-Haves

- [ ] `application/dashboard.py` is under 800 lines
- [ ] `application/dashboard_models.py` exists with all dataclass/enum definitions
- [ ] `application/dashboard_loaders.py` exists with all tab loaders
- [ ] No import of `docker.core.ContainerInfo` in application/dashboard*.py files
- [ ] All 40 characterization tests in test_app_dashboard_characterization.py pass
- [ ] All 31 import boundary tests pass
- [ ] `uv run ruff check && uv run mypy src/scc_cli` clean
  - Estimate: 45m
  - Files: src/scc_cli/application/dashboard.py, src/scc_cli/application/dashboard_models.py, src/scc_cli/application/dashboard_loaders.py, tests/test_app_dashboard_characterization.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_app_dashboard_characterization.py tests/test_import_boundaries.py -q
- [x] **T02: Decomposed three oversized modules (1044, 839, 914 lines) into focused files under 800 lines and eliminated the core→marketplace boundary violation via dependency injection** — Extract three application/core layer modules into smaller focused files. Fix the core→marketplace boundary violation in personal_profiles.

## Steps

1. **application/worktree/use_cases.py (1044 lines):** Read fully. Extract 18 dataclass model definitions (~L24–L370, ~346 lines) into `src/scc_cli/application/worktree/models.py`. Extract `enter_worktree_shell` (134L) + `create_worktree` (94L) + their helper functions into `src/scc_cli/application/worktree/operations.py`. Update `use_cases.py` to import and re-export all public names. Update `src/scc_cli/application/worktree/__init__.py` if it imports from `use_cases` — add imports from `models` and `operations` as needed.

2. **core/personal_profiles.py (839 lines):** Read fully. Extract `compute_structured_diff` (97L) + `DiffItem`/`StructuredDiff` classes + merge functions (`merge_personal_settings`, `merge_personal_mcp`) into `src/scc_cli/core/personal_profiles_merge.py` (~250 lines). **Boundary fix:** In the extracted merge file, replace the direct `from scc_cli.marketplace.managed import load_managed_state` with a `managed_state_loader: Callable` parameter — the function should accept the loader as a parameter instead of importing it. Update the call site(s) that invoke `merge_personal_settings` to pass `load_managed_state` as an argument. Re-export all moved symbols from `personal_profiles.py`.

3. **application/launch/start_wizard.py (914 lines):** Read fully. Extract 26 ViewModel/Option dataclass definitions (~L409–L594, ~185 lines) into `src/scc_cli/application/launch/wizard_models.py`. Keep state machine + `apply_start_wizard_event` in `start_wizard.py`. Re-export from `start_wizard.py`. Update `src/scc_cli/application/launch/__init__.py` if needed.

4. Update test imports in `tests/test_worktree_use_cases_characterization.py`, `tests/test_personal_profiles_characterization.py`, and any other affected test files.

5. Run verification: `uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_worktree_use_cases_characterization.py tests/test_personal_profiles_characterization.py tests/test_import_boundaries.py -q`

## Must-Haves

- [ ] `application/worktree/use_cases.py` under 800 lines
- [ ] `core/personal_profiles.py` under 800 lines
- [ ] `application/launch/start_wizard.py` under 800 lines
- [ ] No import of `marketplace.managed` in core/personal_profiles*.py
- [ ] All characterization tests for these 3 modules pass
- [ ] Import boundary tests pass
- [ ] `uv run ruff check && uv run mypy src/scc_cli` clean
  - Estimate: 1h
  - Files: src/scc_cli/application/worktree/use_cases.py, src/scc_cli/application/worktree/models.py, src/scc_cli/application/worktree/operations.py, src/scc_cli/application/worktree/__init__.py, src/scc_cli/core/personal_profiles.py, src/scc_cli/core/personal_profiles_merge.py, src/scc_cli/application/launch/start_wizard.py, src/scc_cli/application/launch/wizard_models.py, src/scc_cli/application/launch/__init__.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_worktree_use_cases_characterization.py tests/test_personal_profiles_characterization.py tests/test_import_boundaries.py -q
- [ ] **T03: Decompose docker/launch.py and marketplace/materialize.py with boundary fix** — Extract docker/launch.py (874 lines) and marketplace/materialize.py (866 lines) into smaller focused files. Fix the docker→presentation boundary violation (console.err_line import).

## Steps

1. **docker/launch.py (874 lines):** Read fully. Extract `run_sandbox` (216L) + `inject_plugin_settings_to_container` (65L) + related helpers into `src/scc_cli/docker/sandbox.py`. NOTE: there is already a `src/scc_cli/commands/launch/sandbox.py` — the new file goes in `src/scc_cli/docker/sandbox.py` which is a different package. **Boundary fix:** The `from ..console import err_line` import is used for a single warning message. Replace it with `logging.warning()` or `logging.getLogger(__name__).warning()`. Re-export public names from `launch.py`. Update `src/scc_cli/docker/__init__.py` if it re-exports from `launch.py`.

2. **marketplace/materialize.py (866 lines):** Read fully. Extract `download_and_extract` (113L) + `run_git_clone` (82L) + helper functions into `src/scc_cli/marketplace/materialize_git.py` (~250 lines). Keep high-level `materialize_*` dispatch functions in `materialize.py`. Re-export all public names.

3. Update test imports in `tests/test_docker_launch_characterization.py` and `tests/test_marketplace_materialize_characterization.py` if they reference moved internals.

4. Run verification: `uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_docker_launch_characterization.py tests/test_marketplace_materialize_characterization.py tests/test_import_boundaries.py -q`

## Must-Haves

- [ ] `docker/launch.py` under 800 lines
- [ ] `marketplace/materialize.py` under 800 lines
- [ ] No import of `console.err_line` in docker/launch.py or docker/sandbox.py
- [ ] All 27 docker launch characterization tests pass
- [ ] All 24 marketplace materialize characterization tests pass
- [ ] Import boundary tests pass
- [ ] `uv run ruff check && uv run mypy src/scc_cli` clean
  - Estimate: 45m
  - Files: src/scc_cli/docker/launch.py, src/scc_cli/docker/sandbox.py, src/scc_cli/docker/__init__.py, src/scc_cli/marketplace/materialize.py, src/scc_cli/marketplace/materialize_git.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_docker_launch_characterization.py tests/test_marketplace_materialize_characterization.py tests/test_import_boundaries.py -q
- [ ] **T04: Decompose commands/launch/flow.py, commands/team.py, and commands/config.py** — Extract three commands-layer modules into smaller focused files.

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
  - Estimate: 1h
  - Files: src/scc_cli/commands/launch/flow.py, src/scc_cli/commands/launch/flow_interactive.py, src/scc_cli/commands/launch/flow_session.py, src/scc_cli/commands/launch/__init__.py, src/scc_cli/commands/team.py, src/scc_cli/commands/team_validate.py, src/scc_cli/commands/team_info.py, src/scc_cli/commands/config.py, src/scc_cli/commands/config_validate.py, src/scc_cli/commands/config_inspect.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_launch_flow_characterization.py tests/test_team_commands_characterization.py tests/test_config_commands_characterization.py tests/test_import_boundaries.py -q
- [ ] **T05: Decompose UI layer: orchestrator, _dashboard, settings, wizard, and git_interactive** — Extract five UI-layer modules into smaller focused files. These are the outermost layer — inner-layer extractions from T01–T04 are settled.

## Steps

1. **ui/dashboard/orchestrator.py (1489 lines — HARD-FAIL, largest file):** Read fully. Extract `_handle_*` handler clusters (container actions, session actions, worktree actions, profile menu, sandbox import, onboarding — ~650 lines of handler functions) into `src/scc_cli/ui/dashboard/orchestrator_handlers.py`. Keep `run_dashboard` + `_apply_event` + `_run_effect` in `orchestrator.py`. Re-export from `orchestrator.py` and update `ui/dashboard/__init__.py` if needed.

2. **ui/dashboard/_dashboard.py (966 lines):** Read fully. Extract `_handle_action` (355L) into `src/scc_cli/ui/dashboard/_dashboard_actions.py` as a standalone function that takes Dashboard state parameters. Keep rendering + run loop in `_dashboard.py`.

3. **ui/settings.py (1081 lines):** Read fully. The single 969L `SettingsScreen` class needs decomposition. Extract `_render` (219L) + rendering helper methods into `src/scc_cli/ui/settings_render.py`. Extract `_profile_diff` (73L) + `_profile_sync` (58L) + profile-related methods into `src/scc_cli/ui/settings_profile.py`. Keep `_handle_key` + constructor + `run()` in `settings.py`. Since these are class methods, extract them as module-level functions that accept the relevant state as parameters, then call them from the class.

4. **ui/wizard.py (931 lines):** Read fully. Extract `pick_team_repo` (105L) + `pick_workspace_source` (100L) + `pick_recent_workspace` (68L) + `build_workspace_source_options*` (154L) into `src/scc_cli/ui/wizard_pickers.py` (~430 lines). Keep `render_start_wizard_prompt` (192L) + answer types in `wizard.py`. Re-export public names.

5. **ui/git_interactive.py (884 lines):** Read fully. Extract `cleanup_worktree` (147L) + `install_hooks` (83L) + `install_dependencies` (62L) into `src/scc_cli/ui/git_interactive_ops.py` (~300 lines). Keep `create_worktree` + `check_branch_safety` + `clone_repo` in `git_interactive.py`. Re-export public names.

6. Update test imports in `tests/test_dashboard_orchestrator_characterization.py` and `tests/test_wizard_characterization.py`.

7. Run verification: `uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_dashboard_orchestrator_characterization.py tests/test_wizard_characterization.py tests/test_import_boundaries.py -q`

## Must-Haves

- [ ] `ui/dashboard/orchestrator.py` under 800 lines (from 1489 HARD-FAIL)
- [ ] `ui/dashboard/_dashboard.py` under 800 lines
- [ ] `ui/settings.py` under 800 lines
- [ ] `ui/wizard.py` under 800 lines
- [ ] `ui/git_interactive.py` under 800 lines
- [ ] All 26 orchestrator characterization tests pass
- [ ] All 10 wizard characterization tests pass
- [ ] Import boundary tests pass
- [ ] `uv run ruff check && uv run mypy src/scc_cli` clean
  - Estimate: 1h30m
  - Files: src/scc_cli/ui/dashboard/orchestrator.py, src/scc_cli/ui/dashboard/orchestrator_handlers.py, src/scc_cli/ui/dashboard/_dashboard.py, src/scc_cli/ui/dashboard/_dashboard_actions.py, src/scc_cli/ui/dashboard/__init__.py, src/scc_cli/ui/settings.py, src/scc_cli/ui/settings_render.py, src/scc_cli/ui/settings_profile.py, src/scc_cli/ui/wizard.py, src/scc_cli/ui/wizard_pickers.py, src/scc_cli/ui/git_interactive.py, src/scc_cli/ui/git_interactive_ops.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_dashboard_orchestrator_characterization.py tests/test_wizard_characterization.py tests/test_import_boundaries.py -q
- [ ] **T06: Decompose setup.py and run final size verification** — Extract setup.py (1336 lines — HARD-FAIL) into smaller focused files, then run the final comprehensive verification confirming all 15 targets are below threshold.

## Steps

1. **setup.py (1336 lines — HARD-FAIL):** Read fully. Extract TUI components (`_select_option`, `_render_setup_layout`, `_render_setup_header`, `_render_options`, `show_welcome`) into `src/scc_cli/setup_ui.py` (~400 lines). Extract `run_non_interactive_setup` + `_build_proposed_config` + `_build_config_preview` into `src/scc_cli/setup_config.py` (~300 lines). Keep `run_setup_wizard` + `show_setup_complete` + public API in `setup.py`. Re-export all public names from `setup.py`.

2. Update test imports in `tests/test_setup_characterization.py` if they reference moved internals.

3. Run characterization verification: `uv run pytest tests/test_setup_characterization.py tests/test_import_boundaries.py -q`

4. Run the final comprehensive file-size check to confirm all 15 targets are under 800 lines:
```python
python3 -c "
from pathlib import Path
fail = False
for f in sorted(Path('src/scc_cli').rglob('*.py')):
    lines = len(f.read_text().splitlines())
    if lines > 1100:
        print(f'HARD-FAIL: {f} ({lines} lines)')
        fail = True
    elif lines > 800:
        print(f'WARNING: {f} ({lines} lines)')
if not fail:
    print('All HARD-FAIL targets eliminated.')
"
```

5. Run full gate: `uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q`

6. Run complete characterization suite: `uv run pytest tests/test_*_characterization.py tests/test_import_boundaries.py -q` — all 315 tests must pass.

## Must-Haves

- [ ] `setup.py` under 800 lines (from 1336 HARD-FAIL)
- [ ] `setup_ui.py` exists with TUI components
- [ ] `setup_config.py` exists with config logic
- [ ] No file in src/scc_cli/ exceeds 1100 lines
- [ ] All 19 setup characterization tests pass
- [ ] All 315 characterization + boundary tests pass
- [ ] Full gate passes: ruff + mypy + pytest (4079+ tests)
- [ ] 3 boundary violations confirmed fixed: no docker.core.ContainerInfo in application/dashboard*, no marketplace.managed in core/personal_profiles*, no console.err_line in docker/launch*
  - Estimate: 45m
  - Files: src/scc_cli/setup.py, src/scc_cli/setup_ui.py, src/scc_cli/setup_config.py, tests/test_setup_characterization.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q && uv run pytest tests/test_*_characterization.py tests/test_import_boundaries.py -q && python3 -c "from pathlib import Path; [print(f'OVER 800: {f} ({len(f.read_text().splitlines())} lines)') for f in sorted(Path('src/scc_cli').rglob('*.py')) if len(f.read_text().splitlines()) > 800]"
