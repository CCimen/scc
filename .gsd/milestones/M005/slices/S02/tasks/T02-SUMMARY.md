---
id: T02
parent: S02
milestone: M005
key_files:
  - src/scc_cli/application/worktree/models.py
  - src/scc_cli/application/worktree/operations.py
  - src/scc_cli/application/worktree/use_cases.py
  - src/scc_cli/core/personal_profiles_merge.py
  - src/scc_cli/core/personal_profiles.py
  - src/scc_cli/application/launch/wizard_models.py
  - src/scc_cli/application/launch/start_wizard.py
key_decisions:
  - merge_personal_settings uses managed_state_loader: Callable DI parameter to eliminate core→marketplace boundary violation
  - Re-export all extracted symbols from residual modules for backward compatibility
duration: 
verification_result: passed
completed_at: 2026-04-04T15:23:29.785Z
blocker_discovered: false
---

# T02: Decomposed three oversized modules (1044, 839, 914 lines) into focused files under 800 lines and eliminated the core→marketplace boundary violation via dependency injection

**Decomposed three oversized modules (1044, 839, 914 lines) into focused files under 800 lines and eliminated the core→marketplace boundary violation via dependency injection**

## What Happened

Extracted three oversized modules into smaller focused files:\n\n1. application/worktree/use_cases.py (1044→446 lines): Extracted 18 dataclass models into models.py (363 lines) and enter_worktree_shell/create_worktree into operations.py (320 lines).\n\n2. core/personal_profiles.py (839→554 lines): Extracted merge/diff/sandbox-import logic into personal_profiles_merge.py (321 lines). Boundary fix: merge_personal_settings now accepts managed_state_loader: Callable parameter. All 5 callers updated.\n\n3. application/launch/start_wizard.py (914→737 lines): Extracted 16 ViewModel/Option/Prompt dataclasses into wizard_models.py (215 lines).\n\nAll residual modules re-export extracted symbols for backward compatibility. No downstream import changes needed except for the managed_state_loader parameter.

## Verification

uv run ruff check — clean. uv run mypy src/scc_cli — clean (267 files). uv run pytest (full suite) — 4079 passed, 23 skipped, 4 xfailed. Targeted tests (worktree characterization, personal profiles characterization, import boundaries) — 64 passed. Boundary check: no marketplace imports in core/.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 4100ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4600ms |
| 3 | `uv run pytest tests/test_worktree_use_cases_characterization.py tests/test_personal_profiles_characterization.py tests/test_import_boundaries.py -q` | 0 | ✅ pass | 4900ms |
| 4 | `uv run pytest -q` | 0 | ✅ pass | 72300ms |

## Deviations

merge_personal_settings boundary fix uses Callable parameter with ValueError default instead of plain required parameter — provides safety net. operations.py uses lazy local imports to avoid circular dependencies between extracted modules.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/application/worktree/models.py`
- `src/scc_cli/application/worktree/operations.py`
- `src/scc_cli/application/worktree/use_cases.py`
- `src/scc_cli/core/personal_profiles_merge.py`
- `src/scc_cli/core/personal_profiles.py`
- `src/scc_cli/application/launch/wizard_models.py`
- `src/scc_cli/application/launch/start_wizard.py`
