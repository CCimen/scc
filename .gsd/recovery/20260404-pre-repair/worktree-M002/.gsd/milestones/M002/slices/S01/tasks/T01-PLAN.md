---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T01: Characterize the live launch seam and target plan shape

Read the current `start_session`, `prepare_launch_plan`, bootstrap wiring, and runtime adapter usage in detail. Add or update focused tests that describe the intended S01 boundary: the prepared plan should carry a typed `AgentLaunchSpec`, and the executed path should depend on the provider seam rather than `AgentRunner`-built Claude settings. Keep scope to tests and plan-shape expectations; do not yet perform the full runtime rewiring.

## Inputs

- `.gsd/milestones/M002/M002-ROADMAP.md`
- `.gsd/milestones/M002/M002-CONTEXT.md`
- `src/scc_cli/core/contracts.py`
- `src/scc_cli/ports/agent_provider.py`
- `src/scc_cli/application/start_session.py`

## Expected Output

- `.gsd/milestones/M002/slices/S01/tasks/T01-PLAN.md`
- `updated focused tests covering the new launch-plan seam expectations`

## Verification

uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py
