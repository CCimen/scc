---
id: T05
parent: S02
milestone: M005
key_files:
  - src/scc_cli/ui/dashboard/orchestrator_handlers.py
  - src/scc_cli/ui/dashboard/_dashboard_actions.py
  - src/scc_cli/ui/settings_profile.py
  - src/scc_cli/ui/wizard_pickers.py
  - src/scc_cli/ui/git_interactive_ops.py
  - src/scc_cli/ui/dashboard/orchestrator.py
  - src/scc_cli/ui/dashboard/_dashboard.py
  - src/scc_cli/ui/settings.py
  - src/scc_cli/ui/wizard.py
  - src/scc_cli/ui/git_interactive.py
key_decisions:
  - Used late-bound module lookup (_get_picker/_get_confirm_with_layout) in extracted modules to preserve test-patch compatibility with existing mock targets on original module paths
  - Re-exported all moved symbols from original modules with noqa:F401 for backward compatibility
duration: 
verification_result: passed
completed_at: 2026-04-04T16:35:57.751Z
blocker_discovered: false
---

# T05: Decomposed five HARD-FAIL/MANDATORY-SPLIT UI modules (1492, 968, 1081, 931, 884 lines) into focused files all under 800 lines while preserving all 4079 tests

**Decomposed five HARD-FAIL/MANDATORY-SPLIT UI modules (1492, 968, 1081, 931, 884 lines) into focused files all under 800 lines while preserving all 4079 tests**

## What Happened

Extracted five UI-layer modules into smaller focused files: orchestrator.py (1492→399), _dashboard.py (968→611), settings.py (1081→792), wizard.py (931→416), git_interactive.py (884→543). Created five new extraction targets: orchestrator_handlers.py, _dashboard_actions.py, settings_profile.py, wizard_pickers.py, git_interactive_ops.py. Used late-bound module lookup pattern for extracted functions that tests patch on the original module path, ensuring all 4079 tests continue to pass.

## Verification

uv run ruff check — All checks passed. uv run mypy src/scc_cli — Success: no issues found in 280 source files. uv run pytest -q — 4079 passed, 23 skipped, 4 xfailed in 65s.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 4000ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 7000ms |
| 3 | `uv run pytest -q` | 0 | ✅ pass | 65000ms |

## Deviations

Used late-bound lookup pattern (_get_picker/_get_confirm_with_layout) instead of direct imports to preserve test-patch compatibility. Did not extract _render from settings.py — profile sync extraction was sufficient to bring it under 800 lines.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/ui/dashboard/orchestrator_handlers.py`
- `src/scc_cli/ui/dashboard/_dashboard_actions.py`
- `src/scc_cli/ui/settings_profile.py`
- `src/scc_cli/ui/wizard_pickers.py`
- `src/scc_cli/ui/git_interactive_ops.py`
- `src/scc_cli/ui/dashboard/orchestrator.py`
- `src/scc_cli/ui/dashboard/_dashboard.py`
- `src/scc_cli/ui/settings.py`
- `src/scc_cli/ui/wizard.py`
- `src/scc_cli/ui/git_interactive.py`
