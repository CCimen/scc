---
estimated_steps: 32
estimated_files: 4
skills_used: []
---

# T06: Decompose setup.py and run final size verification

Extract setup.py (1336 lines — HARD-FAIL) into smaller focused files, then run the final comprehensive verification confirming all 15 targets are below threshold.

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

## Inputs

- ``src/scc_cli/setup.py` — 1336-line HARD-FAIL module to decompose`
- ``tests/test_setup_characterization.py` — 19 characterization tests`
- ``tests/test_import_boundaries.py` — 31 boundary tests`

## Expected Output

- ``src/scc_cli/setup.py` — residual under 800 lines with re-exports`
- ``src/scc_cli/setup_ui.py` — extracted TUI components (~400 lines)`
- ``src/scc_cli/setup_config.py` — extracted config logic (~300 lines)`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q && uv run pytest tests/test_*_characterization.py tests/test_import_boundaries.py -q && python3 -c "from pathlib import Path; [print(f'OVER 800: {f} ({len(f.read_text().splitlines())} lines)') for f in sorted(Path('src/scc_cli').rglob('*.py')) if len(f.read_text().splitlines()) > 800]"
