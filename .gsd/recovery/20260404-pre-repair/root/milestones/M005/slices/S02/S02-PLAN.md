# S02: Decompose oversized orchestrators and mixed-responsibility modules

**Goal:** Split all 58+ oversized files into smaller cohesive modules aligned to clean-architecture boundaries. Fix all architecture boundary violations. Each resulting module should own one concern and be individually easy to understand, test, and modify.
**Demo:** After this slice, no module mixes control-plane, runtime, and provider concerns. No file exceeds the complexity/size guardrails. All boundary violations identified in S01 are resolved.

## Tasks
- [ ] **T01: Decompose launch flow and application orchestration** — Split commands/launch/flow.py (1665 lines) into focused units: config resolution, provider dispatch, launch plan assembly, interactive flow state machine, and runtime handoff. Split application/launch/start_wizard.py (914 lines) by wizard phase. Split application/start_session.py where mixed concerns exist. Each resulting module should own one concern.
  - Estimate: large
  - Files: src/scc_cli/commands/launch/flow.py, src/scc_cli/commands/launch/render.py, src/scc_cli/commands/launch/sandbox.py, src/scc_cli/commands/launch/workspace.py, src/scc_cli/application/launch/start_wizard.py, src/scc_cli/application/start_session.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest

- [ ] **T02: Decompose UI layer modules** — Split ui/dashboard/orchestrator.py (1493 lines), ui/settings.py (1081 lines), ui/dashboard/_dashboard.py (966 lines), ui/wizard.py (931 lines), ui/git_interactive.py (884 lines), ui/picker.py (786 lines), ui/keys.py (784 lines), and ui/chrome.py (590 lines) into focused modules by responsibility (data loading, rendering, interaction handling, state management).
  - Estimate: large
  - Files: src/scc_cli/ui/dashboard/orchestrator.py, src/scc_cli/ui/settings.py, src/scc_cli/ui/dashboard/_dashboard.py, src/scc_cli/ui/wizard.py, src/scc_cli/ui/git_interactive.py, src/scc_cli/ui/picker.py, src/scc_cli/ui/keys.py, src/scc_cli/ui/chrome.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest

- [ ] **T03: Decompose commands layer modules** — Split commands/team.py (1036 lines), commands/config.py (1029 lines), commands/profile.py (715 lines), commands/reset.py (632 lines), commands/exceptions.py (685 lines), and commands/admin.py (701 lines) into focused modules. Extract pure business logic from CLI wiring. Route docker calls through SandboxRuntime port instead of calling docker.* directly.
  - Estimate: medium
  - Files: src/scc_cli/commands/team.py, src/scc_cli/commands/config.py, src/scc_cli/commands/profile.py, src/scc_cli/commands/reset.py, src/scc_cli/commands/exceptions.py, src/scc_cli/commands/admin.py, src/scc_cli/commands/worktree/container_commands.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest

- [ ] **T04: Decompose application, docker, and marketplace layers** — Split application/dashboard.py (1084 lines, 33 classes), application/worktree/use_cases.py (1044 lines), application/compute_effective_config.py (775 lines), application/settings/use_cases.py (703 lines). Split docker/launch.py (925 lines), docker/credentials.py (743 lines), docker/core.py (620 lines). Split marketplace/materialize.py (866 lines), marketplace/team_fetch.py (689 lines), marketplace/normalize.py (553 lines). Extract models into dedicated model files where classes are mixed with logic.
  - Estimate: large
  - Files: src/scc_cli/application/dashboard.py, src/scc_cli/application/worktree/use_cases.py, src/scc_cli/application/compute_effective_config.py, src/scc_cli/application/settings/use_cases.py, src/scc_cli/docker/launch.py, src/scc_cli/docker/credentials.py, src/scc_cli/docker/core.py, src/scc_cli/marketplace/materialize.py, src/scc_cli/marketplace/team_fetch.py, src/scc_cli/marketplace/normalize.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest

- [ ] **T05: Repair all architecture boundary violations** — Fix every violation cataloged in S01/T02: (1) Remove core/personal_profiles.py dependency on marketplace/ — extract marketplace interaction to an adapter or application-layer caller. (2) Remove core/maintenance.py shim that re-exports maintenance/. (3) Remove docker/launch.py import of console — signal errors via exceptions, not console calls. (4) Route all commands/* and ui/* docker calls through SandboxRuntime port. (5) Break marketplace/sync.py → application/sync_marketplace.py circular dependency. (6) Move port type dependencies from doctor/ and services/ into ports/ or core/. (7) Remove application/dashboard.py module-level docker.core import.
  - Estimate: medium
  - Files: src/scc_cli/core/personal_profiles.py, src/scc_cli/core/maintenance.py, src/scc_cli/docker/launch.py, src/scc_cli/marketplace/sync.py, src/scc_cli/application/dashboard.py, src/scc_cli/ports/doctor_runner.py, src/scc_cli/ports/git_client.py, src/scc_cli/ui/dashboard/orchestrator.py, src/scc_cli/ui/formatters.py, src/scc_cli/ui/picker.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest; verify no core/ file imports from docker/, commands/, ui/, marketplace/; verify no docker/ file imports from console or ui/

- [ ] **T06: Decompose remaining oversized modules and clean up setup.py** — Split setup.py (1336 lines, 32 functions), core/personal_profiles.py (839 lines, 47 functions), remote.py (491 lines), validate.py (489 lines), config.py (521 lines), services/git/worktree.py (556 lines), claude_adapter.py (506 lines), and any remaining files over the complexity/size guardrail threshold.
  - Estimate: medium
  - Files: src/scc_cli/setup.py, src/scc_cli/core/personal_profiles.py, src/scc_cli/remote.py, src/scc_cli/validate.py, src/scc_cli/config.py, src/scc_cli/services/git/worktree.py, src/scc_cli/claude_adapter.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest; no file in src/scc_cli exceeds the guardrail threshold
