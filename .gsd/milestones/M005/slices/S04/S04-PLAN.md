# S04: Error handling, subprocess hardening, and fail-closed cleanup

**Goal:** Make error handling explicit, consistent, and robust across CLI, JSON, and audit surfaces. Eliminate all 27 bare except+pass sites, harden all subprocess calls, freeze all mutable global state, and ensure fail-closed behavior on security/policy paths.
**Demo:** After this: TBD

## Tasks
- [ ] **T01: Eliminate all silent error swallowing** — 
  - Files: src/scc_cli/application/dashboard.py, src/scc_cli/ui/dashboard/orchestrator.py, src/scc_cli/docker/credentials.py, src/scc_cli/application/settings/use_cases.py, src/scc_cli/core/personal_profiles.py, src/scc_cli/maintenance/*.py, src/scc_cli/update.py, src/scc_cli/utils/ttl.py, src/scc_cli/ui/picker.py, src/scc_cli/commands/launch/flow.py
  - Verify: grep -rn "except.*:\s*$" src/scc_cli followed by grep for "pass" shows zero silent swallows without justification; uv run pytest passes
- [ ] **T02: Harden subprocess handling** — 
  - Files: src/scc_cli/config.py, src/scc_cli/ui/git_interactive.py, src/scc_cli/commands/worktree/worktree_commands.py, src/scc_cli/marketplace/materialize.py, src/scc_cli/marketplace/team_fetch.py, src/scc_cli/ui/dashboard/orchestrator.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest
- [ ] **T03: Freeze mutable global state and security defaults** — 
  - Files: src/scc_cli/docker/launch.py, src/scc_cli/maintenance/tasks.py, src/scc_cli/application/settings/use_cases.py, src/scc_cli/update.py, src/scc_cli/core/network_policy.py, src/scc_cli/ui/help.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest
- [ ] **T04: Strengthen exception taxonomy and ensure fail-closed behavior** — 
  - Files: src/scc_cli/core/errors.py, src/scc_cli/core/error_mapping.py, src/scc_cli/json_command.py, src/scc_cli/commands/**/*.py, src/scc_cli/application/*.py, src/scc_cli/docker/*.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest
- [ ] **T05: Verify audit event consistency across all error paths** — 
  - Files: src/scc_cli/core/errors.py, src/scc_cli/ui/dashboard/orchestrator.py, tests/test_core_errors.py, tests/test_error_mapping.py
  - Verify: uv run pytest tests/test_core_errors.py tests/test_error_mapping.py && uv run pytest
