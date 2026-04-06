---
estimated_steps: 10
estimated_files: 1
skills_used: []
---

# T01: Characterize current launch preflight behavior across all five sites

Write characterization tests capturing the current behavior of each launch preflight copy:

1. flow.py start() — provider resolution with full precedence (cli_flag, resume, workspace_last_used, config, auth probing)
2. flow_interactive.py run_start_wizard_flow() — inline provider resolution (no cli_flag, no resume_provider)
3. worktree_commands.py worktree_create_cmd() — uses resolve_active_provider() directly (missing workspace_last_used, missing image/auth bootstrap)
4. orchestrator_handlers.py _handle_worktree_start() — inline resolution + image + auth (imports _allowed_provider_ids from flow.py)
5. orchestrator_handlers.py _handle_session_resume() — inline resolution with resume_provider + image + auth

Also characterize:
- _record_session_and_context: verify WorkContext.provider_id is currently None
- Non-interactive behavior: verify each site's behavior when non_interactive=True and provider/image/auth is missing

These tests document current behavior as the regression baseline.

## Inputs

- `src/scc_cli/commands/launch/flow.py`
- `src/scc_cli/commands/launch/flow_interactive.py`
- `src/scc_cli/commands/worktree/worktree_commands.py`
- `src/scc_cli/ui/dashboard/orchestrator_handlers.py`
- `src/scc_cli/commands/launch/flow_session.py`

## Expected Output

- `tests/test_launch_preflight_characterization.py`

## Verification

uv run pytest tests/test_launch_preflight_characterization.py -v
