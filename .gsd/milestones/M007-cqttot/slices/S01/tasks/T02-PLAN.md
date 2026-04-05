---
estimated_steps: 77
estimated_files: 7
skills_used: []
---

# T02: Wire registry into start_session, dependencies, and doctor; fix settings-path; flip fallback tests

Replace all 5 scattered provider dicts with registry lookups, fix the hardcoded Claude settings path, make unknown providers fail closed, and update all affected tests.

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

## Inputs

- ``src/scc_cli/provider_registry.py` — T01 output: PROVIDER_REGISTRY and get_runtime_spec()`
- ``src/scc_cli/core/errors.py` — T01 output: InvalidProviderError`
- ``src/scc_cli/core/contracts.py` — T01 output: ProviderRuntimeSpec`
- ``src/scc_cli/application/start_session.py` — current scattered dicts and hardcoded settings path to replace`
- ``src/scc_cli/commands/launch/dependencies.py` — current _PROVIDER_DISPATCH fallback to fix`
- ``src/scc_cli/doctor/checks/environment.py` — current image_map dict to replace`
- ``tests/test_provider_dispatch.py` — fallback tests to flip`
- ``tests/test_provider_coexistence.py` — imports to update from scattered dicts to registry`
- ``tests/test_application_start_session.py` — fallback test to flip`

## Expected Output

- ``src/scc_cli/application/start_session.py` — scattered dicts removed, registry used, settings path fixed`
- ``src/scc_cli/commands/launch/dependencies.py` — fail-closed dispatch with InvalidProviderError`
- ``src/scc_cli/doctor/checks/environment.py` — registry-based image lookup`
- ``tests/test_provider_dispatch.py` — fallback tests assert InvalidProviderError`
- ``tests/test_provider_coexistence.py` — imports from provider_registry`
- ``tests/test_application_start_session.py` — fallback test asserts InvalidProviderError`
- ``tests/test_doctor_image_check.py` — updated for registry-based lookup`

## Verification

uv run pytest tests/test_provider_dispatch.py tests/test_provider_coexistence.py tests/test_application_start_session.py tests/test_doctor_image_check.py tests/test_provider_registry.py -v && uv run mypy src/scc_cli/application/start_session.py src/scc_cli/commands/launch/dependencies.py src/scc_cli/doctor/checks/environment.py && uv run pytest -q
