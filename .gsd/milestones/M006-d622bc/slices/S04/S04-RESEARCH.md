# S04 Research: Error handling hardening, end-to-end verification, zero-regression gate

## Summary

S04 closes the remaining D028 constraints and hardens the multi-provider launch path. The work falls into five natural units: (1) provider_id on machine-readable outputs, (2) provider-aware container naming for coexistence, (3) provider_id on session models for session list and Quick Resume, (4) provider image doctor check with build command hint, and (5) coexistence proof test + full regression gate. Safety adapter dispatch is wired in `_PROVIDER_DISPATCH` but has no consumer in the application layer — no threading needed, just a verification note.

## Recommendation

Targeted research depth. All patterns are established by S01-S03. The work is additive field-plumbing and new tests — no new technology, no risky integration. Five tasks in dependency order:

1. **Machine-readable provider_id outputs** (dry-run JSON, support bundle, session list JSON)
2. **Provider-aware container naming** (coexistence-critical)
3. **Provider_id on session models** (SessionRecord, SessionSummary, record_session, session list)
4. **Doctor image check** (D028 constraint 4)
5. **Coexistence proof test + regression gate**

## Implementation Landscape

### Task 1: Machine-readable provider_id in dry-run JSON, support bundle, audit events

**Dry-run JSON** — `build_dry_run_data()` in `commands/launch/render.py` returns a dict. Add `provider_id: str | None = None` parameter, include it in the returned dict. The call site in `flow.py:336` has `provider_id` in scope from `_resolve_provider()` — thread it through.

**Support bundle** — `build_support_bundle_manifest()` in `application/support_bundle.py` returns a dict. Add a `provider_id` key. The caller chain: `create_support_bundle()` ← `SupportBundleRequest`. The request doesn't carry provider_id. Options: (a) add `provider_id` to `SupportBundleRequest`, or (b) resolve it at manifest build time from `config.get_selected_provider()`. Option (b) is simpler — the bundle already calls `config.load_cached_org_config()` inline.

**Session list JSON** — `build_session_list_data()` in `presentation/json/sessions_json.py` takes sessions as dicts. If sessions carry provider_id (Task 3), it flows through automatically. But the envelope should also carry `provider_id` at the top level as a filter indicator.

**Audit events** — Already done. `build_launch_started_event()` and `build_preflight_failure_event()` in `application/launch/preflight.py` already include provider_id in metadata. `LaunchAuditEventRecord` already parses it. No work needed.

Files touched:
- `src/scc_cli/commands/launch/render.py` — add provider_id param to `build_dry_run_data()`
- `src/scc_cli/commands/launch/flow.py` — thread provider_id to `build_dry_run_data()`
- `src/scc_cli/application/support_bundle.py` — add provider_id to manifest
- `src/scc_cli/presentation/json/sessions_json.py` — optional, top-level provider_id on envelope
- `tests/test_provider_machine_readable.py` — new test file

### Task 2: Provider-aware container naming for coexistence

**Current state**: `_container_name(workspace)` in `adapters/oci_sandbox_runtime.py` produces `scc-oci-{sha256(workspace)[:12]}`. Two providers for the same workspace produce the same container name — collision.

**Fix**: Include provider_id in the hash input or in the name prefix. The cleanest approach: `scc-oci-{provider}-{sha256(workspace)[:12]}`. This requires the provider_id to reach `_container_name()`. Currently the `run()` method calls `_container_name(spec.workspace_mount.source)` — the spec doesn't carry provider_id.

**Approach**: Add `provider_id: str = ""` to `SandboxSpec`. Populate it in `_build_sandbox_spec()` in `start_session.py`. Update `_container_name(workspace, provider_id)` to include provider in hash or prefix. This is the minimal change.

**Backward compat**: Existing Claude containers have `scc-oci-{hash}` names. Changing the naming scheme means existing containers won't be found by name. Since container name is used for OCI runtime `run()` only (not resume — resume uses container_id from session), this is safe for new containers. Existing sessions' container_names in session records will still work for status checks.

Files touched:
- `src/scc_cli/ports/models.py` — add `provider_id: str = ""` to SandboxSpec
- `src/scc_cli/application/start_session.py` — populate `provider_id` on SandboxSpec
- `src/scc_cli/adapters/oci_sandbox_runtime.py` — update `_container_name()` to include provider
- `tests/test_oci_sandbox_runtime.py` — update container name assertions
- `tests/test_application_start_session.py` — verify provider_id on SandboxSpec

### Task 3: Provider_id on session models

**SessionRecord** — Add `provider_id: str | None = None` field. `to_dict()` already uses `asdict()` with None-omission, so backward compat is free. `from_dict()` needs to extract the field with a fallback.

**SessionSummary** — Add `provider_id: str | None = None`.

**SessionFilter** — Add `provider_id: str | None = None`. Thread filtering in `_filter_sessions()` in `application/sessions/use_cases.py`.

**record_session()** — Add `provider_id: str | None = None` parameter in `sessions.py`. Thread to `service.record_session()`.

**Call sites** — The start flow in `flow.py` calls `record_session()` after launch. It has the resolved provider_id in scope.

Files touched:
- `src/scc_cli/ports/session_models.py` — add provider_id to SessionRecord, SessionSummary, SessionFilter
- `src/scc_cli/application/sessions/use_cases.py` — thread provider_id in filter, record, list
- `src/scc_cli/sessions.py` — add provider_id param to record_session(), list_recent()
- `src/scc_cli/commands/launch/flow.py` — pass provider_id to record_session()
- `tests/test_session_models.py` or similar — new tests

### Task 4: Doctor image check with build command hint

D028 constraint 4: "For missing provider images, doctor and start must print the exact build command: `docker build -t scc-agent-{provider}:latest images/scc-agent-{provider}/`"

**Doctor**: Add a new check function `check_provider_image()` in `doctor/checks/` that runs `docker image inspect` for the active provider's image ref. On failure, returns `CheckResult` with `fix_commands=["docker build -t scc-agent-{provider}:latest images/scc-agent-{provider}/"]`.

**Start flow**: On `SandboxLaunchError` that includes "No such image" in stderr, catch and print the build command. Or: check image existence before `docker create` in the OCI runtime and raise a typed error with the build command in `suggested_action`.

The provider's image ref is on `SCC_CLAUDE_IMAGE_REF`/`SCC_CODEX_IMAGE_REF` in `image_contracts.py`. The doctor check needs the image ref for the active provider.

Files touched:
- `src/scc_cli/doctor/checks/__init__.py` — export new check
- `src/scc_cli/doctor/checks/environment.py` or new file — `check_provider_image()` function
- `src/scc_cli/doctor/core.py` — call the new check
- `tests/test_doctor_image_check.py` — new test file

### Task 5: Coexistence proof test + zero-regression gate

D028 constraint 5: "S04 must include a coexistence test proving Claude and Codex containers, volumes, sessions, and Quick Resume entries can both exist for the same workspace without collision."

This is a unit test that:
1. Creates two SandboxSpecs for the same workspace with different provider_ids
2. Asserts container names differ
3. Asserts data_volume names differ
4. Creates two SessionRecords for the same workspace with different provider_ids
5. Asserts session filtering by provider_id returns only the correct one
6. Asserts session list includes both when no provider filter

Plus the full regression gate: `uv run pytest --rootdir "$PWD" -q --no-cov` must pass with zero failures.

Files touched:
- `tests/test_provider_coexistence.py` — new test file
- No source changes — this is verification only

## Existing Patterns

- **Dry-run data building**: `build_dry_run_data()` is pure, returns dict — just add a field.
- **Support bundle**: Already wraps each section in try/except for partial results.
- **Session models**: Frozen dataclasses with `to_dict()`/`from_dict()` — add fields with None defaults.
- **Doctor checks**: Functions returning `CheckResult` with optional `fix_commands`.
- **Container naming**: Static function in OCI runtime, easy to extend.
- **SandboxSpec field additions**: S02 added `agent_argv`, `data_volume`, `config_dir` — same pattern for `provider_id`.

## Constraints

1. All new fields must have backward-compatible defaults (None or empty string).
2. Container name change means new containers get new names — existing containers won't match. This is acceptable since the naming scheme is internal to OCI runtime.
3. Session schema_version should increment when provider_id is added to SessionRecord for migration awareness.
4. No Docker required for tests — all verification is unit-level with mocks.
5. Full suite must stay green (4586+ tests, 0 failures).

## Risk Assessment

**Low risk overall.** All work follows established patterns. The highest-risk item is Task 2 (container naming) because it changes the identity scheme, but the change is additive (provider_id defaults to empty string, preserving existing hash for backward compat when not set).

## Dependencies

- S01 provides: `resolve_active_provider()`, `get_selected_provider()`, provider_id on StartSessionRequest, `_PROVIDER_DISPATCH`
- S02 provides: `_PROVIDER_IMAGE_REF`, `_PROVIDER_DATA_VOLUME`, `_PROVIDER_CONFIG_DIR` dicts, SandboxSpec fields
- S03 provides: `get_provider_display_name()`, provider-neutral branding, guardrail test

All dependencies are delivered and tested.
