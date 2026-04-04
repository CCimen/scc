---
estimated_steps: 19
estimated_files: 12
skills_used: []
---

# T05: Decompose UI layer: orchestrator, _dashboard, settings, wizard, and git_interactive

Extract five UI-layer modules into smaller focused files. These are the outermost layer — inner-layer extractions from T01–T04 are settled.

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

## Inputs

- ``src/scc_cli/ui/dashboard/orchestrator.py` — 1489-line HARD-FAIL module (largest file)`
- ``src/scc_cli/ui/dashboard/_dashboard.py` — 966-line module to decompose`
- ``src/scc_cli/ui/settings.py` — 1081-line module to decompose`
- ``src/scc_cli/ui/wizard.py` — 931-line module to decompose`
- ``src/scc_cli/ui/git_interactive.py` — 884-line module to decompose`
- ``tests/test_dashboard_orchestrator_characterization.py` — 26 characterization tests`
- ``tests/test_wizard_characterization.py` — 10 characterization tests`
- ``tests/test_import_boundaries.py` — 31 boundary tests`

## Expected Output

- ``src/scc_cli/ui/dashboard/orchestrator.py` — residual under 800 lines with re-exports`
- ``src/scc_cli/ui/dashboard/orchestrator_handlers.py` — extracted handler clusters (~650 lines)`
- ``src/scc_cli/ui/dashboard/_dashboard.py` — residual under 800 lines`
- ``src/scc_cli/ui/dashboard/_dashboard_actions.py` — extracted action handler (~355 lines)`
- ``src/scc_cli/ui/settings.py` — residual under 800 lines`
- ``src/scc_cli/ui/settings_render.py` — extracted rendering helpers`
- ``src/scc_cli/ui/settings_profile.py` — extracted profile operations`
- ``src/scc_cli/ui/wizard.py` — residual under 800 lines with re-exports`
- ``src/scc_cli/ui/wizard_pickers.py` — extracted picker functions (~430 lines)`
- ``src/scc_cli/ui/git_interactive.py` — residual under 800 lines with re-exports`
- ``src/scc_cli/ui/git_interactive_ops.py` — extracted operations (~300 lines)`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_dashboard_orchestrator_characterization.py tests/test_wizard_characterization.py tests/test_import_boundaries.py -q
