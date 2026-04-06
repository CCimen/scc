---
estimated_steps: 10
estimated_files: 4
skills_used: []
---

# T02: Remove Docker Desktop references from active user-facing paths and verify lifecycle inventory consistency

Docker Desktop cleanup:
1. admin.py:480 — change 'Ensure Docker Desktop is running' to 'Ensure Docker is running'
2. container_commands.py:304 prune_cmd comment — reword to mention 'containers not created by SCC' rather than 'Docker Desktop'
3. Scan all remaining user-facing strings in commands/ for 'Docker Desktop' via rg — fix to 'Docker' or 'container runtime'
4. Keep Docker Desktop references ONLY in: docker/core.py, docker/launch.py, docker/sandbox.py, adapters/docker_sandbox_runtime.py, adapters/docker_runtime_probe.py, core/errors.py (typed error for Desktop-specific failures)

Lifecycle inventory consistency:
5. Verify scc list, scc stop, scc prune, scc status, dashboard container actions, and session resume all use docker.list_scc_containers() or its running variant as the SCC-managed inventory source
6. Check that stale/non-SCC containers (no scc labels) don't pollute the active inventory
7. Write a focused test verifying inventory consistency across command surfaces

Update test_docs_truthfulness.py with Docker Desktop boundary guardrail.

## Inputs

- None specified.

## Expected Output

- `tests/test_lifecycle_inventory_consistency.py`

## Verification

uv run pytest tests/test_docs_truthfulness.py tests/test_lifecycle_inventory_consistency.py -v && uv run ruff check
