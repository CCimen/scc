---
estimated_steps: 12
estimated_files: 5
skills_used: []
---

# T02: Write characterization tests for top-4 mandatory-split targets before S02 surgery

Add behavioral characterization tests for the four highest-priority split targets identified in T01's audit. These tests protect existing behavior before S02 surgery decomposes these modules. docker/launch.py already has existing tests in test_docker_launch_characterization.py — extend coverage there rather than duplicating.

Targets and approach:
1. `commands/launch/flow.py` (1447 lines) — Create `tests/test_launch_flow_characterization.py` targeting wizard state machine logic, session selection, CLI error paths. Use mock adapters from tests/fakes/.
2. `ui/dashboard/orchestrator.py` (1489 lines) — Create `tests/test_dashboard_orchestrator_characterization.py` targeting view building, event routing, effect result application, tab fallbacks, placeholder helpers.
3. `docker/launch.py` (874 lines) — Extend `tests/test_docker_launch_characterization.py` with safety-net policy chain, atomic file writing, run_sandbox failure branches, mount race detection.
4. `core/personal_profiles.py` (839 lines) — Create `tests/test_personal_profiles_characterization.py` targeting CRUD operations, listing edge cases, MCP merge, applied-state tracking.

Also create `tests/test_import_boundaries.py` to codify the boundary violations identified in T01 as test assertions.

Key constraints:
- Tests target pure application-layer logic rather than mocking full TUI interactions
- Use existing fakes/fixtures from tests/conftest.py and tests/fakes/
- No production source code modified
- Allowlist new test files in boundary guard with M005/S01/T02 tracking comment

## Inputs

- ``src/scc_cli/commands/launch/flow.py` — primary characterization target (1447 lines)`
- ``src/scc_cli/ui/dashboard/orchestrator.py` — primary characterization target (1489 lines)`
- ``src/scc_cli/docker/launch.py` — characterization target (874 lines)`
- ``src/scc_cli/core/personal_profiles.py` — characterization target (839 lines)`
- ``tests/conftest.py` — existing fixtures`
- ``tests/fakes/` — fake adapters`
- ``tests/test_docker_launch_characterization.py` — existing characterization tests to extend`
- ``.gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md` — confirms mandatory-split targets from T01`

## Expected Output

- ``tests/test_launch_flow_characterization.py` — behavioral characterization tests for commands/launch/flow.py`
- ``tests/test_dashboard_orchestrator_characterization.py` — characterization tests for ui/dashboard/orchestrator.py`
- ``tests/test_docker_launch_characterization.py` — extended characterization tests for docker/launch.py`
- ``tests/test_personal_profiles_characterization.py` — characterization tests for core/personal_profiles.py`
- ``tests/test_import_boundaries.py` — boundary violation assertions codified as tests`

## Verification

uv run pytest tests/test_launch_flow_characterization.py tests/test_dashboard_orchestrator_characterization.py tests/test_docker_launch_characterization.py tests/test_personal_profiles_characterization.py tests/test_import_boundaries.py -v && uv run pytest && uv run mypy src/scc_cli && uv run ruff check
