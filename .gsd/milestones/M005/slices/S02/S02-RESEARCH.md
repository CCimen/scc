# S02 Research: Decompose Oversized Modules and Repair Boundaries

## Summary

S02 must reduce 15 files from HARD-FAIL (>1100 lines) and MANDATORY-SPLIT (>800 lines) status to below 800 lines, while repairing 5 concrete architecture boundary violations. The work is mechanical refactoring — extract functions/classes into new sibling modules, re-export from `__init__.py`, update imports — using patterns already established in the codebase (e.g., `commands/launch/` already has `wizard_resume.py`, `workspace.py`, `render.py` as prior extractions from `flow.py`). S01 delivered 315 characterization tests protecting all split targets. No new technology, no new patterns, no ambiguity.

## Recommendation

Decompose in dependency order: application/core first (inner layers), then commands/ui (outer layers that import from inner). Each task should target 2-4 files with clear extraction targets, run the full gate after each task, and keep public API surfaces stable by re-exporting from original module or `__init__.py`. Boundary repairs should be bundled with the decomposition of the violating file rather than done as a separate pass.

## Implementation Landscape

### Target Files and Split Strategy

**HARD-FAIL (must get below 800 lines):**

| File | Lines | Strategy |
|------|-------|----------|
| `ui/dashboard/orchestrator.py` (1489) | Extract handler clusters into `orchestrator_handlers.py` (~650 lines of `_handle_*` functions: container actions, session actions, worktree actions, profile menu, sandbox import, onboarding). Keep `run_dashboard` + `_apply_event` + `_run_effect` in `orchestrator.py`. |
| `commands/launch/flow.py` (1447) | Extract `interactive_start` (534L) + `run_start_wizard_flow` (121L) into `flow_interactive.py`. Extract `_resolve_session_selection` (212L) + session helpers into `flow_session.py`. Keep `start` (293L) in `flow.py`. |
| `setup.py` (1336) | Extract TUI components (`_select_option`, `_render_setup_layout`, `_render_setup_header`, `_render_options`, `show_welcome`) into `setup_ui.py` (~400L). Extract `run_non_interactive_setup` + `_build_proposed_config` + `_build_config_preview` into `setup_config.py` (~300L). Keep `run_setup_wizard` + `show_setup_complete` + public API in `setup.py`. |

**MANDATORY-SPLIT (must get below 800 lines):**

| File | Lines | Strategy |
|------|-------|----------|
| `application/dashboard.py` (1084) | Extract 33 dataclass/enum model definitions (L17-L368, ~380L) into `application/dashboard_models.py`. Extract 4 tab data loaders (`load_status_tab_data` 171L, `load_containers_tab_data` 52L, `load_sessions_tab_data` 66L, `load_worktrees_tab_data` 71L, total ~360L) into `application/dashboard_loaders.py`. Keep event handler + effect logic (~340L) in `dashboard.py`. Fix boundary: replace `docker.core.ContainerInfo` import with a port type or local TypeAlias. |
| `ui/settings.py` (1081) | Single 969L class `SettingsScreen`. Extract `_render` (219L) + rendering helpers into `settings_render.py`. Extract `_profile_diff` (73L) + `_profile_sync` (58L) + profile-related methods into `settings_profile.py`. Keep `_handle_key` + constructor + `run()` in `settings.py`. |
| `application/worktree/use_cases.py` (1044) | Extract 18 dataclass model definitions (L24-L370, ~346L) into `application/worktree/models.py`. Extract `enter_worktree_shell` (134L) + `create_worktree` (94L) + helpers into `application/worktree/operations.py`. Keep `switch_worktree` + `select_worktree` + `list_worktrees` in `use_cases.py`. |
| `commands/team.py` (1036) | Extract `team_validate` (198L) + `_render_validation_result` (93L) into `commands/team_validate.py` (~290L). Extract `team_info` (149L) + `team_list` (107L) into `commands/team_info.py` (~260L). Keep `team_switch` + `team_callback` + small helpers in `team.py`. |
| `commands/config.py` (1029) | Extract `_config_validate` (166L) + `_render_config_decisions` (99L) + `_render_blocked_items` + `_render_denied_additions` into `commands/config_validate.py` (~400L). Extract `_config_paths` (76L) + `_render_active_exceptions` (71L) into `commands/config_inspect.py` (~200L). Keep `config_cmd` + `setup_cmd` + `_config_explain` in `config.py`. |
| `ui/dashboard/_dashboard.py` (966) | Extract `_handle_action` (355L) into `_dashboard_actions.py` as a standalone function that takes Dashboard state. Keep rendering + run loop in `_dashboard.py`. |
| `ui/wizard.py` (931) | Extract `pick_team_repo` (105L) + `pick_workspace_source` (100L) + `pick_recent_workspace` (68L) + `build_workspace_source_options*` (154L) into `wizard_pickers.py` (~430L). Keep `render_start_wizard_prompt` (192L) + answer types in `wizard.py`. |
| `application/launch/start_wizard.py` (914) | Extract 26 ViewModel/Option dataclasses (L409-L594, ~185L) into `application/launch/wizard_models.py`. Keep state machine + `apply_start_wizard_event` in `start_wizard.py`. Result ~729L — under threshold. |
| `ui/git_interactive.py` (884) | Extract `cleanup_worktree` (147L) + `install_hooks` (83L) + `install_dependencies` (62L) into `git_interactive_ops.py` (~300L). Keep `create_worktree` + `check_branch_safety` + `clone_repo` in `git_interactive.py`. |
| `docker/launch.py` (874) | Extract `run_sandbox` (216L) + `inject_plugin_settings_to_container` (65L) into `docker/sandbox.py` (~300L). Keep `run` + `_write_policy_to_dir` + policy helpers in `launch.py`. Fix boundary: remove `console.err_line` import. |
| `marketplace/materialize.py` (866) | Extract `download_and_extract` (113L) + `run_git_clone` (82L) + helper functions into `marketplace/materialize_git.py` (~250L). Keep high-level `materialize_*` dispatch functions in `materialize.py`. |
| `core/personal_profiles.py` (839) | Extract `compute_structured_diff` (97L) + `DiffItem`/`StructuredDiff` classes + merge functions (`merge_personal_settings` 66L, `merge_personal_mcp`) into `core/personal_profiles_merge.py` (~250L). Fix boundary: replace `marketplace.managed.load_managed_state` import with a callable parameter (dependency injection). Keep CRUD + I/O in `personal_profiles.py`. |

### Boundary Repairs (5 violations)

| Violation | Fix | Bundle With |
|-----------|-----|-------------|
| `application/dashboard.py` imports `docker.core.ContainerInfo` | Create a `ContainerSummary` type in `ports/` or use an existing port type; remap inside the dashboard loaders | `application/dashboard.py` decomposition |
| `core/personal_profiles.py` imports `marketplace.managed.load_managed_state` | Pass `managed_state_loader: Callable` as parameter to `merge_personal_settings`, inject at call site | `core/personal_profiles.py` decomposition |
| `docker/launch.py` imports `..console.err_line` | Replace with `logging.warning()` or remove the single call (used for one warning message) | `docker/launch.py` decomposition |
| `adapters/claude_settings.py` imports from application layer | This is a minor violation — defer to S03 typed config work since it requires deeper refactoring |
| `ui/formatters.py` imports `docker.core.ContainerInfo` | Low severity (docstring reference only) — fix is trivial, bundle with any dashboard task |

### Existing Characterization Test Coverage

S01 delivered characterization tests for all 15 split targets. Key coverage:
- `test_launch_flow_characterization.py` — 17 tests (flow.py wizard state machine)
- `test_dashboard_orchestrator_characterization.py` — 26 tests (orchestrator.py view building)
- `test_docker_launch_characterization.py` — 27 tests (docker/launch.py policy chain)
- `test_personal_profiles_characterization.py` — 17 tests (personal_profiles.py CRUD)
- `test_compute_effective_config_characterization.py` — 63 tests (largest coverage)
- `test_app_dashboard_characterization.py` — 40 tests (dashboard event/effect handling)
- `test_marketplace_materialize_characterization.py` — 24 tests (materialize name validation)
- `test_setup_characterization.py` — 19 tests (setup config preview)
- `test_team_commands_characterization.py` — 17 tests (team display/validation)
- `test_worktree_use_cases_characterization.py` — 16 tests (selection/shell resolution)
- `test_wizard_characterization.py` — 10 tests (path normalization, answer factories)
- `test_config_commands_characterization.py` — 8 tests (enforcement status)
- `test_import_boundaries.py` — 31 tests (layer separation)

Total: 315 tests protecting behavior before surgery.

### Task Ordering and Dependencies

The correct order is inner-layers-first:
1. **Application/core layer** — `application/dashboard.py`, `application/worktree/use_cases.py`, `application/launch/start_wizard.py`, `core/personal_profiles.py` (with boundary fixes)
2. **Docker/marketplace layer** — `docker/launch.py`, `marketplace/materialize.py`
3. **Commands layer** — `commands/launch/flow.py`, `commands/team.py`, `commands/config.py`
4. **UI layer** — `ui/dashboard/orchestrator.py`, `ui/dashboard/_dashboard.py`, `ui/settings.py`, `ui/wizard.py`, `ui/git_interactive.py`
5. **Root modules** — `setup.py`

Rationale: outer layers import from inner layers. If inner-layer module paths change, we want those changes settled before touching outer-layer imports. Each task should target one layer or one tightly-coupled cluster.

### Constraints

1. **Public API preservation**: Functions called from outside the module must remain importable from the same path (re-export via `__init__.py` or keep the original name in the original file with a re-import).
2. **Characterization tests must pass after every extraction**: Run `uv run pytest tests/test_*_characterization.py tests/test_import_boundaries.py -q` after each task.
3. **No behavior changes**: Extractions are pure code movement. No logic changes, no new features, no refactoring of internals.
4. **Boundary fixes are minimal**: Inject dependencies or use port types. Don't redesign the whole module.
5. **Gate must pass**: `uv run ruff check && uv run mypy src/scc_cli && uv run pytest` after every task.

### Verification Commands

```bash
# After each task:
uv run ruff check
uv run mypy src/scc_cli
uv run pytest --rootdir "$PWD" -q
uv run pytest tests/test_*_characterization.py tests/test_import_boundaries.py -q

# After all tasks:
# Confirm no file exceeds 1100 lines
python3 -c "
from pathlib import Path
for f in sorted(Path('src/scc_cli').rglob('*.py')):
    lines = len(f.read_text().splitlines())
    if lines > 1100:
        print(f'HARD-FAIL: {f} ({lines} lines)')
    elif lines > 800:
        print(f'WARNING: {f} ({lines} lines)')
"
```

### Risks

1. **Import cycle creation**: Extracting pieces of a large file into sibling modules can create cycles if the extracted functions call back into the original. Mitigation: extract complete clusters with their dependencies; use lazy imports for back-references if unavoidable.
2. **Re-export breakage**: If external code imports a specific symbol from a module that gets moved, the import breaks. Mitigation: always re-export from the original module or `__init__.py`; run the full test suite.
3. **Characterization test fragility**: Some tests may import internal helpers that move. Mitigation: update test imports as part of the extraction task; the tests themselves validate behavior preservation.
4. **Task size**: 15 files is a lot. Each task should target 2-4 files max to stay within one context window. Expect 5-6 tasks.

### Recommended Task Decomposition (6 tasks)

**T01: Decompose application/dashboard.py + boundary fix** (1084L → ~340L + 380L models + 360L loaders)
- Extract models to `application/dashboard_models.py`
- Extract tab loaders to `application/dashboard_loaders.py`
- Fix `docker.core.ContainerInfo` boundary violation in loaders
- Re-export all public names from `application/dashboard.py` for backward compat
- Files: `application/dashboard.py`, new `application/dashboard_models.py`, new `application/dashboard_loaders.py`

**T02: Decompose application/worktree + core/personal_profiles + application/launch/start_wizard** (~2900L → targets all under 800)
- Extract worktree models to `application/worktree/models.py`, operations to `operations.py`
- Extract personal_profiles merge/diff to `core/personal_profiles_merge.py`; fix marketplace boundary
- Extract start_wizard view models to `application/launch/wizard_models.py`
- Files: `application/worktree/use_cases.py`, `core/personal_profiles.py`, `application/launch/start_wizard.py` + new files

**T03: Decompose docker/launch.py + marketplace/materialize.py** (~1740L → targets under 800)
- Extract sandbox functions to `docker/sandbox.py`; fix console boundary
- Extract git clone/download to `marketplace/materialize_git.py`
- Files: `docker/launch.py`, `marketplace/materialize.py` + new files

**T04: Decompose commands/launch/flow.py + commands/team.py + commands/config.py** (~3512L → targets under 800)
- Extract interactive flow to `commands/launch/flow_interactive.py`, session helpers to `flow_session.py`
- Extract team validate/info to `commands/team_validate.py`, `commands/team_info.py`
- Extract config validate/inspect to `commands/config_validate.py`, `commands/config_inspect.py`
- Files: 3 source files + 5 new files

**T05: Decompose UI layer** (~5351L → targets under 800)
- Extract orchestrator handlers to `ui/dashboard/orchestrator_handlers.py`
- Extract dashboard actions to `ui/dashboard/_dashboard_actions.py`
- Extract settings render + profile to `ui/settings_render.py`, `ui/settings_profile.py`
- Extract wizard pickers to `ui/wizard_pickers.py`
- Extract git_interactive operations to `ui/git_interactive_ops.py`
- Files: 5 source files + 6 new files

**T06: Decompose setup.py + final verification** (1336L → target under 800)
- Extract UI components to `setup_ui.py`, config logic to `setup_config.py`
- Run final guardrail check: no file >1100, count files >800
- Update `test_import_boundaries.py` if new boundary rules needed
- Files: `setup.py` + 2 new files

### What the Planner Should NOT Do

- Do not refactor function internals — only move them to new files.
- Do not rename functions or change signatures.
- Do not change the `except Exception` sites or subprocess calls — those are S04.
- Do not replace `dict[str, Any]` with typed models — that is S03.
- Do not add new test coverage beyond import fixes — that is S05.
- Do not try to decompose all 63 files >300 lines — only the 15 HARD-FAIL/MANDATORY-SPLIT targets.
- Do not fix the `adapters/claude_settings.py` upward dependency — that requires S03 typed config work.
