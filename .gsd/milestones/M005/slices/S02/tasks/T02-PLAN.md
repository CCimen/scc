---
estimated_steps: 15
estimated_files: 9
skills_used: []
---

# T02: Decompose application/worktree, core/personal_profiles, and application/launch/start_wizard

Extract three application/core layer modules into smaller focused files. Fix the core→marketplace boundary violation in personal_profiles.

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

## Inputs

- ``src/scc_cli/application/worktree/use_cases.py` — 1044-line module to decompose`
- ``src/scc_cli/core/personal_profiles.py` — 839-line module with marketplace boundary violation`
- ``src/scc_cli/application/launch/start_wizard.py` — 914-line module to decompose`
- ``tests/test_worktree_use_cases_characterization.py` — 16 characterization tests`
- ``tests/test_personal_profiles_characterization.py` — 17 characterization tests`
- ``tests/test_import_boundaries.py` — 31 boundary tests`

## Expected Output

- ``src/scc_cli/application/worktree/use_cases.py` — residual under 800 lines with re-exports`
- ``src/scc_cli/application/worktree/models.py` — extracted dataclass models (~346 lines)`
- ``src/scc_cli/application/worktree/operations.py` — extracted worktree operations`
- ``src/scc_cli/core/personal_profiles.py` — residual under 800 lines with re-exports`
- ``src/scc_cli/core/personal_profiles_merge.py` — extracted merge/diff logic with DI boundary fix (~250 lines)`
- ``src/scc_cli/application/launch/start_wizard.py` — residual under 800 lines with re-exports`
- ``src/scc_cli/application/launch/wizard_models.py` — extracted ViewModel/Option dataclasses (~185 lines)`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_worktree_use_cases_characterization.py tests/test_personal_profiles_characterization.py tests/test_import_boundaries.py -q
