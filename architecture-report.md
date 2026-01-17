# SCC Architecture & Code Review Guide

Date: 2026-01-17
Scope: `scc/` (source under `scc/src/scc_cli`, Python only)

## Summary
- Entry point: `pyproject.toml` exposes `scc = scc_cli.cli:main` which calls `scc/src/scc_cli/cli.py`.
- Source inventory: 182 Python files, 49,503 total lines (Appendix A).
- Core responsibilities: sandboxed Claude Code execution in Docker, organization/team config resolution, plugin marketplace sync, git worktree management, Rich-based TUI, and structured JSON output.
- New seams: `application/` use cases, `ports/` + `adapters/`, and `bootstrap.py` composition root.
- Purpose: handoff document for agents doing a full code review (flows, coupling, and checklist included).

## Architecture Overview
SCC is a layered CLI/TUI application with a deliberate split between orchestration, pure services, and presentation:

```
CLI (Typer)
  -> commands/* (orchestration, argument parsing)
     -> application/* (use cases and orchestration)
        -> ports/* (Protocol boundaries)
        -> adapters/* (Docker/Claude/Requests implementations) via bootstrap.py
     -> services/* (git/workspace pure functions)
     -> core/* (errors, exit codes, maintenance)
     -> marketplace/* (config parsing, trust, compute, materialize, render, sync)
     -> docker/* (sandbox lifecycle, credentials, policy injection)
     -> persistence (config, sessions, contexts, profiles, stores)
  -> ui/* (Rich TUI, dashboard, pickers)
  -> json_* / output_mode (structured output)
External: Docker CLI, Git CLI, HTTP (requests)
```

## Subsystem Map
- CLI entry + routing: `scc/src/scc_cli/cli.py`, `scc/src/scc_cli/cli_common.py`.
- Command modules: `scc/src/scc_cli/commands/*` (start, worktree, team, org, config, admin, profile, audit, support).
- Application layer: `scc/src/scc_cli/application/*` (start_session, sync_marketplace, settings, dashboard).
- Ports + adapters: `scc/src/scc_cli/ports/*`, `scc/src/scc_cli/adapters/*`, wired in `scc/src/scc_cli/bootstrap.py`.
- Workspace resolution: `scc/src/scc_cli/services/workspace/resolver.py`, `.../suspicious.py`, `scc/src/scc_cli/core/workspace.py`.
- Git services: `scc/src/scc_cli/services/git/*` (pure), with facade in `scc/src/scc_cli/git.py`.
- Docker sandbox: `scc/src/scc_cli/docker/*`, entry in `docker/__init__.py`, launch orchestration in `docker/launch.py`, credential persistence in `docker/credentials.py`.
- Marketplace pipeline: `scc/src/scc_cli/marketplace/*` (schema, compute, resolve, materialize, render, sync, trust).
- Config + remote: `scc/src/scc_cli/config.py`, `remote.py`, `auth.py`, `source_resolver.py`.
- User state: `sessions.py`, `contexts.py`, `core/personal_profiles.py`, `stores/exception_store.py`.
- Maintenance tasks: `scc/src/scc_cli/maintenance/*` (cache cleanup, migrations, health checks) with wrapper in `core/maintenance.py`.
- TUI: `scc/src/scc_cli/ui/*`, dashboard modules under `ui/dashboard/*`, list engine in `ui/list_screen.py`.
- Diagnostics: `doctor/*`, `stats.py`, `audit/*`, `evaluation/*`.
- Output: `json_command.py`, `json_output.py`, `output_mode.py`, `core/errors.py`, `core/exit_codes.py`.

## Key Flows

### Smart Start (`scc` with no args)
1. `cli.py` callback evaluates flags, version, and interactivity.
2. Auto-detects workspace via `services/workspace/resolve_launch_context`.
3. If interactive, runs `ui/dashboard/orchestrator.run_dashboard`; otherwise invokes `commands.launch.start` with defaults.

### Start/Launch (`scc start`)
1. `commands/launch/app.py` parses CLI flags and builds a `StartSessionRequest`.
2. `application/start_session.prepare_start_session` resolves workspace + effective config and runs marketplace sync.
3. `AgentRunner` builds `AgentSettings` from rendered marketplace settings.
4. `SandboxSpec` assembled with mount + env details.
5. `SandboxRuntime.run` launches the sandbox (default Docker adapter via `bootstrap.py`).

### Worktrees
- `commands/worktree/*` orchestrates creation/listing/removal and calls git services.
- Pure git worktree logic in `services/git/worktree.py`.
- Interactive UX and rendering via `ui/git_interactive.py` and `ui/git_render.py`.

### Org/Team Configuration
- `setup.py` drives onboarding and writes user config.
- `remote.py` fetches org config with HTTPS-only validation and auth gating.
- `profiles.py` computes effective config with security policy, delegation, and blocked items.
- `marketplace/schema.py` provides strict Pydantic models for org config.

### Marketplace Sync Pipeline
`marketplace/sync.py` orchestrates:
1. Pydantic validation (`marketplace/schema.py`).
2. Resolve effective plugins and marketplaces (`marketplace/resolve.py`, `marketplace/compute.py`).
3. Materialize marketplace artifacts (`marketplace/materialize.py`).
4. Render Claude settings (`marketplace/render.py` + `claude_adapter.py`).
5. Merge settings and persist managed state (`marketplace/managed.py`).

### Dashboard (TUI)
- `ui/dashboard/orchestrator.py` is the outer loop and flow dispatcher.
- `ui/dashboard/_dashboard.py` handles rendering and the input loop.
- `ui/list_screen.py` provides the reusable list/navigation engine.

### JSON Output Mode
- `json_command.py` decorates commands for envelope output.
- `output_mode.py` provides ContextVar-based output suppression and JSON printing.
- `cli_common.handle_errors` provides human/JSON error handling for non-json-command flows.

## Design Patterns and Architectural Styles
- Command pattern: Typer apps + command modules in `commands/*`.
- Facade pattern: `git.py` and `docker/__init__.py` re-export internal APIs (UI helpers live in `ui/*`).
- Ports & adapters: `ports/*` + `adapters/*` wired by `bootstrap.py`.
- Decorator pattern: `cli_common.handle_errors`, `json_command.json_command`.
- Orchestrator pattern: `commands/launch/app.py`, `marketplace/sync.py`, `ui/dashboard/orchestrator.py`.
- Adapter pattern: `claude_adapter.py` isolates Claude settings format.
- Functional core / imperative shell: pure compute modules (`services/*`, `marketplace/compute.py`) with side-effect orchestration in commands and docker/remote modules.
- DTOs via dataclasses: `ResolverResult`, `WorkContext`, `SessionRecord`, `EffectiveConfig`, `TeamInfo`, and more.
- Event-loop TUI: `ui/list_screen.py` and `ui/dashboard/_dashboard.py` implement stateful input loops.

## Maintainability and Coupling Assessment

### Strengths
- Clear layering between services, core domain, and UI rendering.
- Typed error taxonomy with standardized exit codes (`core/errors.py`, `core/exit_codes.py`).
- Defensive filesystem patterns (atomic writes, file locks, cache TTLs).
- Explicit JSON output mode with separation of human vs machine output.
- Security-first defaults: suspicious directory gating, safety-net policy injection, HTTPS-only org config.
- Claude settings isolated behind `claude_adapter.py` to reduce blast radius for format changes.

### Risks / Hotspots
- Large modules that concentrate multiple responsibilities:
  - `commands/launch/app.py` (1378 lines)
  - `ui/dashboard/orchestrator.py` (1374)
  - `ui/settings.py` (1416)
  - `ui/dashboard/_dashboard.py` (1025)
  - `profiles.py` (1000)
- Maintenance logic is now split into `maintenance/*`, but the settings/dashboard/profiles hotspots remain.
- Cross-layer coupling via facades remains a risk, though `git.py` no longer re-exports UI helpers.
- Dual error handling paths (`handle_errors` vs `json_command`) can produce divergent behavior; check for consistency in mixed flows.
- Global state (`cli_common.state.debug`, `output_mode` ContextVars) requires careful test isolation.
- Multiple workspace detection paths (`services/workspace/resolver.py` vs `services/git/core.detect_workspace_root`) increase risk of drift.
- UI modules import config/services directly; difficult to unit test without stubbing filesystem and Docker/Git dependencies.

### Coupling Effects to Watch
- Commands invoking UI functions (`ui/*`) directly (tight coupling between CLI and TUI).
- Facade modules (`git.py`, `docker/__init__.py`) expose many internal functions, increasing surface area.
- Marketplace pipeline couples network fetch, schema validation, file writes, and settings render; failures can cascade if not isolated.

### Coupling Map (What Depends on What)
- CLI entry -> commands: `cli.py` imports `commands/*` Typer apps plus `ui/dashboard/orchestrator.py` for interactive start.
- Commands -> services/core: most `commands/*` import `services/*` (git/workspace) and `core/*` errors/exit codes.
- Commands -> UI: `commands/*` invoke `ui/*` pickers, panels, and prompts (`ui/picker.py`, `ui/prompts.py`, `ui/git_interactive.py`).
- Commands -> marketplace: `commands/launch/app.py`, `commands/team.py`, `commands/org/*` depend on `marketplace/*` for config and trust.
- Commands -> docker: `commands/launch/sandbox.py` uses `docker/*` for container lifecycle.
- Marketplace -> persistence: `marketplace/sync.py` writes `.claude/settings.local.json` and managed state via `marketplace/managed.py`.
- Marketplace -> remote/auth: `marketplace/materialize.py` and `team_fetch.py` use network fetching and auth resolution.
- UI -> services/core: `ui/dashboard/loaders.py` reads git status/worktrees and sessions, bridging UI to domain.
- UI -> config: `ui/settings.py`, `ui/wizard.py` and onboarding flow read/write user config.

### Coupled Areas That Affect Review Scope
- `scc/src/scc_cli/commands/launch/app.py` ties together workspace resolution, config, marketplace sync, and docker launch.
- `scc/src/scc_cli/ui/dashboard/orchestrator.py` ties together git status, sessions, worktrees, and container lifecycle.
- `scc/src/scc_cli/profiles.py` ties org config, project overrides, and plugin policy computation.
- `scc/src/scc_cli/marketplace/sync.py` ties schema validation, marketplace materialization, settings merge, and file IO.
- `scc/src/scc_cli/git.py` re-exports service APIs only; UI helpers live in `ui/git_interactive.py` and `ui/git_render.py`.

### Module Responsibility Matrix (Review Cheatsheet)
| Area | Primary Modules | Downstream Dependencies |
| --- | --- | --- |
| CLI entry | `cli.py`, `cli_common.py` | `commands/*`, `ui/dashboard/*`, `output_mode.py` |
| Launch flow | `commands/launch/*` | `services/workspace/*`, `profiles.py`, `marketplace/*`, `docker/*` |
| Config/org/team | `config.py`, `teams.py`, `commands/org/*` | `remote.py`, `marketplace/*`, `auth.py` |
| Marketplace | `marketplace/*`, `claude_adapter.py` | `remote.py`, `profiles.py`, `.claude` files |
| Git/worktree | `services/git/*`, `commands/worktree/*` | `ui/git_*`, `ui/dashboard/*` |
| UI/TUI | `ui/*`, `ui/dashboard/*` | `services/*`, `config.py`, `sessions.py` |
| Persistence | `sessions.py`, `contexts.py`, `core/personal_profiles.py` | filesystem, `.scc`/`.claude` files |

## Code Review Focus Areas
- Security gating and safe defaults: suspicious workspace handling and policy injection (`services/workspace/suspicious.py`, `docker/launch.py`).
- Org config trust model and auth command gating (`auth.py`, `remote.py`, `claude_adapter.py`).
- Marketplace sync correctness: canonical name collisions, managed state merge rules, container-only settings injection (`marketplace/sync.py`, `marketplace/materialize.py`).
- Docker credential persistence and detached run pattern (`docker/credentials.py`, `docker/launch.py`).
- Consistency of error reporting between JSON and human modes (`cli_common.py`, `json_command.py`, `output_mode.py`).
- TUI state transitions and Live rendering loops (`ui/list_screen.py`, `ui/dashboard/*`).

## Review Checklist (For Agent Use)
- Entry/dispatch: verify `cli.py` routes each command correctly and respects `--json`, `--no-interactive`, and `--debug` (`cli_common.py`).
- Error discipline: ensure errors use `core/errors.py` types with user_message/suggested_action and exit codes from `core/exit_codes.py`.
- External calls: check `subprocess_utils.run_command` usage and ensure `shell=False` unless explicitly required.
- Filesystem writes: confirm atomic writes and path normalization (`contexts.py`, `core/personal_profiles.py`, `marketplace/managed.py`).
- Network boundaries: ensure HTTPS-only and auth gating (`remote.py`, `marketplace/materialize.py`, `marketplace/team_fetch.py`).
- Plugin policy: verify blocked/allowed/disabled logic in `marketplace/compute.py` and trust enforcement in `marketplace/trust.py`.
- Docker policy: validate sandbox flags, mount paths, and environment injection (`docker/launch.py`, `docker/core.py`).
- TUI/UI: confirm keymaps don’t conflict and that rendering respects capability gates (`ui/keys.py`, `ui/gate.py`, `console.py`).
- JSON mode: confirm commands decorated with `json_command` and no Rich output leaks when `output_mode.is_json_mode()` is true.

## Handoff Notes for Review Agent
- The codebase has three major “hot” files that concentrate logic: `commands/launch/app.py`, `ui/dashboard/orchestrator.py`, and `profiles.py`.
- The marketplace flow is the most security-sensitive pipeline: it combines remote config, auth, network fetch, and file writes.
- Facade modules (`git.py`, `docker/__init__.py`) still widen the API surface; UI helpers now live in `ui/git_*`.
- When reviewing tests, prefer minimal integration: many modules depend on external CLI tools, so unit tests mock `run_command`.

## Appendix A: Source Inventory (Python Only)
```
     113 scc/src/scc_cli/panels.py
      20 scc/src/scc_cli/confirm.py
     444 scc/src/scc_cli/services/git/worktree.py
     151 scc/src/scc_cli/services/git/branch.py
     216 scc/src/scc_cli/services/git/core.py
      79 scc/src/scc_cli/services/git/__init__.py
     108 scc/src/scc_cli/services/git/hooks.py
       1 scc/src/scc_cli/services/__init__.py
     200 scc/src/scc_cli/services/workspace/suspicious.py
     223 scc/src/scc_cli/services/workspace/resolver.py
      36 scc/src/scc_cli/services/workspace/__init__.py
    1000 scc/src/scc_cli/profiles.py
     269 scc/src/scc_cli/org_templates.py
     485 scc/src/scc_cli/claude_adapter.py
     394 scc/src/scc_cli/contexts.py
      88 scc/src/scc_cli/subprocess_utils.py
     272 scc/src/scc_cli/commands/init.py
     684 scc/src/scc_cli/commands/exceptions.py
     701 scc/src/scc_cli/commands/admin.py
     897 scc/src/scc_cli/commands/team.py
      20 scc/src/scc_cli/commands/__init__.py
      57 scc/src/scc_cli/commands/worktree/_helpers.py
     171 scc/src/scc_cli/commands/worktree/app.py
      61 scc/src/scc_cli/commands/worktree/context_commands.py
      73 scc/src/scc_cli/commands/worktree/__init__.py
     288 scc/src/scc_cli/commands/worktree/session_commands.py
     734 scc/src/scc_cli/commands/worktree/worktree_commands.py
     385 scc/src/scc_cli/commands/worktree/container_commands.py
     597 scc/src/scc_cli/commands/reset.py
     683 scc/src/scc_cli/commands/profile.py
     339 scc/src/scc_cli/commands/launch/workspace.py
    1378 scc/src/scc_cli/commands/launch/app.py
     156 scc/src/scc_cli/commands/launch/sandbox.py
      73 scc/src/scc_cli/commands/launch/__init__.py
     311 scc/src/scc_cli/commands/launch/render.py
     133 scc/src/scc_cli/commands/org/validate_cmd.py
     267 scc/src/scc_cli/commands/org/import_cmd.py
      74 scc/src/scc_cli/commands/org/schema_cmd.py
      41 scc/src/scc_cli/commands/org/app.py
     330 scc/src/scc_cli/commands/org/update_cmd.py
     157 scc/src/scc_cli/commands/org/status_cmd.py
      49 scc/src/scc_cli/commands/org/__init__.py
     260 scc/src/scc_cli/commands/org/_builders.py
     269 scc/src/scc_cli/commands/org/init_cmd.py
     246 scc/src/scc_cli/commands/audit.py
     627 scc/src/scc_cli/commands/config.py
     323 scc/src/scc_cli/commands/support.py
     166 scc/src/scc_cli/json_command.py
       2 scc/src/scc_cli/templates/__init__.py
       0 scc/src/scc_cli/templates/org/__init__.py
      87 scc/src/scc_cli/evaluation/evaluate.py
      27 scc/src/scc_cli/evaluation/__init__.py
     205 scc/src/scc_cli/evaluation/apply_exceptions.py
      80 scc/src/scc_cli/evaluation/models.py
     378 scc/src/scc_cli/stats.py
     180 scc/src/scc_cli/audit/reader.py
     191 scc/src/scc_cli/audit/parser.py
      37 scc/src/scc_cli/audit/__init__.py
     339 scc/src/scc_cli/cli.py
    1336 scc/src/scc_cli/setup.py
     201 scc/src/scc_cli/cli_common.py
     457 scc/src/scc_cli/validate.py
     159 scc/src/scc_cli/json_output.py
     350 scc/src/scc_cli/platform.py
       1 scc/src/scc_cli/schemas/__init__.py
     244 scc/src/scc_cli/cli_helpers.py
     434 scc/src/scc_cli/models/plugin_audit.py
     269 scc/src/scc_cli/models/exceptions.py
      41 scc/src/scc_cli/models/__init__.py
     514 scc/src/scc_cli/config.py
      65 scc/src/scc_cli/kinds.py
     484 scc/src/scc_cli/remote.py
      54 scc/src/scc_cli/deprecation.py
     348 scc/src/scc_cli/theme.py
      15 scc/src/scc_cli/__init__.py
     225 scc/src/scc_cli/teams.py
     376 scc/src/scc_cli/utils/ttl.py
     262 scc/src/scc_cli/utils/fixit.py
      39 scc/src/scc_cli/utils/__init__.py
     114 scc/src/scc_cli/utils/locks.py
     124 scc/src/scc_cli/utils/fuzzy.py
     145 scc/src/scc_cli/auth.py
     470 scc/src/scc_cli/source_resolver.py
     686 scc/src/scc_cli/update.py
     167 scc/src/scc_cli/output_mode.py
     425 scc/src/scc_cli/sessions.py
     562 scc/src/scc_cli/console.py
      84 scc/src/scc_cli/git.py
     189 scc/src/scc_cli/deps.py
      13 scc/src/scc_cli/stores/__init__.py
     251 scc/src/scc_cli/stores/exception_store.py
     498 scc/src/scc_cli/ui/formatters.py
     785 scc/src/scc_cli/ui/picker.py
     585 scc/src/scc_cli/ui/wizard.py
     884 scc/src/scc_cli/ui/git_interactive.py
      68 scc/src/scc_cli/ui/branding.py
     687 scc/src/scc_cli/docker/launch.py
     583 scc/src/scc_cli/docker/core.py
     179 scc/src/scc_cli/ui/help.py
     129 scc/src/scc_cli/docker/__init__.py
     726 scc/src/scc_cli/docker/credentials.py
     782 scc/src/scc_cli/ui/keys.py
     590 scc/src/scc_cli/ui/chrome.py
     154 scc/src/scc_cli/ui/__init__.py
     116 scc/src/scc_cli/ui/quick_resume.py
     176 scc/src/scc_cli/ui/git_render.py
    1416 scc/src/scc_cli/ui/settings.py
     219 scc/src/scc_cli/ui/prompts.py
     437 scc/src/scc_cli/ui/list_screen.py
     350 scc/src/scc_cli/ui/gate.py
     808 scc/src/scc_cli/core/personal_profiles.py
      57 scc/src/scc_cli/core/workspace.py
     316 scc/src/scc_cli/core/errors.py
      71 scc/src/scc_cli/core/__init__.py
     134 scc/src/scc_cli/core/exit_codes.py
      97 scc/src/scc_cli/core/constants.py
    1003 scc/src/scc_cli/core/maintenance.py
      87 scc/src/scc_cli/marketplace/constants.py
     548 scc/src/scc_cli/marketplace/normalize.py
     296 scc/src/scc_cli/marketplace/render.py
     430 scc/src/scc_cli/marketplace/resolve.py
     283 scc/src/scc_cli/marketplace/sync.py
     244 scc/src/scc_cli/marketplace/trust.py
     846 scc/src/scc_cli/marketplace/materialize.py
     123 scc/src/scc_cli/marketplace/__init__.py
     195 scc/src/scc_cli/marketplace/team_cache.py
     689 scc/src/scc_cli/marketplace/team_fetch.py
     135 scc/src/scc_cli/marketplace/managed.py
     498 scc/src/scc_cli/marketplace/schema.py
     316 scc/src/scc_cli/marketplace/compute.py
      66 scc/src/scc_cli/doctor/types.py
    1025 scc/src/scc_cli/ui/dashboard/_dashboard.py
    1374 scc/src/scc_cli/ui/dashboard/orchestrator.py
      62 scc/src/scc_cli/ui/dashboard/__init__.py
     463 scc/src/scc_cli/ui/dashboard/loaders.py
     190 scc/src/scc_cli/ui/dashboard/models.py
     100 scc/src/scc_cli/doctor/__init__.py
     365 scc/src/scc_cli/doctor/render.py
     278 scc/src/scc_cli/doctor/checks/worktree.py
     210 scc/src/scc_cli/doctor/checks/environment.py
     164 scc/src/scc_cli/doctor/checks/__init__.py
     275 scc/src/scc_cli/doctor/checks/cache.py
     273 scc/src/scc_cli/doctor/checks/organization.py
     107 scc/src/scc_cli/doctor/checks/config.py
     157 scc/src/scc_cli/doctor/checks/json_helpers.py
   46928 total
```
