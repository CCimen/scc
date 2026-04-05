---
id: S04
parent: M006-d622bc
milestone: M006-d622bc
provides:
  - provider_id threaded through session recording and listing
  - provider_id in all machine-readable outputs (dry-run, bundle, session list)
  - provider-aware container naming preventing coexistence collisions
  - doctor check for provider image availability with fix_commands
  - 16 coexistence proof tests for containers, volumes, sessions, and SandboxSpec
  - 4643-test zero-regression gate
requires:
  - slice: S01
    provides: Provider resolution and bootstrap dispatch
  - slice: S02
    provides: CodexAgentRunner, image refs, and SandboxSpec field-forwarding pattern
  - slice: S03
    provides: Provider-aware branding and string cleanup
affects:
  []
key_files:
  - src/scc_cli/ports/session_models.py
  - src/scc_cli/ports/models.py
  - src/scc_cli/application/sessions/use_cases.py
  - src/scc_cli/sessions.py
  - src/scc_cli/commands/launch/flow_session.py
  - src/scc_cli/commands/launch/flow.py
  - src/scc_cli/commands/launch/flow_interactive.py
  - src/scc_cli/commands/launch/render.py
  - src/scc_cli/application/support_bundle.py
  - src/scc_cli/presentation/json/sessions_json.py
  - src/scc_cli/adapters/oci_sandbox_runtime.py
  - src/scc_cli/application/start_session.py
  - src/scc_cli/doctor/checks/environment.py
  - src/scc_cli/doctor/core.py
  - tests/test_session_provider_id.py
  - tests/test_provider_machine_readable.py
  - tests/test_doctor_image_check.py
  - tests/test_provider_coexistence.py
key_decisions:
  - schema_version bumped from 1 to 2 for new SessionRecords; from_dict still defaults to 1 for legacy data
  - _container_name uses provider_id:workspace as hash input when non-empty, preserving backward compat for empty provider_id
  - SandboxSpec.provider_id defaults to empty string (not None) for hash-input consistency
  - WARNING severity for missing provider image — only needed for scc start, not general usage
  - Provider image check gated on docker_ok in run_doctor() — no point checking images if Docker is unreachable
  - Coexistence tested at data-structure level without requiring Docker — fast, deterministic, proves hash/naming isolation
patterns_established:
  - SessionRecord schema_version bump with backward-compat from_dict() default for schema evolution
  - Provider-aware container naming via hash-input prefix (provider_id:workspace) preserving empty-string backward compat
  - Doctor checks for provider-specific resources with exact fix_commands for operator recovery
  - Data-structure-level coexistence proof (no Docker dependency) for multi-provider identity isolation
observability_surfaces:
  - check_provider_image() doctor check: reports missing provider agent images with exact docker build command
  - provider_id in dry-run JSON output
  - provider_id in support bundle manifest
  - provider_id in session list --json output
drill_down_paths:
  - .gsd/milestones/M006-d622bc/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M006-d622bc/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M006-d622bc/slices/S04/tasks/T03-SUMMARY.md
  - .gsd/milestones/M006-d622bc/slices/S04/tasks/T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-05T01:25:48.012Z
blocker_discovered: false
---

# S04: Error handling hardening, end-to-end verification, zero-regression gate

**Threaded provider_id through session recording, machine-readable outputs, container naming, and doctor checks; proved Claude/Codex coexistence with 57 new tests and a 4643-test zero-regression gate.**

## What Happened

S04 closed the remaining D028 constraints for provider selection production-readiness: machine-readable provider output, provider-aware container naming, doctor image checks, and coexistence proof.

**T01 — Session provider_id threading.** Added `provider_id: str | None = None` to SessionRecord, SessionSummary, and SessionFilter. Threaded through `record_session()`, `_record_session_and_context()`, and all call sites in flow.py, flow_interactive.py, and sandbox.py. Bumped SessionRecord schema_version from 1→2 for new records while preserving backward compat in from_dict(). Added provider_id filtering to list_recent(). 13 new tests.

**T02 — Machine-readable output and container naming.** Added provider_id to dry-run JSON (build_dry_run_data), support bundle manifest (build_support_bundle_manifest), and session list JSON (build_session_list_data). Made _container_name() include provider_id in the hash input (`provider_id:workspace` format) so Claude and Codex containers for the same workspace produce different names. Added provider_id field to SandboxSpec, populated by _build_sandbox_spec() from the provider adapter's capability profile. 18 new tests.

**T03 — Doctor provider image check.** Added check_provider_image() to doctor/checks/environment.py. Resolves the active provider, maps to image ref, runs `docker image inspect`, and returns a CheckResult with the exact `docker build -t <ref> images/scc-agent-<provider>/` command as fix_commands on failure. Uses WARNING severity (image only needed for `scc start`). Gated behind docker_ok in run_doctor(). 10 new tests.

**T04 — Coexistence proof and regression gate.** Created 16 coexistence tests proving Claude and Codex containers, volumes, config dirs, sessions, and SandboxSpec fields don't collide for the same workspace. Fixed 3 inherited ruff lint issues from prior tasks. Full regression gate: 4643 passed, 0 failures, 23 skipped, 2 xfailed. Ruff clean. Mypy clean (292 files).

All D028 constraints are now met: (1) provider validated against policy (S01), (2) request-scoped resolution (S01), (3) provider_id in dry-run/bundle/session JSON (T02), (4) exact build command in doctor (T03), (5) coexistence proof (T04).

## Verification

Slice-level verification gate passed:
- `uv run pytest --rootdir "$PWD" -q --no-cov` → 4643 passed, 0 failures, 23 skipped, 2 xfailed (63s)
- `uv run ruff check` → All checks passed
- `uv run mypy src/scc_cli` → Success: no issues found in 292 source files

Task-specific tests:
- tests/test_session_provider_id.py: 13/13 passed
- tests/test_provider_machine_readable.py: 18/18 passed
- tests/test_doctor_image_check.py: 10/10 passed
- tests/test_provider_coexistence.py: 16/16 passed

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

T01: Fixed latent schema_version preservation bug exposed by version bump. Updated existing test_sessions.py. T02: Renamed local variable to avoid shadowing; added non-OCI branch provider resolution. T03: Renamed _IMAGE_MAP to image_map for ruff N806. T04: Fixed 3 inherited ruff lint errors from prior tasks.

## Known Limitations

None.

## Follow-ups

None.

## Files Created/Modified

- `src/scc_cli/ports/session_models.py` — Added provider_id field to SessionRecord, SessionSummary, SessionFilter; bumped schema_version to 2
- `src/scc_cli/ports/models.py` — Added provider_id: str = '' field to SandboxSpec
- `src/scc_cli/application/sessions/use_cases.py` — Threaded provider_id through record_session() and filtering in list_recent()
- `src/scc_cli/sessions.py` — Added provider_id parameter to record_session() and list_recent() facades
- `src/scc_cli/commands/launch/flow_session.py` — Added provider_id parameter to _record_session_and_context()
- `src/scc_cli/commands/launch/flow.py` — Threaded resolved_provider to session recording and dry-run JSON
- `src/scc_cli/commands/launch/flow_interactive.py` — Threaded provider_id to session recording in interactive flow
- `src/scc_cli/commands/launch/sandbox.py` — Added provider_id=None passthrough at sandbox-level recording
- `src/scc_cli/commands/launch/render.py` — Added provider_id to build_dry_run_data() output
- `src/scc_cli/application/support_bundle.py` — Added provider_id to support bundle manifest
- `src/scc_cli/presentation/json/sessions_json.py` — Added provider_id to session list JSON output
- `src/scc_cli/adapters/oci_sandbox_runtime.py` — Made _container_name() include provider_id in hash input
- `src/scc_cli/application/start_session.py` — Populated SandboxSpec.provider_id from capability profile in _build_sandbox_spec()
- `src/scc_cli/doctor/checks/environment.py` — Added check_provider_image() with exact build command in fix_commands
- `src/scc_cli/doctor/checks/__init__.py` — Exported check_provider_image
- `src/scc_cli/doctor/core.py` — Wired check_provider_image() into run_doctor() and run_all_checks()
- `tests/test_session_provider_id.py` — 13 tests for session provider_id threading and filtering
- `tests/test_provider_machine_readable.py` — 18 tests for dry-run/bundle/session JSON and container naming
- `tests/test_doctor_image_check.py` — 10 tests for provider image doctor check
- `tests/test_provider_coexistence.py` — 16 coexistence proof tests for multi-provider identity isolation
- `tests/test_sessions.py` — Updated existing schema_version test for v2 default
