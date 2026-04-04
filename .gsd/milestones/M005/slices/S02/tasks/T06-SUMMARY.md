---
id: T06
parent: S02
milestone: M005
key_files:
  - src/scc_cli/setup.py
  - src/scc_cli/setup_ui.py
  - src/scc_cli/setup_config.py
  - src/scc_cli/ui/dashboard/orchestrator_menus.py
  - src/scc_cli/ui/dashboard/orchestrator_handlers.py
  - tests/test_no_root_sprawl.py
key_decisions:
  - Kept run_non_interactive_setup in setup.py residual to preserve test-patch targets at scc_cli.setup.*
  - Extracted orchestrator_handlers.py secondary overflow (1163→846) into orchestrator_menus.py
duration: 
verification_result: passed
completed_at: 2026-04-04T16:57:08.252Z
blocker_discovered: false
---

# T06: Decomposed setup.py (1336→794 lines) and eliminated all HARD-FAIL files, completing S02 size reduction with all 4079 tests passing

**Decomposed setup.py (1336→794 lines) and eliminated all HARD-FAIL files, completing S02 size reduction with all 4079 tests passing**

## What Happened

Extracted TUI rendering components into setup_ui.py (303 lines) and config building/preview/persistence logic into setup_config.py (310 lines), reducing setup.py from 1336 to 794 lines. Kept run_non_interactive_setup in the residual to preserve test-patch targets. Also extracted secondary overflow in orchestrator_handlers.py (1163→846 lines) into orchestrator_menus.py (344 lines). Updated root sprawl allowlist. All 4079 tests pass, zero HARD-FAIL files remain, all 3 boundary violations confirmed clean.

## Verification

Full gate passes: ruff check (0 errors), mypy (0 errors in 283 files), pytest (4079 passed, 0 failed). All 315 characterization+boundary tests pass. All 19 setup characterization tests pass. Zero files exceed 1100 lines. 3 boundary violations confirmed eliminated via AST analysis.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 3700ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3700ms |
| 3 | `uv run pytest --rootdir "$PWD" -q` | 0 | ✅ pass | 69700ms |
| 4 | `uv run pytest tests/test_*_characterization.py tests/test_import_boundaries.py -q` | 0 | ✅ pass | 3200ms |
| 5 | `python3 -c 'file size check (no >1100)'` | 0 | ✅ pass | 100ms |

## Deviations

Kept run_non_interactive_setup in setup.py instead of setup_config.py to preserve test-patch compatibility. Added secondary extraction of orchestrator_handlers.py (not in original plan) to meet no-file-over-1100 must-have.

## Known Issues

orchestrator_handlers.py at 846 lines is WARNING level (>800) but below HARD-FAIL threshold (<1100).

## Files Created/Modified

- `src/scc_cli/setup.py`
- `src/scc_cli/setup_ui.py`
- `src/scc_cli/setup_config.py`
- `src/scc_cli/ui/dashboard/orchestrator_menus.py`
- `src/scc_cli/ui/dashboard/orchestrator_handlers.py`
- `tests/test_no_root_sprawl.py`
