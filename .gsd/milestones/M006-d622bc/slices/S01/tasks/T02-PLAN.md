---
estimated_steps: 10
estimated_files: 5
skills_used: []
---

# T02: CLI commands (scc provider show/set), --provider flag on start, request model update

Wire provider selection into the CLI surface:

1. Create `src/scc_cli/commands/provider.py` with `provider_app = typer.Typer()`. Add `show()` command: loads user config via `get_selected_provider()`, prints provider name (default 'claude' if None). Add `set(provider: str)` command: validates against `KNOWN_PROVIDERS`, calls `set_selected_provider()`, prints confirmation. Follow the `profile_app` pattern in `src/scc_cli/commands/profile.py`.

2. Register in `src/scc_cli/cli.py`: import `provider_app` from `.commands.provider`, add `app.add_typer(provider_app, name='provider', rich_help_panel=PANEL_CONFIG)` alongside the existing team/profile registrations.

3. Add `provider_id: str | None = None` field to `StartSessionRequest` in `src/scc_cli/application/start_session.py`.

4. Add `--provider` option to `start()` in `src/scc_cli/commands/launch/flow.py`: `provider: str | None = typer.Option(None, '--provider', help='Agent provider (claude or codex)')`. Thread it into `StartSessionRequest(provider_id=provider, ...)`.

5. Write `tests/test_provider_commands.py` testing: `scc provider show` outputs 'claude' by default, `scc provider set codex` persists, `scc provider set invalid` errors. Use typer.testing.CliRunner or mock config helpers.

Constraints:
- `provider_app` must use `handle_errors` decorator if the profile_app uses it.
- `StartSessionRequest.provider_id` must default to None (not 'claude') — resolution happens downstream.
- The `--provider` flag on start must not resolve or validate the provider — just pass it through.

## Inputs

- ``src/scc_cli/core/provider_resolution.py` — KNOWN_PROVIDERS constant for validation`
- ``src/scc_cli/config.py` — get_selected_provider/set_selected_provider helpers from T01`
- ``src/scc_cli/commands/profile.py` — pattern reference for CLI subcommand structure`
- ``src/scc_cli/cli.py` — existing app.add_typer registrations`
- ``src/scc_cli/application/start_session.py` — StartSessionRequest to extend`
- ``src/scc_cli/commands/launch/flow.py` — start() function to add --provider flag`

## Expected Output

- ``src/scc_cli/commands/provider.py` — new module with provider_app, show, set commands`
- ``src/scc_cli/cli.py` — provider_app registered`
- ``src/scc_cli/application/start_session.py` — provider_id field on StartSessionRequest`
- ``src/scc_cli/commands/launch/flow.py` — --provider flag threaded to request`
- ``tests/test_provider_commands.py` — CLI command tests`

## Verification

uv run pytest tests/test_provider_commands.py -v && uv run mypy src/scc_cli/commands/provider.py src/scc_cli/application/start_session.py && uv run ruff check src/scc_cli/commands/provider.py src/scc_cli/cli.py
