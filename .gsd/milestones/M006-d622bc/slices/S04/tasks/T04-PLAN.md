---
estimated_steps: 25
estimated_files: 1
skills_used: []
---

# T04: Coexistence proof test and zero-regression gate

## Description

D028 constraint 5: prove that Claude and Codex containers, volumes, sessions, and Quick Resume entries coexist for the same workspace without collision. Plus the full regression gate.

## Steps

1. Create `tests/test_provider_coexistence.py` with a comprehensive coexistence proof:
   - **Container name collision test**: Import `_container_name` from `scc_cli.adapters.oci_sandbox_runtime`. Create two calls with the same workspace Path but different provider_ids ("claude" and "codex"). Assert the returned names differ.
   - **Data volume collision test**: Import `_PROVIDER_DATA_VOLUME` from `scc_cli.application.start_session`. Assert `_PROVIDER_DATA_VOLUME["claude"] != _PROVIDER_DATA_VOLUME["codex"]`.
   - **Session coexistence test**: Create two SessionRecord instances for the same workspace with different provider_ids. Assert both can exist. Create a SessionFilter with provider_id="claude" and verify filtering logic returns only the Claude session (use the SessionService or test the filter manually by constructing records and applying the filter).
   - **Session list isolation test**: Build two sessions, list with provider_id filter, assert only matching provider returned.
   - **SandboxSpec identity test**: Build two SandboxSpec instances (or use `_build_sandbox_spec` if accessible) for the same workspace with different providers. Assert image_ref, data_volume, config_dir, and agent_argv all differ.
2. Run the full regression gate: `uv run pytest --rootdir "$PWD" -q --no-cov` — must be 0 failures.
3. Run `uv run ruff check` — must be 0 errors.
4. Run `uv run mypy src/scc_cli` — must be 0 issues (or same as baseline).

## Must-Haves

- [ ] Container names for same workspace + different providers are distinct
- [ ] Data volume names for claude and codex are distinct
- [ ] Sessions with different provider_ids can coexist and be filtered independently
- [ ] SandboxSpec fields (image_ref, data_volume, config_dir, agent_argv) differ per provider
- [ ] Full test suite: 0 failures
- [ ] ruff check: 0 errors
- [ ] mypy: 0 issues

## Verification

- `uv run pytest tests/test_provider_coexistence.py -v --no-cov` — all coexistence tests pass
- `uv run pytest --rootdir "$PWD" -q --no-cov` — 0 failures (4600+ tests expected)
- `uv run ruff check` — 0 errors
- `uv run mypy src/scc_cli` — success

## Inputs

- ``src/scc_cli/adapters/oci_sandbox_runtime.py` — _container_name() with provider_id from T02`
- ``src/scc_cli/application/start_session.py` — _PROVIDER_DATA_VOLUME, _PROVIDER_CONFIG_DIR, _PROVIDER_IMAGE_REF dicts from S02`
- ``src/scc_cli/ports/session_models.py` — SessionRecord, SessionFilter with provider_id from T01`
- ``src/scc_cli/ports/models.py` — SandboxSpec with provider_id from T02`
- ``tests/test_provider_machine_readable.py` — T02 test file (no dependency, just co-exists)`
- ``tests/test_session_provider_id.py` — T01 test file (no dependency, just co-exists)`
- ``tests/test_doctor_image_check.py` — T03 test file (no dependency, just co-exists)`

## Expected Output

- ``tests/test_provider_coexistence.py` — coexistence proof tests covering containers, volumes, sessions, specs`

## Verification

uv run pytest tests/test_provider_coexistence.py -v --no-cov && uv run pytest --rootdir "$PWD" -q --no-cov && uv run ruff check && uv run mypy src/scc_cli
