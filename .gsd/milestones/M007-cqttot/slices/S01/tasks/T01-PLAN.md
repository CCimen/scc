---
estimated_steps: 45
estimated_files: 4
skills_used: []
---

# T01: Create ProviderRuntimeSpec model, InvalidProviderError, and provider_registry module with tests

Create the foundation types and registry module that all downstream consumers will depend on.

## Steps

1. Add `ProviderRuntimeSpec` frozen dataclass to `src/scc_cli/core/contracts.py`:
   - Fields: `provider_id: str`, `display_name: str`, `image_ref: str`, `config_dir: str`, `settings_path: str`, `data_volume: str`
   - Place it near the existing `ProviderCapabilityProfile` dataclass
   - Import image refs from `core.image_contracts` (SCC_CLAUDE_IMAGE_REF, SCC_CODEX_IMAGE_REF)

2. Add `InvalidProviderError(SCCError)` to `src/scc_cli/core/errors.py`:
   - Fields: `provider_id: str = ""`, `known_providers: tuple[str, ...] = ()`
   - Set `exit_code = 2` (invalid usage)
   - `user_message` should say: `Unknown provider '{provider_id}'. Known providers: {', '.join(known_providers)}`
   - `suggested_action` should say: `Use one of: {', '.join(known_providers)}`
   - Follow the existing error patterns like `ProviderNotAllowedError`

3. Create `src/scc_cli/provider_registry.py`:
   - Import `ProviderRuntimeSpec` from `core.contracts`
   - Import `InvalidProviderError` from `core.errors`
   - Import image refs from `core.image_contracts`
   - Define `PROVIDER_REGISTRY: dict[str, ProviderRuntimeSpec]` with entries for `"claude"` and `"codex"`
   - Claude entry: `display_name="Claude Code"`, `image_ref=SCC_CLAUDE_IMAGE_REF`, `config_dir=".claude"`, `settings_path=".claude/settings.json"`, `data_volume="docker-claude-sandbox-data"`
   - Codex entry: `display_name="Codex"`, `image_ref=SCC_CODEX_IMAGE_REF`, `config_dir=".codex"`, `settings_path=".codex/config.toml"`, `data_volume="docker-codex-sandbox-data"`
   - Define `get_runtime_spec(provider_id: str) -> ProviderRuntimeSpec` that does `PROVIDER_REGISTRY[provider_id]` with KeyError → `InvalidProviderError` conversion
   - This module sits at the composition layer (same level as bootstrap.py) — do NOT import from adapters or commands

4. Write `tests/test_provider_registry.py`:
   - `test_claude_spec_returns_correct_fields` — verify all 6 fields
   - `test_codex_spec_returns_correct_fields` — verify all 6 fields
   - `test_unknown_provider_raises_invalid_provider_error` — assert raises with correct provider_id and known_providers
   - `test_all_registry_fields_are_nonempty` — iterate all entries, assert no empty strings
   - `test_registry_keys_match_known_providers` — import `KNOWN_PROVIDERS` from `core.provider_resolution` and assert `set(PROVIDER_REGISTRY.keys()) == set(KNOWN_PROVIDERS)` (guardrail)
   - `test_different_providers_have_different_volumes` — coexistence safety
   - `test_different_providers_have_different_config_dirs` — coexistence safety
   - `test_invalid_provider_error_message_includes_known_providers` — verify error message content

## Must-Haves

- [ ] `ProviderRuntimeSpec` frozen dataclass in `core/contracts.py` with 6 typed fields
- [ ] `InvalidProviderError(SCCError)` in `core/errors.py` with provider_id and known_providers
- [ ] `provider_registry.py` at composition layer with PROVIDER_REGISTRY and get_runtime_spec()
- [ ] Registry entries for claude and codex with correct values matching current scattered dicts
- [ ] Exhaustive test coverage in `tests/test_provider_registry.py`
- [ ] Clean mypy on all three files

## Negative Tests

- **Malformed inputs**: empty string provider_id, None-like values
- **Error paths**: unknown provider raises InvalidProviderError with correct fields
- **Boundary conditions**: registry key sync with KNOWN_PROVIDERS

## Verification

- `uv run pytest tests/test_provider_registry.py -v` — all registry tests pass
- `uv run mypy src/scc_cli/provider_registry.py src/scc_cli/core/contracts.py src/scc_cli/core/errors.py` — clean
- `uv run ruff check src/scc_cli/provider_registry.py` — clean

## Inputs

- ``src/scc_cli/core/contracts.py` — existing contract types, placement reference for ProviderRuntimeSpec`
- ``src/scc_cli/core/errors.py` — existing error hierarchy, pattern reference for InvalidProviderError`
- ``src/scc_cli/core/image_contracts.py` — SCC_CLAUDE_IMAGE_REF, SCC_CODEX_IMAGE_REF constants`
- ``src/scc_cli/core/provider_resolution.py` — KNOWN_PROVIDERS tuple, _PROVIDER_DISPLAY_NAMES dict`
- ``src/scc_cli/application/start_session.py` — current _PROVIDER_IMAGE_REF, _PROVIDER_DATA_VOLUME, _PROVIDER_CONFIG_DIR values to match`

## Expected Output

- ``src/scc_cli/core/contracts.py` — ProviderRuntimeSpec frozen dataclass added`
- ``src/scc_cli/core/errors.py` — InvalidProviderError added`
- ``src/scc_cli/provider_registry.py` — new module with PROVIDER_REGISTRY and get_runtime_spec()`
- ``tests/test_provider_registry.py` — new test file with 8+ tests`

## Verification

uv run pytest tests/test_provider_registry.py -v && uv run mypy src/scc_cli/provider_registry.py src/scc_cli/core/contracts.py src/scc_cli/core/errors.py && uv run ruff check src/scc_cli/provider_registry.py
