---
estimated_steps: 14
estimated_files: 5
skills_used: []
---

# T03: Decompose docker/launch.py and marketplace/materialize.py with boundary fix

Extract docker/launch.py (874 lines) and marketplace/materialize.py (866 lines) into smaller focused files. Fix the docker→presentation boundary violation (console.err_line import).

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

## Inputs

- ``src/scc_cli/docker/launch.py` — 874-line module with console boundary violation`
- ``src/scc_cli/marketplace/materialize.py` — 866-line module to decompose`
- ``tests/test_docker_launch_characterization.py` — 27 characterization tests`
- ``tests/test_marketplace_materialize_characterization.py` — 24 characterization tests`
- ``tests/test_import_boundaries.py` — 31 boundary tests`

## Expected Output

- ``src/scc_cli/docker/launch.py` — residual under 800 lines with re-exports`
- ``src/scc_cli/docker/sandbox.py` — extracted sandbox functions (~300 lines) with boundary fix`
- ``src/scc_cli/marketplace/materialize.py` — residual under 800 lines with re-exports`
- ``src/scc_cli/marketplace/materialize_git.py` — extracted git clone/download functions (~250 lines)`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_docker_launch_characterization.py tests/test_marketplace_materialize_characterization.py tests/test_import_boundaries.py -q
