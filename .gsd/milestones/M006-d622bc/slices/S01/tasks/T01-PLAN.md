---
estimated_steps: 11
estimated_files: 5
skills_used: []
---

# T01: Core provider resolver, error types, config model, and user config helpers

Add the pure-logic foundation for provider selection:

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

## Inputs

- ``src/scc_cli/core/errors.py` — PolicyViolationError base class`
- ``src/scc_cli/ports/config_models.py` — NormalizedTeamConfig to extend`
- ``src/scc_cli/config.py` — USER_CONFIG_DEFAULTS and get/set_selected_profile pattern`

## Expected Output

- ``src/scc_cli/core/provider_resolution.py` — new module with resolve_active_provider() and KNOWN_PROVIDERS`
- ``src/scc_cli/core/errors.py` — ProviderNotAllowedError added`
- ``src/scc_cli/ports/config_models.py` — allowed_providers field on NormalizedTeamConfig`
- ``src/scc_cli/config.py` — selected_provider in defaults, get/set helpers`
- ``tests/test_provider_resolution.py` — unit tests for resolver and config helpers`

## Verification

uv run pytest tests/test_provider_resolution.py -v && uv run mypy src/scc_cli/core/provider_resolution.py src/scc_cli/core/errors.py src/scc_cli/ports/config_models.py src/scc_cli/config.py && uv run ruff check src/scc_cli/core/provider_resolution.py src/scc_cli/core/errors.py src/scc_cli/ports/config_models.py src/scc_cli/config.py
