---
estimated_steps: 34
estimated_files: 4
skills_used: []
---

# T02: Add characterization tests for top-4 split targets before S02 surgery

Write characterization tests that capture current behavior of the top-4 mandatory-split targets. These tests protect against accidental behavior changes when S02 decomposes these modules. The targets are:

1. **`commands/launch/flow.py`** — `interactive_start` (534 lines) and `start` (293 lines). Current tests are AST-level guardrails only. Write behavioral tests that verify:
   - `start()` returns early with appropriate error when no git repo is found
   - `start()` handles team override parameter correctly
   - `interactive_start()` delegates to resume helpers when resume context is provided
   - Test file: `tests/test_launch_flow_characterization.py`

2. **`ui/dashboard/orchestrator.py`** — `run_dashboard` (232 lines) and action handlers. Only 6% coverage. Write tests that verify:
   - `run_dashboard` handles empty session list gracefully
   - Dashboard action dispatch routes to correct handlers
   - Team switch flow is invoked when team switch is requested
   - Test file: `tests/test_dashboard_orchestrator_characterization.py`

3. **`docker/launch.py`** — `run_sandbox` (216 lines). 54% coverage. Write tests that verify:
   - Safety policy injection is applied to container config
   - Container name generation follows expected format
   - Failure branches (docker not available, image pull failure) produce correct errors
   - Test file: `tests/test_docker_launch_characterization.py`

4. **`core/personal_profiles.py`** — Only 7 tests for 839 lines. Write tests that verify:
   - Profile CRUD operations (create, read, update, delete)
   - Profile listing returns expected structure
   - Marketplace-state interaction (load/save managed state)
   - Edge cases: nonexistent profile, duplicate name, empty profile list
   - Test file: `tests/test_personal_profiles_characterization.py`

**Testing patterns to follow:**
- Use existing `tests/conftest.py` fixtures (`temp_dir`, `temp_git_repo`, `build_fake_adapters`)
- Use existing `tests/fakes/` for fake adapters where needed
- Use `unittest.mock.patch` for heavy external dependencies (docker, git, subprocess, filesystem)
- Use `from __future__ import annotations` in all new test files
- Each test function should have a docstring explaining what behavior it captures
- Mark any test that cannot be made fully deterministic with `pytest.mark.skip` and a note, rather than writing a flaky test

**Constraints:**
- Do NOT modify any production code.
- All tests must pass when run individually AND as part of the full suite.
- Tests must not make network calls, start containers, or access real filesystem paths outside temp dirs.
- Target: at least 3-5 meaningful behavioral tests per module (12-20 total new tests).

## Inputs

- `src/scc_cli/commands/launch/flow.py`
- `src/scc_cli/ui/dashboard/orchestrator.py`
- `src/scc_cli/docker/launch.py`
- `src/scc_cli/core/personal_profiles.py`
- `tests/conftest.py`
- `tests/fakes/fake_sandbox_runtime.py`
- `tests/fakes/fake_agent_runner.py`
- `tests/fakes/fake_safety_engine.py`
- `.gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md`

## Expected Output

- `tests/test_launch_flow_characterization.py`
- `tests/test_dashboard_orchestrator_characterization.py`
- `tests/test_docker_launch_characterization.py`
- `tests/test_personal_profiles_characterization.py`

## Verification

uv run pytest tests/test_launch_flow_characterization.py tests/test_dashboard_orchestrator_characterization.py tests/test_docker_launch_characterization.py tests/test_personal_profiles_characterization.py -v && uv run mypy src/scc_cli && uv run ruff check
