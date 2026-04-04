---
id: S02
parent: M005
milestone: M005
provides:
  - All 15 HARD-FAIL/MANDATORY-SPLIT files decomposed below 800 lines
  - 3 boundary violations eliminated (application→docker, core→marketplace, docker→presentation)
  - Zero regression: all 4079 tests + 315 characterization/boundary tests pass
  - Decomposition patterns (re-export, DI, logging) established for downstream use
requires:
  - slice: S01
    provides: Maintainability baseline, characterization tests, defect catalog identifying the 15 HARD-FAIL/MANDATORY-SPLIT files and 3 boundary violations
affects:
  - S03
  - S04
  - S05
  - S06
key_files:
  - src/scc_cli/application/dashboard_models.py
  - src/scc_cli/application/dashboard_loaders.py
  - src/scc_cli/application/worktree/models.py
  - src/scc_cli/application/worktree/operations.py
  - src/scc_cli/core/personal_profiles_merge.py
  - src/scc_cli/docker/sandbox.py
  - src/scc_cli/marketplace/materialize_git.py
  - src/scc_cli/commands/launch/flow_interactive.py
  - src/scc_cli/commands/launch/flow_session.py
  - src/scc_cli/commands/team_validate.py
  - src/scc_cli/commands/team_info.py
  - src/scc_cli/commands/config_validate.py
  - src/scc_cli/commands/config_inspect.py
  - src/scc_cli/ui/dashboard/orchestrator_handlers.py
  - src/scc_cli/ui/dashboard/orchestrator_menus.py
  - src/scc_cli/ui/dashboard/orchestrator_container_actions.py
  - src/scc_cli/ui/dashboard/_dashboard_actions.py
  - src/scc_cli/ui/settings_profile.py
  - src/scc_cli/ui/wizard_pickers.py
  - src/scc_cli/ui/git_interactive_ops.py
  - src/scc_cli/setup_ui.py
  - src/scc_cli/setup_config.py
key_decisions:
  - Re-export all extracted symbols from residual modules to preserve backward-compatible import paths
  - Used Callable DI parameter to eliminate core→marketplace boundary violation in personal_profiles_merge.py
  - Replaced console.err_line with logging.warning() to eliminate docker→presentation boundary violation
  - Introduced ContainerSummary dataclass as application-layer boundary type replacing docker.core.ContainerInfo
  - Used deferred imports in flow_session.py and sandbox.py to break circular dependencies after extraction
  - Used late-bound module lookup pattern (_get_picker/_get_confirm) in extracted UI modules to preserve test-patch compatibility
patterns_established:
  - Residual + extracted-modules pattern: keep the original module as a thin re-exporter, move definitions to focused files. All public symbols remain importable from the original path.
  - DI-for-boundary-repair: when a cross-layer import violates boundaries, accept the dependency as a Callable parameter. The call site in the correct layer passes the concrete implementation.
  - Logging-for-presentation-boundary: replace direct UI output calls (err_line) with logging.warning() in infrastructure modules. The presentation layer can attach appropriate log handlers.
  - Late-bound module lookup for test-patch compatibility: when extracting methods that are mock targets, use a _get_module() indirection so tests patching the original module path still work.
  - Deferred imports for circular-dependency breaking: use function-level imports when two extracted modules would otherwise create a circular import at module level.
observability_surfaces:
  - none
drill_down_paths:
  - .gsd/milestones/M005/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M005/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M005/slices/S02/tasks/T03-SUMMARY.md
  - .gsd/milestones/M005/slices/S02/tasks/T04-SUMMARY.md
  - .gsd/milestones/M005/slices/S02/tasks/T05-SUMMARY.md
  - .gsd/milestones/M005/slices/S02/tasks/T06-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-04T17:11:48.938Z
blocker_discovered: false
---

# S02: Decompose oversized modules and repair boundaries

**Decomposed all 15 HARD-FAIL/MANDATORY-SPLIT files below 800 lines through mechanical code extraction, repaired 3 architecture boundary violations, and confirmed all 4079 tests + 315 characterization/boundary tests pass.**

## What Happened

S02 executed 6 tasks (T01–T06) over the application, core, docker, marketplace, commands, UI, and setup layers to mechanically decompose every file exceeding 800 lines and fix three concrete architecture boundary violations.

**T01 — dashboard.py (1084→388 lines):** Extracted 33 dataclass/enum model definitions into `dashboard_models.py` (390L) and 4 tab loaders into `dashboard_loaders.py` (481L). Introduced a `ContainerSummary` dataclass as an application-layer boundary type replacing the direct `docker.core.ContainerInfo` import.

**T02 — Three application/core modules:** Decomposed `worktree/use_cases.py` (1044→446) into `worktree/models.py` (363L) and `worktree/operations.py` (317L). Decomposed `core/personal_profiles.py` (839→554) into `personal_profiles_merge.py` (322L) with a `Callable` DI parameter replacing the direct `marketplace.managed` import. Decomposed `launch/start_wizard.py` (914→737) into `wizard_models.py` (215L).

**T03 — docker/launch.py and marketplace/materialize.py:** Extracted `docker/sandbox.py` (433L) from `docker/launch.py` (874→498). Replaced `console.err_line` import with `logging.warning()` to eliminate the docker→presentation boundary violation. Extracted `marketplace/materialize_git.py` (306L) from `marketplace/materialize.py` (866→612).

**T04 — Three commands-layer modules:** Decomposed `commands/launch/flow.py` (1447→338, the largest HARD-FAIL) into `flow_interactive.py` (717L) and `flow_session.py` (404L). Decomposed `commands/team.py` (1036→416) into `team_validate.py` (317L) and `team_info.py` (291L). Decomposed `commands/config.py` (1029→628) into `config_validate.py` (234L) and `config_inspect.py` (166L).

**T05 — Five UI modules:** Decomposed `ui/dashboard/orchestrator.py` (1489→399, the second-largest HARD-FAIL) into `orchestrator_handlers.py` + `orchestrator_menus.py`. Decomposed `_dashboard.py` (966→611) into `_dashboard_actions.py` (406L). Decomposed `settings.py` (1081→792) into `settings_profile.py` (404L). Decomposed `wizard.py` (931→416) into `wizard_pickers.py` (443L). Decomposed `git_interactive.py` (884→543) into `git_interactive_ops.py` (381L).

**T06 — setup.py (1336→794):** Extracted `setup_ui.py` (303L) and `setup_config.py` (310L). Secondary extraction of `orchestrator_container_actions.py` (114L) from `orchestrator_handlers.py` (846→777) to bring the last remaining >800L file under threshold.

**Boundary violations fixed:**
1. `application/dashboard*.py` → no import of `docker.core.ContainerInfo` (replaced with `ContainerSummary` dataclass)
2. `core/personal_profiles*.py` → no import of `marketplace.managed` (replaced with `Callable` DI parameter)
3. `docker/launch.py`, `docker/sandbox.py` → no import of `console.err_line` (replaced with `logging.warning()`)

**Final verification:** All files under 800 lines. ruff check clean. mypy clean (284 source files). 4079 tests pass. 315 characterization + boundary tests pass.

## Verification

All slice-level verification checks pass:
1. `uv run ruff check` → All checks passed
2. `uv run mypy src/scc_cli` → Success: no issues found in 284 source files
3. `uv run pytest --rootdir "$PWD" -q` → 4079 passed, 23 skipped, 3 xfailed, 1 xpassed (65.31s)
4. `uv run pytest tests/test_*_characterization.py tests/test_import_boundaries.py -q` → 315 passed (3.19s)
5. File size scan: zero files in src/scc_cli/ exceed 800 lines
6. Boundary violations: all 3 confirmed eliminated (grep confirms only docstring/error-message references remain, no actual imports)

## Requirements Advanced

- R001 — Completed all 15 HARD-FAIL/MANDATORY-SPLIT decompositions and 3 boundary violation repairs. Every file in src/scc_cli/ is now under 800 lines. All 315 characterization tests + 31 boundary tests pass, confirming no regressions from mechanical extraction.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Minor deviation from plan: T05 left orchestrator_handlers.py at 846 lines (over the 800 threshold). T06 performed a secondary extraction into orchestrator_menus.py bringing it to 846, then the slice closer extracted orchestrator_container_actions.py (114L) bringing it to 777 lines. The settings_render.py file mentioned in the plan was not created — instead T05 extracted settings_profile.py (404L) which was sufficient to bring settings.py under 800 (792L). The slice goal of all files under 800 lines is fully met.

## Known Limitations

- orchestrator_handlers.py (777L) is close to the 800-line threshold and may grow back above it if new dashboard handlers are added without further extraction
- Re-export approach means some modules have non-trivial import prologues (~10-20 lines of re-exports) which adds minor complexity
- The ContainerSummary/ContainerInfo union type in the UI layer (_dashboard.py) is a temporary bridge — should be resolved when the full typed config flow lands in S03

## Follow-ups

- S03 must be replanned to incorporate the governed-artifact/team-pack architecture per user override (D-018–D-020, D017) before implementation
- The ContainerSummary boundary type should become the sole container representation in the application layer once S03 establishes the full typed model hierarchy
- Consider establishing a pre-commit hook or CI check to prevent files from growing back above 800 lines

## Files Created/Modified

- `src/scc_cli/application/dashboard.py` — Residual module (1084→388L): event/effect logic only, re-exports models + loaders
- `src/scc_cli/application/dashboard_models.py` — New: 33 dataclass/enum model definitions (390L) extracted from dashboard.py
- `src/scc_cli/application/dashboard_loaders.py` — New: 4 tab data loaders (481L) with ContainerSummary boundary type
- `src/scc_cli/application/worktree/use_cases.py` — Residual module (1044→446L): re-exports models + operations
- `src/scc_cli/application/worktree/models.py` — New: 18 dataclass model definitions (363L) extracted from use_cases.py
- `src/scc_cli/application/worktree/operations.py` — New: enter_worktree_shell + create_worktree (317L)
- `src/scc_cli/core/personal_profiles.py` — Residual module (839→554L): re-exports merge functions
- `src/scc_cli/core/personal_profiles_merge.py` — New: merge functions with Callable DI replacing marketplace.managed import (322L)
- `src/scc_cli/application/launch/start_wizard.py` — Residual module (914→737L): state machine + event handling
- `src/scc_cli/application/launch/wizard_models.py` — New: 26 ViewModel/Option dataclasses (215L)
- `src/scc_cli/docker/launch.py` — Residual module (874→498L): launch orchestration
- `src/scc_cli/docker/sandbox.py` — New: run_sandbox + inject_plugin_settings (433L), logging replaces err_line
- `src/scc_cli/marketplace/materialize.py` — Residual module (866→612L): high-level dispatch
- `src/scc_cli/marketplace/materialize_git.py` — New: download_and_extract + run_git_clone (306L)
- `src/scc_cli/commands/launch/flow.py` — Residual module (1447→338L): start command orchestration
- `src/scc_cli/commands/launch/flow_interactive.py` — New: interactive_start + run_start_wizard_flow (717L)
- `src/scc_cli/commands/launch/flow_session.py` — New: session resolution + helpers (404L)
- `src/scc_cli/commands/team.py` — Residual module (1036→416L): team_switch + team_callback
- `src/scc_cli/commands/team_validate.py` — New: team_validate + render (317L)
- `src/scc_cli/commands/team_info.py` — New: team_info + team_list (291L)
- `src/scc_cli/commands/config.py` — Residual module (1029→628L): config_cmd + setup_cmd
- `src/scc_cli/commands/config_validate.py` — New: config validation + rendering (234L)
- `src/scc_cli/commands/config_inspect.py` — New: config_paths + render_active_exceptions (166L)
- `src/scc_cli/ui/dashboard/orchestrator.py` — Residual module (1489→399L): run_dashboard + event loop
- `src/scc_cli/ui/dashboard/orchestrator_handlers.py` — New: handler functions for dashboard effects (777L)
- `src/scc_cli/ui/dashboard/orchestrator_menus.py` — New: profile menu + sandbox import + settings + onboarding (344L)
- `src/scc_cli/ui/dashboard/orchestrator_container_actions.py` — New: container stop/resume/remove handlers (114L)
- `src/scc_cli/ui/dashboard/_dashboard.py` — Residual module (966→611L): rendering + run loop
- `src/scc_cli/ui/dashboard/_dashboard_actions.py` — New: _handle_action extracted (406L)
- `src/scc_cli/ui/settings.py` — Residual module (1081→792L): SettingsScreen core
- `src/scc_cli/ui/settings_profile.py` — New: profile diff + sync methods (404L)
- `src/scc_cli/ui/wizard.py` — Residual module (931→416L): render_start_wizard_prompt + answer types
- `src/scc_cli/ui/wizard_pickers.py` — New: picker functions + option builders (443L)
- `src/scc_cli/ui/git_interactive.py` — Residual module (884→543L): create_worktree + clone_repo
- `src/scc_cli/ui/git_interactive_ops.py` — New: cleanup_worktree + install_hooks + install_dependencies (381L)
- `src/scc_cli/setup.py` — Residual module (1336→794L): run_setup_wizard + public API
- `src/scc_cli/setup_ui.py` — New: TUI components for setup wizard (303L)
- `src/scc_cli/setup_config.py` — New: non-interactive setup + config building (310L)
