---
estimated_steps: 30
estimated_files: 8
skills_used: []
---

# T02: Machine-readable provider_id outputs and provider-aware container naming

## Description

Two related D028 deliverables: (1) add provider_id to dry-run JSON, support bundle manifest, and session list JSON envelope; (2) include provider_id in container naming for coexistence.

## Steps

1. Read `src/scc_cli/commands/launch/render.py` around `build_dry_run_data()` (line 49). Add `provider_id: str | None = None` parameter. Include `"provider_id": provider_id` in the returned dict (near other metadata fields).
2. Read `src/scc_cli/commands/launch/flow.py` around line 339 where `build_dry_run_data()` is called. Thread `provider_id=resolved_provider` (resolved_provider is already in scope from `_resolve_provider()`).
3. Read `src/scc_cli/application/support_bundle.py` around `build_support_bundle_manifest()` (line 204). Add provider_id to the manifest dict. The simplest approach: call `config.get_selected_provider()` inline (the bundle already reads config), or add a `provider_id` key to the dict. Use `config.get_selected_provider()` to resolve it at manifest build time.
4. Read `src/scc_cli/presentation/json/sessions_json.py`. Add `provider_id: str | None = None` parameter to `build_session_list_data()`. Include it in the returned dict as a top-level filter indicator.
5. Read `src/scc_cli/adapters/oci_sandbox_runtime.py` around `_container_name()` (line 49). Change signature to `_container_name(workspace: Path, provider_id: str = "")`. Include provider_id in the hash input: `hashlib.sha256(f"{provider_id}:{workspace}".encode())`. When provider_id is empty, this changes the hash from the old scheme — but the old scheme is only for unnamed containers, and existing sessions use container_id for resume, so this is safe.
6. Find all call sites of `_container_name()` in oci_sandbox_runtime.py. The `run()` method calls it. Thread `spec.provider_id` if SandboxSpec has it, otherwise use empty string. But SandboxSpec doesn't have provider_id yet — research suggested adding it. Read `src/scc_cli/ports/models.py` SandboxSpec. Add `provider_id: str = ""` field. Then read `src/scc_cli/application/start_session.py` `_build_sandbox_spec()` — populate `provider_id` from the function's provider_id parameter (already present in scope via `_PROVIDER_IMAGE_REF` key).
7. Update `_container_name()` calls in oci_sandbox_runtime.py to pass `spec.provider_id` or the provider_id from the run() method's SandboxSpec.
8. Create `tests/test_provider_machine_readable.py` with tests:
   - build_dry_run_data with provider_id returns it in dict
   - build_dry_run_data without provider_id has None
   - build_session_list_data with provider_id
   - Container name differs for same workspace with different provider_ids
   - Container name with empty provider_id (backward compat)
   - SandboxSpec.provider_id populated by _build_sandbox_spec

## Must-Haves

- [ ] build_dry_run_data includes provider_id in output dict
- [ ] flow.py threads resolved_provider to build_dry_run_data
- [ ] Support bundle manifest includes provider_id
- [ ] build_session_list_data includes provider_id
- [ ] _container_name includes provider_id in hash, producing different names per provider
- [ ] SandboxSpec gains provider_id field, populated in _build_sandbox_spec
- [ ] All new code passes ruff, mypy

## Verification

- `uv run pytest tests/test_provider_machine_readable.py -v --no-cov` — all tests pass
- `uv run ruff check src/scc_cli/commands/launch/render.py src/scc_cli/application/support_bundle.py src/scc_cli/presentation/json/sessions_json.py src/scc_cli/adapters/oci_sandbox_runtime.py src/scc_cli/ports/models.py src/scc_cli/application/start_session.py` — clean
- `uv run mypy src/scc_cli/commands/launch/render.py src/scc_cli/application/support_bundle.py src/scc_cli/presentation/json/sessions_json.py src/scc_cli/adapters/oci_sandbox_runtime.py src/scc_cli/ports/models.py src/scc_cli/application/start_session.py` — no issues
- `uv run pytest --rootdir "$PWD" -q --no-cov` — zero regressions

## Inputs

- ``src/scc_cli/commands/launch/render.py` — build_dry_run_data() function`
- ``src/scc_cli/commands/launch/flow.py` — dry-run call site around line 339 with resolved_provider in scope`
- ``src/scc_cli/application/support_bundle.py` — build_support_bundle_manifest() function`
- ``src/scc_cli/presentation/json/sessions_json.py` — build_session_list_data() function`
- ``src/scc_cli/adapters/oci_sandbox_runtime.py` — _container_name() function`
- ``src/scc_cli/ports/models.py` — SandboxSpec dataclass`
- ``src/scc_cli/application/start_session.py` — _build_sandbox_spec() with _PROVIDER_IMAGE_REF/_PROVIDER_DATA_VOLUME/_PROVIDER_CONFIG_DIR dicts`
- ``src/scc_cli/ports/session_models.py` — SessionRecord with provider_id from T01`

## Expected Output

- ``src/scc_cli/commands/launch/render.py` — provider_id param on build_dry_run_data`
- ``src/scc_cli/commands/launch/flow.py` — resolved_provider threaded to dry-run`
- ``src/scc_cli/application/support_bundle.py` — provider_id in manifest`
- ``src/scc_cli/presentation/json/sessions_json.py` — provider_id on session list data`
- ``src/scc_cli/adapters/oci_sandbox_runtime.py` — provider-aware _container_name`
- ``src/scc_cli/ports/models.py` — provider_id field on SandboxSpec`
- ``src/scc_cli/application/start_session.py` — provider_id populated on SandboxSpec`
- ``tests/test_provider_machine_readable.py` — dry-run, session list, container naming, support bundle tests`

## Verification

uv run pytest tests/test_provider_machine_readable.py -v --no-cov && uv run ruff check src/scc_cli/commands/launch/render.py src/scc_cli/application/support_bundle.py src/scc_cli/presentation/json/sessions_json.py src/scc_cli/adapters/oci_sandbox_runtime.py src/scc_cli/ports/models.py src/scc_cli/application/start_session.py && uv run mypy src/scc_cli/commands/launch/render.py src/scc_cli/application/support_bundle.py src/scc_cli/presentation/json/sessions_json.py src/scc_cli/adapters/oci_sandbox_runtime.py src/scc_cli/ports/models.py src/scc_cli/application/start_session.py && uv run pytest --rootdir "$PWD" -q --no-cov
