# S01: ProviderRuntimeSpec model, fail-closed dispatch, and settings-path fix

**Goal:** ProviderRuntimeSpec frozen dataclass in core/contracts.py. provider_registry.py with PROVIDER_REGISTRY dict and fail-closed get_runtime_spec() lookup. InvalidProviderError in core/errors.py. All 5 scattered provider dicts replaced with registry lookups. Settings path from registry (not hardcoded Claude). Unknown providers raise InvalidProviderError instead of silently falling back to Claude. Doctor image_map uses registry.
**Demo:** After this: ProviderRuntimeSpec defined in core/contracts.py. PROVIDER_REGISTRY in dependencies.py with get_runtime_spec() fail-closed lookup. _build_agent_settings uses spec.settings_path. Unknown provider_id raises InvalidProviderError. Full test suite passes.

## Tasks
- [x] **T01: Added ProviderRuntimeSpec frozen dataclass, InvalidProviderError, and provider_registry module with fail-closed lookup and 11-test suite** — Create the foundation types and registry module that all downstream consumers will depend on.

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
  - Estimate: 45m
  - Files: src/scc_cli/core/contracts.py, src/scc_cli/core/errors.py, src/scc_cli/provider_registry.py, tests/test_provider_registry.py
  - Verify: uv run pytest tests/test_provider_registry.py -v && uv run mypy src/scc_cli/provider_registry.py src/scc_cli/core/contracts.py src/scc_cli/core/errors.py && uv run ruff check src/scc_cli/provider_registry.py
- [x] **T02: Replaced all 5 scattered provider dicts with PROVIDER_REGISTRY lookups, fixed hardcoded Claude settings path, made unknown providers fail-closed, and flipped 4 fallback tests** — Replace all 5 scattered provider dicts with registry lookups, fix the hardcoded Claude settings path, make unknown providers fail closed, and update all affected tests.

## Steps

1. **Remove scattered dicts from `start_session.py`:**
   - Delete `_PROVIDER_IMAGE_REF`, `_PROVIDER_DATA_VOLUME`, `_PROVIDER_CONFIG_DIR` dicts (lines ~42-58)
   - Add `from scc_cli.provider_registry import get_runtime_spec` import

2. **Wire `_build_sandbox_spec` to use registry:**
   - Replace the `.get()` fallback block (lines ~320-322) with:
     ```python
     spec = get_runtime_spec(resolved_pid)
     image = spec.image_ref
     data_volume = spec.data_volume
     config_dir = spec.config_dir
     ```
   - `InvalidProviderError` propagates naturally — no try/except needed here

3. **Fix `_build_agent_settings` settings path (the bug):**
   - Thread `provider_id` into `_build_agent_settings` — add `provider_id: str = "claude"` parameter
   - Replace `settings_path = Path("/home/agent") / AGENT_CONFIG_DIR / "settings.json"` with:
     ```python
     spec = get_runtime_spec(provider_id)
     settings_path = Path("/home/agent") / spec.settings_path
     ```
   - Update the call site in `prepare_start_session` to pass `provider_id` — extract it from `dependencies.agent_provider.capability_profile().provider_id` if available, else `"claude"`
   - Note: can remove the `AGENT_CONFIG_DIR` import from this file if it's no longer used here

4. **Fix `dependencies.py` fail-closed dispatch:**
   - Replace `_PROVIDER_DISPATCH.get(provider_id, _PROVIDER_DISPATCH[_DEFAULT_PROVIDER_ID])` with:
     ```python
     if provider_id not in _PROVIDER_DISPATCH:
         from scc_cli.core.errors import InvalidProviderError
         from scc_cli.provider_registry import PROVIDER_REGISTRY
         raise InvalidProviderError(
             provider_id=provider_id,
             known_providers=tuple(PROVIDER_REGISTRY.keys()),
         )
     dispatch = _PROVIDER_DISPATCH[provider_id]
     ```
   - Update the docstring to say "Raises InvalidProviderError" instead of "Falls back to claude"

5. **Fix doctor `image_map` in `environment.py`:**
   - Replace the local `image_map` dict (lines ~305-308) and `image_ref = image_map.get(...)` with:
     ```python
     from scc_cli.provider_registry import get_runtime_spec, PROVIDER_REGISTRY
     try:
         spec = get_runtime_spec(provider_id)
         image_ref = spec.image_ref
     except InvalidProviderError:
         # Doctor is diagnostic — fall back to claude image for unknown providers
         image_ref = get_runtime_spec("claude").image_ref
     ```
   - Doctor is diagnostic, not a launch path — graceful fallback here is correct per D032

6. **Flip dispatch fallback tests in `test_provider_dispatch.py`:**
   - `test_unknown_provider_falls_back_to_claude` (line ~34): change from asserting `deps.agent_provider is adapters.agent_provider` to `pytest.raises(InvalidProviderError)`
   - `test_unknown_provider_falls_back_to_claude_runner` (line ~62): same flip
   - Import `InvalidProviderError` from `scc_cli.core.errors`

7. **Flip start_session fallback test:**
   - `test_unknown_provider_falls_back_to_claude_image` in `test_application_start_session.py` (~line 965): change to assert `InvalidProviderError` is raised instead of Claude image fallback

8. **Update `test_provider_coexistence.py` imports:**
   - Replace `from scc_cli.application.start_session import _PROVIDER_CONFIG_DIR, _PROVIDER_DATA_VOLUME, _PROVIDER_IMAGE_REF` with `from scc_cli.provider_registry import PROVIDER_REGISTRY`
   - Update test assertions to use `PROVIDER_REGISTRY["claude"].data_volume` etc. instead of dict access
   - Tests themselves stay structurally the same — they still prove coexistence isolation

9. **Update `test_doctor_image_check.py`:**
   - `test_unknown_provider_falls_back_to_claude` (~line 66): update if the behavior changed — doctor still falls back gracefully, so this test may just need import updates

10. **Add guardrail test for KNOWN_PROVIDERS sync** (if not already in T01's test file):
    - In `test_provider_registry.py`, verify `set(PROVIDER_REGISTRY.keys()) == set(KNOWN_PROVIDERS)`

## Must-Haves

- [ ] `_PROVIDER_IMAGE_REF`, `_PROVIDER_DATA_VOLUME`, `_PROVIDER_CONFIG_DIR` removed from `start_session.py`
- [ ] `_build_sandbox_spec` uses `get_runtime_spec()` — no silent Claude fallback
- [ ] Settings path uses `spec.settings_path` — Codex gets `.codex/config.toml`, not `.claude/settings.json`
- [ ] `dependencies.py` raises `InvalidProviderError` for unknown provider_id
- [ ] Doctor uses registry for image ref lookup
- [ ] Two dispatch fallback tests flipped to assert `InvalidProviderError`
- [ ] Start session fallback test flipped
- [ ] Coexistence tests import from registry
- [ ] Full test suite passes with zero regressions

## Verification

- `uv run pytest tests/test_provider_dispatch.py tests/test_provider_coexistence.py tests/test_application_start_session.py tests/test_doctor_image_check.py tests/test_provider_registry.py -v` — all targeted tests pass
- `uv run mypy src/scc_cli/application/start_session.py src/scc_cli/commands/launch/dependencies.py src/scc_cli/doctor/checks/environment.py` — clean
- `uv run pytest -q` — full suite passes, no regressions
- `uv run ruff check src/scc_cli/application/start_session.py src/scc_cli/commands/launch/dependencies.py src/scc_cli/doctor/checks/environment.py` — clean
  - Estimate: 60m
  - Files: src/scc_cli/application/start_session.py, src/scc_cli/commands/launch/dependencies.py, src/scc_cli/doctor/checks/environment.py, tests/test_provider_dispatch.py, tests/test_provider_coexistence.py, tests/test_application_start_session.py, tests/test_doctor_image_check.py
  - Verify: uv run pytest tests/test_provider_dispatch.py tests/test_provider_coexistence.py tests/test_application_start_session.py tests/test_doctor_image_check.py tests/test_provider_registry.py -v && uv run mypy src/scc_cli/application/start_session.py src/scc_cli/commands/launch/dependencies.py src/scc_cli/doctor/checks/environment.py && uv run pytest -q
