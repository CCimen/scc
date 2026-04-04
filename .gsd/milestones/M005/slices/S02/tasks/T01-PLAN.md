---
estimated_steps: 16
estimated_files: 4
skills_used: []
---

# T01: Decompose application/dashboard.py with boundary fix

Extract the application/dashboard.py module (1084 lines) into three focused files: models, loaders, and residual event/effect logic. Fix the docker.core.ContainerInfo boundary violation in the loaders by introducing a local TypeAlias.

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

## Inputs

- ``src/scc_cli/application/dashboard.py` — 1084-line module to decompose`
- ``tests/test_app_dashboard_characterization.py` — 40 characterization tests protecting behavior`
- ``tests/test_import_boundaries.py` — 31 boundary tests to keep passing`

## Expected Output

- ``src/scc_cli/application/dashboard.py` — residual event/effect logic under 800 lines with re-exports`
- ``src/scc_cli/application/dashboard_models.py` — extracted dataclass/enum model definitions (~380 lines)`
- ``src/scc_cli/application/dashboard_loaders.py` — extracted tab loader functions (~360 lines) with boundary fix`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_app_dashboard_characterization.py tests/test_import_boundaries.py -q
