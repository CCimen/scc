---
estimated_steps: 7
estimated_files: 4
skills_used: []
---

# T04: Refactor dashboard handlers and worktree create to use shared preflight

Refactor the three remaining launch paths:

1. orchestrator_handlers.py _handle_worktree_start(): Replace ~80 lines of inline preflight with resolve_launch_provider() + collect_launch_readiness() + ensure_launch_ready(). Remove import of flow.py::_allowed_provider_ids.
2. orchestrator_handlers.py _handle_session_resume(): Same — replace inline preflight. Pass session.provider_id as resume_provider.
3. worktree_commands.py worktree_create_cmd(): Replace resolve_active_provider() with resolve_launch_provider() + collect_launch_readiness() + ensure_launch_ready(). This adds image and auth bootstrap that were completely missing.
4. Rename start_claude parameter to start_agent (keep --start/--no-start CLI flags).
5. Thread provider_id through _record_session_and_context() → WorkContext constructor.

Verify characterization tests still pass. The worktree create tests should now show enhanced behavior (image + auth bootstrap).

## Inputs

- `src/scc_cli/commands/launch/preflight.py`

## Expected Output

- `src/scc_cli/ui/dashboard/orchestrator_handlers.py`
- `src/scc_cli/commands/worktree/worktree_commands.py`
- `src/scc_cli/commands/launch/flow_session.py`

## Verification

uv run pytest tests/test_launch_preflight_characterization.py tests/test_launch_preflight.py -v && uv run ruff check src/scc_cli/ui/dashboard/orchestrator_handlers.py src/scc_cli/commands/worktree/worktree_commands.py src/scc_cli/commands/launch/flow_session.py && uv run mypy src/scc_cli/ui/dashboard/orchestrator_handlers.py src/scc_cli/commands/worktree/worktree_commands.py src/scc_cli/commands/launch/flow_session.py
