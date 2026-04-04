# S01: Provider selection config, CLI flag, and bootstrap dispatch

**Goal:** Provider selection flows from user intent (CLI flag, config, default) to bootstrap dispatch, with policy validation against org/team config.
**Demo:** After this: scc provider show prints the active provider. scc provider set codex persists it. scc start --provider codex overrides the default. Bootstrap dispatches the correct agent_provider, agent_runner, and safety_adapter based on the resolved provider.

## Tasks
- [x] **T01: Added pure provider resolver with CLI > config > default precedence, ProviderNotAllowedError, allowed_providers team config field, and selected_provider user config helpers** — Add the pure-logic foundation for provider selection:

1. Create `src/scc_cli/core/provider_resolution.py` with `resolve_active_provider(cli_flag: str | None, config_provider: str | None, allowed_providers: tuple[str, ...]) -> str`. Precedence: cli_flag > config_provider > default 'claude'. Validate against allowed_providers (empty tuple = all allowed). Raise `ProviderNotAllowedError` on policy violation. Define `KNOWN_PROVIDERS = ('claude', 'codex')` as module constant. Raise ValueError for unknown providers.

2. Add `ProviderNotAllowedError` to `src/scc_cli/core/errors.py` extending `PolicyViolationError`. Fields: `provider_id: str`, `allowed_providers: tuple[str, ...]`. Auto-generate `user_message` and `suggested_action` in `__post_init__`.

3. Add `allowed_providers: tuple[str, ...] = ()` to `NormalizedTeamConfig` in `src/scc_cli/ports/config_models.py`. Empty means all allowed.

4. Add `selected_provider: None` to `USER_CONFIG_DEFAULTS` in `src/scc_cli/config.py`. Add `get_selected_provider() -> str | None` and `set_selected_provider(provider: str) -> None` following the exact `get_selected_profile`/`set_selected_profile` pattern.

5. Write `tests/test_provider_resolution.py` covering: default resolution to 'claude', cli_flag override, config override, cli_flag beats config, unknown provider ValueError, policy validation (allowed non-empty, provider not in list), empty allowed_providers means all allowed.

6. Write tests for config helpers in the same or a companion test file.

Constraints:
- `resolve_active_provider` must be pure — no imports from adapters or bootstrap.
- Follow the `selected_profile` pattern exactly for config helpers.
- `allowed_providers` empty tuple = all allowed (matches `blocked_plugins` pattern).
  - Estimate: 45m
  - Files: src/scc_cli/core/provider_resolution.py, src/scc_cli/core/errors.py, src/scc_cli/ports/config_models.py, src/scc_cli/config.py, tests/test_provider_resolution.py
  - Verify: uv run pytest tests/test_provider_resolution.py -v && uv run mypy src/scc_cli/core/provider_resolution.py src/scc_cli/core/errors.py src/scc_cli/ports/config_models.py src/scc_cli/config.py && uv run ruff check src/scc_cli/core/provider_resolution.py src/scc_cli/core/errors.py src/scc_cli/ports/config_models.py src/scc_cli/config.py
- [x] **T02: Added scc provider show/set commands, --provider flag on scc start, and provider_id field on StartSessionRequest** — Wire provider selection into the CLI surface:

1. Create `src/scc_cli/commands/provider.py` with `provider_app = typer.Typer()`. Add `show()` command: loads user config via `get_selected_provider()`, prints provider name (default 'claude' if None). Add `set(provider: str)` command: validates against `KNOWN_PROVIDERS`, calls `set_selected_provider()`, prints confirmation. Follow the `profile_app` pattern in `src/scc_cli/commands/profile.py`.

2. Register in `src/scc_cli/cli.py`: import `provider_app` from `.commands.provider`, add `app.add_typer(provider_app, name='provider', rich_help_panel=PANEL_CONFIG)` alongside the existing team/profile registrations.

3. Add `provider_id: str | None = None` field to `StartSessionRequest` in `src/scc_cli/application/start_session.py`.

4. Add `--provider` option to `start()` in `src/scc_cli/commands/launch/flow.py`: `provider: str | None = typer.Option(None, '--provider', help='Agent provider (claude or codex)')`. Thread it into `StartSessionRequest(provider_id=provider, ...)`.

5. Write `tests/test_provider_commands.py` testing: `scc provider show` outputs 'claude' by default, `scc provider set codex` persists, `scc provider set invalid` errors. Use typer.testing.CliRunner or mock config helpers.

Constraints:
- `provider_app` must use `handle_errors` decorator if the profile_app uses it.
- `StartSessionRequest.provider_id` must default to None (not 'claude') — resolution happens downstream.
- The `--provider` flag on start must not resolve or validate the provider — just pass it through.
  - Estimate: 40m
  - Files: src/scc_cli/commands/provider.py, src/scc_cli/cli.py, src/scc_cli/application/start_session.py, src/scc_cli/commands/launch/flow.py, tests/test_provider_commands.py
  - Verify: uv run pytest tests/test_provider_commands.py -v && uv run mypy src/scc_cli/commands/provider.py src/scc_cli/application/start_session.py && uv run ruff check src/scc_cli/commands/provider.py src/scc_cli/cli.py
- [ ] **T03: Bootstrap dispatch wiring and slice-level verification** — Wire provider resolution into the launch path so bootstrap dispatches the correct adapters:

1. Update `build_start_session_dependencies()` in `src/scc_cli/commands/launch/dependencies.py` to accept a `provider_id: str` parameter. Use it to select the correct `agent_provider` and `safety_adapter` from `DefaultAdapters`:
   - `'claude'` → `adapters.agent_provider`, `adapters.claude_safety_adapter`
   - `'codex'` → `adapters.codex_agent_provider`, `adapters.codex_safety_adapter`
   - For `agent_runner`: always use `adapters.agent_runner` (ClaudeAgentRunner) for now — CodexAgentRunner is S02's scope. If provider_id is 'codex' and no codex runner exists, this is acceptable — the runner will error at actual launch time in S02.
   Use a dict-based lookup, not an if/else chain.

2. Update `prepare_live_start_plan()` in the same file to accept and pass through `provider_id`.

3. In `src/scc_cli/commands/launch/flow.py`, before building `StartSessionRequest`, call `resolve_active_provider()` with the CLI `--provider` flag and `get_selected_provider()` config value. Extract `allowed_providers` from the `NormalizedOrgConfig` team config if available. Pass the resolved `provider_id` to `prepare_live_start_plan()`.

4. Write `tests/test_provider_dispatch.py` covering:
   - Default dispatch (no provider_id) → uses Claude provider and safety adapter
   - Explicit 'claude' → same result
   - Explicit 'codex' → uses codex_agent_provider and codex_safety_adapter
   - Policy violation in flow (mocked org config with restricted allowed_providers) → ProviderNotAllowedError

5. Run the full test suite to verify zero regressions.

Constraints:
- Do NOT modify `get_default_adapters()` or the lru_cache. Provider dispatch is per-invocation in `build_start_session_dependencies()`, not at bootstrap time (D028).
- `StartSessionDependencies.agent_provider` must carry the provider-dispatched value, not always Claude.
- The `allowed_providers` field must be read from the team-level config in NormalizedOrgConfig, falling back to empty (all allowed) if no team config.
- Keep `safety_adapter` dispatch in `dependencies.py` — thread it into `StartSessionDependencies` if needed, or track it alongside for S04.
  - Estimate: 50m
  - Files: src/scc_cli/commands/launch/dependencies.py, src/scc_cli/commands/launch/flow.py, tests/test_provider_dispatch.py
  - Verify: uv run pytest tests/test_provider_dispatch.py -v && uv run pytest --rootdir "$PWD" -q && uv run mypy src/scc_cli/commands/launch/dependencies.py src/scc_cli/commands/launch/flow.py && uv run ruff check
