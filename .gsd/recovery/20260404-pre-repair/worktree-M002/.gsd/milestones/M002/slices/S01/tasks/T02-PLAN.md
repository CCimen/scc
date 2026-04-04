---
estimated_steps: 1
estimated_files: 5
skills_used: []
---

# T02: Adopt AgentProvider in launch preparation

Replace the live launch preparation dependency on `AgentRunner` with provider resolution and `AgentProvider.prepare_launch(...)`. Update the prepared-plan model to carry typed launch data, keep existing launch/resume behavior intact for the first migrated provider, and avoid introducing provider-native fields into core plan contracts.

## Inputs

- `T01 tests`
- `src/scc_cli/core/contracts.py`
- `src/scc_cli/adapters/claude_agent_runner.py`
- `src/scc_cli/adapters/docker_sandbox_runtime.py`

## Expected Output

- `live launch preparation using `AgentProvider.prepare_launch(...)``
- `updated typed plan objects carrying provider-neutral launch data`

## Verification

uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py
