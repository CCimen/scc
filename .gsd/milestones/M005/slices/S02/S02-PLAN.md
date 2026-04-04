# S02: Decompose oversized modules and repair boundaries

**Goal:** Split all 58+ oversized files into smaller cohesive modules aligned to clean-architecture boundaries. Fix all architecture boundary violations. Each resulting module should own one concern and be individually easy to understand, test, and modify.
**Demo:** After this: TBD

## Tasks
- [ ] **T01: Decompose launch flow and application orchestration** — 
  - Files: src/scc_cli/commands/launch/flow.py, src/scc_cli/commands/launch/render.py, src/scc_cli/commands/launch/sandbox.py, src/scc_cli/commands/launch/workspace.py, src/scc_cli/application/launch/start_wizard.py, src/scc_cli/application/start_session.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest
- [ ] **T02: Decompose UI layer modules** — 
  - Files: src/scc_cli/ui/dashboard/orchestrator.py, src/scc_cli/ui/settings.py, src/scc_cli/ui/dashboard/_dashboard.py, src/scc_cli/ui/wizard.py, src/scc_cli/ui/git_interactive.py, src/scc_cli/ui/picker.py, src/scc_cli/ui/keys.py, src/scc_cli/ui/chrome.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest
- [ ] **T03: Decompose commands layer modules** — 
  - Files: src/scc_cli/commands/team.py, src/scc_cli/commands/config.py, src/scc_cli/commands/profile.py, src/scc_cli/commands/reset.py, src/scc_cli/commands/exceptions.py, src/scc_cli/commands/admin.py, src/scc_cli/commands/worktree/container_commands.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest
- [ ] **T04: Decompose application, docker, and marketplace layers** — 
  - Files: src/scc_cli/application/dashboard.py, src/scc_cli/application/worktree/use_cases.py, src/scc_cli/application/compute_effective_config.py, src/scc_cli/application/settings/use_cases.py, src/scc_cli/docker/launch.py, src/scc_cli/docker/credentials.py, src/scc_cli/docker/core.py, src/scc_cli/marketplace/materialize.py, src/scc_cli/marketplace/team_fetch.py, src/scc_cli/marketplace/normalize.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest
- [ ] **T05: Repair all architecture boundary violations** — 
  - Files: src/scc_cli/core/personal_profiles.py, src/scc_cli/core/maintenance.py, src/scc_cli/docker/launch.py, src/scc_cli/marketplace/sync.py, src/scc_cli/application/dashboard.py, src/scc_cli/ports/doctor_runner.py, src/scc_cli/ports/git_client.py, src/scc_cli/ui/dashboard/orchestrator.py, src/scc_cli/ui/formatters.py, src/scc_cli/ui/picker.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest; verify no core/ file imports from docker/, commands/, ui/, marketplace/; verify no docker/ file imports from console or ui/
- [ ] **T06: Decompose remaining oversized modules and clean up setup.py** — 
  - Files: src/scc_cli/setup.py, src/scc_cli/core/personal_profiles.py, src/scc_cli/remote.py, src/scc_cli/validate.py, src/scc_cli/config.py, src/scc_cli/services/git/worktree.py, src/scc_cli/claude_adapter.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest; no file in src/scc_cli exceeds the guardrail threshold
