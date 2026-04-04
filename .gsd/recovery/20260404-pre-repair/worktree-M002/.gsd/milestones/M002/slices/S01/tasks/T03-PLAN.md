---
estimated_steps: 1
estimated_files: 6
skills_used: []
---

# T03: Execute the typed launch plan through runtime

Rewire live launch execution to consume the typed launch plan end-to-end, remove the old `AgentRunner` dependency from the executed path, and update the runtime adapter/tests so the launch seam is the real seam. Finish with the fixed gate.

## Inputs

- `T02 implementation`
- `src/scc_cli/docker/core.py`
- `src/scc_cli/core/network_policy.py`

## Expected Output

- `runtime execution consuming typed provider launch data`
- `full milestone gate passing after S01 seam adoption`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest
