# S04: Error handling hardening, end-to-end verification, zero-regression gate

**Goal:** All error paths produce typed, user-facing errors. provider_id appears in all machine-readable outputs. Provider-aware container naming prevents coexistence collisions. Doctor checks for provider image availability. Full test suite passes with zero regressions.
**Demo:** After this: All error paths produce typed, user-facing errors. Full test suite passes. Both providers verified end-to-end.

## Tasks
- [x] **T01: Added provider_id field to SessionRecord, SessionSummary, SessionFilter and threaded it through all session recording and listing call sites in the launch flow** — ## Description

Add `provider_id: str | None = None` to SessionRecord, SessionSummary, and SessionFilter. Thread it through record_session, list_recent, _record_session_and_context, and all call sites in the launch flow. This is foundational — T02 and T04 depend on sessions carrying provider_id.

## Steps

1. Read `src/scc_cli/ports/session_models.py`. Add `provider_id: str | None = None` field to SessionRecord (after schema_version), SessionSummary (after branch), and SessionFilter (after include_all). Update `from_dict()` on SessionRecord to extract provider_id with default None. Bump `schema_version` default to 2 on SessionRecord.
2. Read `src/scc_cli/application/sessions/use_cases.py`. Thread `provider_id` through `record_session()` method — pass it to the SessionRecord constructor. Thread `provider_id` through filtering in list_recent: if `SessionFilter.provider_id` is set, filter sessions where `provider_id` matches.
3. Read `src/scc_cli/sessions.py`. Add `provider_id: str | None = None` parameter to `record_session()` and `list_recent()`. Pass through to service calls.
4. Read `src/scc_cli/commands/launch/flow_session.py`. Add `provider_id: str | None = None` parameter to `_record_session_and_context()`. Pass to `sessions.record_session()`.
5. Read `src/scc_cli/commands/launch/flow.py` around line 368 where `_record_session_and_context` is called. Thread `resolved_provider` (already in scope) as `provider_id=resolved_provider`.
6. Read `src/scc_cli/commands/launch/flow_interactive.py` around line 708 where `_record_session_and_context` is called. Thread the resolved provider_id (find it in scope from the interactive flow).
7. Read `src/scc_cli/commands/launch/sandbox.py` around line 97 where `sessions.record_session()` is called. Thread provider_id if available in scope, or pass None.
8. Create `tests/test_session_provider_id.py` with tests:
   - SessionRecord round-trip with provider_id set and None
   - SessionRecord.from_dict() with and without provider_id key (backward compat)
   - SessionSummary with provider_id field
   - SessionFilter with provider_id filtering
   - schema_version defaults to 2 for new records

## Must-Haves

- [ ] SessionRecord, SessionSummary, SessionFilter all have `provider_id: str | None = None`
- [ ] SessionRecord.from_dict() handles missing provider_id gracefully
- [ ] record_session() accepts and stores provider_id
- [ ] _record_session_and_context() passes provider_id through
- [ ] flow.py and flow_interactive.py thread resolved_provider to session recording
- [ ] All new code passes ruff, mypy

## Verification

- `uv run pytest tests/test_session_provider_id.py -v --no-cov` — all tests pass
- `uv run ruff check src/scc_cli/ports/session_models.py src/scc_cli/sessions.py src/scc_cli/commands/launch/flow_session.py` — clean
- `uv run mypy src/scc_cli/ports/session_models.py src/scc_cli/sessions.py src/scc_cli/commands/launch/flow_session.py` — no issues
- `uv run pytest --rootdir "$PWD" -q --no-cov` — zero regressions
  - Estimate: 45m
  - Files: src/scc_cli/ports/session_models.py, src/scc_cli/application/sessions/use_cases.py, src/scc_cli/sessions.py, src/scc_cli/commands/launch/flow_session.py, src/scc_cli/commands/launch/flow.py, src/scc_cli/commands/launch/flow_interactive.py, src/scc_cli/commands/launch/sandbox.py, tests/test_session_provider_id.py
  - Verify: uv run pytest tests/test_session_provider_id.py -v --no-cov && uv run ruff check src/scc_cli/ports/session_models.py src/scc_cli/sessions.py src/scc_cli/commands/launch/flow_session.py && uv run mypy src/scc_cli/ports/session_models.py src/scc_cli/sessions.py src/scc_cli/commands/launch/flow_session.py && uv run pytest --rootdir "$PWD" -q --no-cov
- [ ] **T02: Machine-readable provider_id outputs and provider-aware container naming** — ## Description

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
  - Estimate: 1h
  - Files: src/scc_cli/commands/launch/render.py, src/scc_cli/commands/launch/flow.py, src/scc_cli/application/support_bundle.py, src/scc_cli/presentation/json/sessions_json.py, src/scc_cli/adapters/oci_sandbox_runtime.py, src/scc_cli/ports/models.py, src/scc_cli/application/start_session.py, tests/test_provider_machine_readable.py
  - Verify: uv run pytest tests/test_provider_machine_readable.py -v --no-cov && uv run ruff check src/scc_cli/commands/launch/render.py src/scc_cli/application/support_bundle.py src/scc_cli/presentation/json/sessions_json.py src/scc_cli/adapters/oci_sandbox_runtime.py src/scc_cli/ports/models.py src/scc_cli/application/start_session.py && uv run mypy src/scc_cli/commands/launch/render.py src/scc_cli/application/support_bundle.py src/scc_cli/presentation/json/sessions_json.py src/scc_cli/adapters/oci_sandbox_runtime.py src/scc_cli/ports/models.py src/scc_cli/application/start_session.py && uv run pytest --rootdir "$PWD" -q --no-cov
- [ ] **T03: Doctor provider image check with build command hint** — ## Description

D028 constraint 4: for missing provider images, doctor must print the exact build command. Add a `check_provider_image()` doctor check that runs `docker image inspect` for the active provider's image ref and returns a CheckResult with fix_commands on failure.

## Steps

1. Read `src/scc_cli/doctor/checks/environment.py` to understand the existing check pattern (check_docker, check_docker_running, etc). Note how they use subprocess and return CheckResult.
2. Read `src/scc_cli/core/image_contracts.py` to get the exact image ref constants: `SCC_CLAUDE_IMAGE_REF` and `SCC_CODEX_IMAGE_REF`.
3. Read `src/scc_cli/core/provider_resolution.py` to import `get_selected_provider` for resolving the active provider.
4. Create `check_provider_image()` in `src/scc_cli/doctor/checks/environment.py`:
   - Import `get_selected_provider` from config, `SCC_CLAUDE_IMAGE_REF` and `SCC_CODEX_IMAGE_REF` from image_contracts
   - Map provider_id to image_ref: `{"claude": SCC_CLAUDE_IMAGE_REF, "codex": SCC_CODEX_IMAGE_REF}`
   - Resolve active provider via `config.get_selected_provider()`
   - Run `docker image inspect {image_ref}` via subprocess
   - On success: return CheckResult(name="provider_image", passed=True, message=f"{image_ref} found")
   - On failure: return CheckResult(name="provider_image", passed=False, message=f"{image_ref} not found", fix_commands=[f"docker build -t {image_ref} images/scc-agent-{provider_id}/"], fix_hint=f"Build the {provider} agent image", severity=SeverityLevel.WARNING)
   - Use WARNING severity since the image is only needed for `scc start`, not general usage
5. Read `src/scc_cli/doctor/checks/__init__.py`. Export `check_provider_image`.
6. Read `src/scc_cli/doctor/core.py` `run_doctor()`. Add a call to `check_provider_image()` after the Docker checks (it only makes sense to check the image if Docker is working). Wrap in try/except per the support-bundle partial-results pattern.
7. Create `tests/test_doctor_image_check.py`:
   - Test image found → passed=True
   - Test image not found → passed=False with correct fix_commands containing build command
   - Test unknown provider → falls back to claude image ref
   - Test subprocess failure → graceful failure with appropriate message
   - Mock subprocess.run to avoid Docker dependency

## Must-Haves

- [ ] check_provider_image() exists and returns CheckResult
- [ ] On missing image, fix_commands contains exact `docker build -t scc-agent-{provider}:latest images/scc-agent-{provider}/` command
- [ ] Doctor runs the check after Docker checks
- [ ] All code passes ruff, mypy

## Verification

- `uv run pytest tests/test_doctor_image_check.py -v --no-cov` — all tests pass
- `uv run ruff check src/scc_cli/doctor/checks/environment.py src/scc_cli/doctor/core.py` — clean
- `uv run mypy src/scc_cli/doctor/checks/environment.py src/scc_cli/doctor/core.py` — no issues
- `uv run pytest --rootdir "$PWD" -q --no-cov` — zero regressions

## Negative Tests

- **Malformed inputs**: unknown provider_id → falls back to claude image ref
- **Error paths**: subprocess timeout or CalledProcessError → graceful CheckResult(passed=False)
- **Boundary conditions**: Docker not running → check returns failed with helpful message
  - Estimate: 30m
  - Files: src/scc_cli/doctor/checks/environment.py, src/scc_cli/doctor/checks/__init__.py, src/scc_cli/doctor/core.py, tests/test_doctor_image_check.py
  - Verify: uv run pytest tests/test_doctor_image_check.py -v --no-cov && uv run ruff check src/scc_cli/doctor/checks/environment.py src/scc_cli/doctor/core.py && uv run mypy src/scc_cli/doctor/checks/environment.py src/scc_cli/doctor/core.py && uv run pytest --rootdir "$PWD" -q --no-cov
- [ ] **T04: Coexistence proof test and zero-regression gate** — ## Description

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
  - Estimate: 30m
  - Files: tests/test_provider_coexistence.py
  - Verify: uv run pytest tests/test_provider_coexistence.py -v --no-cov && uv run pytest --rootdir "$PWD" -q --no-cov && uv run ruff check && uv run mypy src/scc_cli
