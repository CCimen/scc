# S01 Research: Provider Selection Config, CLI Flag, and Bootstrap Dispatch

## Summary

This slice adds: (1) `selected_provider` to user config with get/set helpers, (2) `scc provider show` / `scc provider set` CLI commands, (3) `--provider` flag on `scc start`, (4) a `resolve_active_provider()` function in core, (5) bootstrap dispatch that wires the correct `agent_provider`, `agent_runner`, and `safety_adapter` per resolved provider. The work is well-scoped and uses established codebase patterns.

## Recommendation

Targeted research. All pieces follow existing patterns (`selected_profile` for config, `profile_app` for CLI subcommands, `build_start_session_dependencies` for dispatch). No unfamiliar technology. Main risk is ensuring the `lru_cache` on `get_default_adapters()` doesn't bake the wrong provider — solved by keeping shared infra cached and making provider-specific adapter selection happen downstream in `build_start_session_dependencies`.

## Implementation Landscape

### Current State

**Bootstrap (`bootstrap.py`):**
- `DefaultAdapters` already carries both providers: `agent_provider: AgentProvider` (Claude), `codex_agent_provider: AgentProvider | None` (Codex).
- Both safety adapters present: `claude_safety_adapter`, `codex_safety_adapter`.
- Only one runner exists: `agent_runner` → `ClaudeAgentRunner()`.
- `get_default_adapters()` is `@lru_cache(maxsize=1)` — shared infra (probe, engine, sink) cached, providers instantiated once. This is fine per D028: shared infra stays cached, provider selection is per-invocation downstream.

**User config (`config.py`):**
- `USER_CONFIG_DEFAULTS` has `selected_profile: None`. No `selected_provider` field exists.
- `get_selected_profile()` / `set_selected_profile()` pattern: load config → read/write key → save.
- `load_user_config()` deep-merges defaults, so adding `selected_provider: None` to defaults is backward-compatible for existing configs.

**Launch flow (`commands/launch/flow.py` → `dependencies.py` → `start_session.py`):**
- `flow.py:start()` has no `--provider` flag.
- `build_start_session_dependencies()` in `dependencies.py` hardwires `adapters.agent_provider` (Claude) and `adapters.agent_runner` (Claude). This is the dispatch point.
- `StartSessionRequest` has no `provider_id` field.
- `StartSessionDependencies` carries `agent_runner`, `agent_provider` — these must be provider-dispatched.

**CLI structure (`cli.py`):**
- Subcommand groups use `typer.Typer()` pattern (see `profile_app`, `team_app`, `stats_app`).
- Added via `app.add_typer(provider_app, name="provider", ...)`.

**Provider adapters:**
- `ClaudeAgentProvider` → `provider_id="claude"`, `display_name="Claude Code"`.
- `CodexAgentProvider` → `provider_id="codex"`, `display_name="Codex"`.
- `ClaudeAgentRunner` exists. No `CodexAgentRunner` yet — that's S02's scope.
- `ClaudeSafetyAdapter`, `CodexSafetyAdapter` both exist.

**Config models (`ports/config_models.py`):**
- `NormalizedTeamConfig` has no `allowed_providers` field yet. D028 requires policy validation.
- `SecurityConfig` could gain `allowed_providers: tuple[str, ...] = ()` (empty = all allowed).

**Errors (`core/errors.py`):**
- No `ProviderNotAllowedError` exists yet. Per D028, this is needed for policy validation.
- Should extend `PolicyViolationError` (line 281) which already has the right shape.

**Image contracts (`core/image_contracts.py`):**
- Only `SCC_CLAUDE_IMAGE_REF` defined. Codex image ref is S02's scope.
- `_build_sandbox_spec()` in `start_session.py` hardwires `SCC_CLAUDE_IMAGE_REF`. S02 changes that.

### Where the Seams Are

1. **Core resolver** — new `core/provider_resolution.py` module with `resolve_active_provider(cli_flag, user_config, org_config, team) -> str`. Pure function, easily tested. Precedence: `--provider` flag > config `selected_provider` > default `"claude"`. Policy validation here too.

2. **User config** — `selected_provider` field added to `USER_CONFIG_DEFAULTS` + `get_selected_provider()` / `set_selected_provider()` helpers in `config.py`. Follows the exact `selected_profile` pattern.

3. **CLI commands** — `commands/provider.py` with `provider_app = typer.Typer()`, `show` and `set` subcommands. Follows `profile_app` pattern.

4. **CLI flag** — `--provider` option on `start()` in `commands/launch/flow.py`. Passed through to `StartSessionRequest`.

5. **Bootstrap dispatch** — `build_start_session_dependencies()` in `dependencies.py` gains a `provider_id: str` parameter. It picks the right `agent_provider`, `agent_runner`, and `safety_adapter` from `DefaultAdapters` based on resolved provider. No changes to `get_default_adapters()` or the lru_cache.

6. **Request model** — `StartSessionRequest` gains `provider_id: str | None = None`.

7. **Error type** — `ProviderNotAllowedError` extending `PolicyViolationError`.

8. **Config model** — `NormalizedTeamConfig.allowed_providers: tuple[str, ...] = ()` for policy.

### Task Decomposition Seams

The natural task order is:

**T01: Core resolver + error types + config model extension (pure, no CLI)**
- `core/provider_resolution.py` — `resolve_active_provider()` with full precedence logic and policy validation.
- `core/errors.py` — `ProviderNotAllowedError`.
- `ports/config_models.py` — `allowed_providers` on `NormalizedTeamConfig`.
- `config.py` — `selected_provider` in defaults, `get_selected_provider()`, `set_selected_provider()`.
- All pure logic with unit tests. No side effects.

**T02: CLI commands (`scc provider show/set`) + `--provider` flag on start**
- `commands/provider.py` — new `provider_app` with `show` and `set`.
- `cli.py` — register `provider_app`.
- `commands/launch/flow.py` — add `--provider` option, thread to `StartSessionRequest`.
- `StartSessionRequest` — add `provider_id: str | None = None`.

**T03: Bootstrap dispatch wiring**
- `commands/launch/dependencies.py` — `build_start_session_dependencies()` picks adapters based on resolved provider.
- `commands/launch/flow.py` — call `resolve_active_provider()` early in `start()`, pass result to deps builder.
- Thread `safety_adapter` through — currently `StartSessionDependencies` doesn't explicitly carry it, but the audit flow might need it later (check preflight).

### Key Constraints

- **No CodexAgentRunner yet** — S01 dispatch must handle the case where Codex has no runner. The resolver allows `codex`, but the runner field for codex should use a stub or error clearly. Safest: `build_start_session_dependencies` raises `ProviderNotAllowedError("Codex runner not yet available")` if runner is missing. Or: defer runner dispatch to S02 and just dispatch `agent_provider` + `safety_adapter` in S01.
- **`DefaultAdapters` field naming** — `agent_provider` is Claude, `codex_agent_provider` is Codex. The dispatch should use these by provider_id. A small lookup dict in `dependencies.py` is cleaner than an if/else chain.
- **Backward compat** — existing configs without `selected_provider` get `None` from `load_user_config()` deep-merge with defaults. `resolve_active_provider()` treats `None` as `"claude"`.
- **Policy empty-means-all** — `allowed_providers: ()` means no restriction (all providers allowed). A non-empty tuple restricts. This matches the pattern used by `blocked_plugins`.

### Files Changed (by task)

**T01 (core):**
- `src/scc_cli/core/provider_resolution.py` (new)
- `src/scc_cli/core/errors.py` (add `ProviderNotAllowedError`)
- `src/scc_cli/ports/config_models.py` (add `allowed_providers` to `NormalizedTeamConfig`)
- `src/scc_cli/config.py` (add `selected_provider` to defaults, get/set helpers)
- `tests/test_provider_resolution.py` (new)

**T02 (CLI):**
- `src/scc_cli/commands/provider.py` (new)
- `src/scc_cli/cli.py` (register `provider_app`)
- `src/scc_cli/commands/launch/flow.py` (add `--provider` option)
- `src/scc_cli/application/start_session.py` (add `provider_id` to `StartSessionRequest`)
- `tests/test_provider_commands.py` (new)

**T03 (dispatch):**
- `src/scc_cli/commands/launch/dependencies.py` (provider-aware dispatch)
- `src/scc_cli/commands/launch/flow.py` (resolve provider, pass to deps)
- `tests/test_provider_dispatch.py` (new)

### Verification

```bash
# Per-task
uv run pytest tests/test_provider_resolution.py -v
uv run pytest tests/test_provider_commands.py -v
uv run pytest tests/test_provider_dispatch.py -v

# Slice-level gate
uv run ruff check
uv run mypy src/scc_cli
uv run pytest --rootdir "$PWD" -q
```

### What S02+ Consumes From S01

S02 needs:
- `resolve_active_provider()` to get the resolved provider_id.
- The dispatch point in `build_start_session_dependencies()` — S02 adds `CodexAgentRunner` and wires it there.
- `ProviderRuntimeSpec` model (from D027) may be introduced in S02, not S01.

S03 needs:
- `resolve_active_provider()` for branding adaptation.
- The `provider_id` on `StartSessionRequest` for diagnostic/display flows.

S04 needs:
- Policy validation flow from `resolve_active_provider()`.
- `ProviderNotAllowedError` for error path testing.
