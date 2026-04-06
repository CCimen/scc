---
id: S03
parent: M008-g7jk8d
milestone: M008-g7jk8d
provides:
  - 106 regression-guard tests covering workspace persistence, resume-after-drift, setup idempotency, and error message quality
  - Auth bootstrap exception wrapping in ensure_provider_auth — raw exceptions become ProviderNotReadyError with actionable guidance
  - Legacy Docker Desktop module documentation cataloging all 7 residual code locations
requires:
  - slice: S01
    provides: Shared preflight module with resolve_launch_provider, collect_launch_readiness, ensure_launch_ready
  - slice: S02
    provides: Three-tier auth vocabulary, Docker Desktop confinement, shared get_agent_provider dispatch
affects:
  []
key_files:
  - tests/test_workspace_provider_persistence.py
  - tests/test_resume_after_drift.py
  - tests/test_setup_idempotency.py
  - tests/test_error_message_quality.py
  - src/scc_cli/commands/launch/auth_bootstrap.py
  - src/scc_cli/docker/core.py
  - src/scc_cli/docker/launch.py
  - src/scc_cli/docker/sandbox.py
  - src/scc_cli/adapters/docker_sandbox_runtime.py
key_decisions:
  - Wrap unexpected bootstrap_auth exceptions in ensure_provider_auth (shared entry point) rather than per-adapter — avoids scattering try/except across provider adapters
  - ProviderNotReadyError from bootstrap_auth passes through unchanged to avoid double-wrapping
  - Setup idempotency and error message quality both confirmed correct by construction — tests serve as regression guards, not fixes
  - Docker-backed smoke checks documented as manual verification items since auto-mode cannot safely delete local Docker images/volumes
patterns_established:
  - Exception wrapping at shared entry points (ensure_provider_auth) rather than per-adapter: typed errors pass through, unexpected errors get wrapped in the appropriate domain error
  - Regression-guard test pattern: when existing behavior is correct by construction, write tests to prevent future drift rather than fix code
observability_surfaces:
  - none
drill_down_paths:
  - .gsd/milestones/M008-g7jk8d/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M008-g7jk8d/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M008-g7jk8d/slices/S03/tasks/T03-SUMMARY.md
  - .gsd/milestones/M008-g7jk8d/slices/S03/tasks/T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-06T14:00:12.946Z
blocker_discovered: false
---

# S03: Error quality, edge case hardening, and final verification

**Added 106 edge-case and regression-guard tests covering workspace provider persistence, resume-after-drift resilience, setup idempotency, and error message quality — plus auth bootstrap exception wrapping and legacy Docker Desktop module documentation.**

## What Happened

S03 hardened the edge cases and error surfaces left after S01 (preflight consolidation) and S02 (vocabulary truthfulness and dispatch consolidation). The work was primarily verification-focused — most behaviors were already correct by construction, and the slice's main contribution is 106 regression-guard tests that mechanically prevent future drift.

**T01 — Workspace provider persistence (17 tests).** Verified all four active launch sites place `set_workspace_last_used_provider()` after `finalize_launch()`, so a failed launch cannot write a stale workspace preference. No code changes were needed — the guard was correct by construction in flow.py, flow_interactive.py, orchestrator_handlers, and the resume path. Added tests for: successful launch writes preference (with call ordering verification), failed launch skips write, cancelled launch skips write, KEEP_EXISTING path writes preference without finalize_launch, and `_resolve_prompt_default()` preselection behavior for ask+workspace_last_used scenarios.

**T02 — Resume-after-drift resilience (22 tests).** Covered all resume-with-environment-change scenarios: deleted auth volume stays on original provider (triggers auth bootstrap), removed image triggers auto-build or fails with exact build command, explicit --provider overrides resume provider, provider blocked by policy raises ProviderNotAllowedError, legacy session with None provider_id falls through to auto-single/global preference, explicit --provider with missing auth in non-interactive raises with actionable guidance. Added a try/except in `ensure_provider_auth` to wrap raw `bootstrap_auth()` exceptions (OSError, FileNotFoundError, TimeoutExpired) in ProviderNotReadyError while letting already-typed ProviderNotReadyError pass through unchanged.

**T03 — Setup idempotency and error message quality (67 tests).** Audited setup idempotency — `_prompt_provider_connections` already filters by auth status, so re-running setup skips connected providers correctly. Error messages across all typed error classes (ProviderNotReadyError, InvalidProviderError, ProviderImageMissingError, SandboxLaunchError, ExistingSandboxConflictError) already include actionable guidance. Created 16 setup idempotency tests and 51 error message quality tests as regression guards covering message content assertions, exit code consistency, and doctor check error wrapping.

**T04 — Legacy documentation and final gate (0 new tests).** Added legacy documentation comment blocks to four Docker Desktop sandbox modules (docker/core.py, docker/launch.py, docker/sandbox.py, adapters/docker_sandbox_runtime.py). Each clearly notes the module implements the Docker Desktop `docker sandbox run` path and is NOT used by the OCI launch path. Cataloged all 7 residual Docker Desktop code locations. Final verification gate passed: ruff clean, mypy clean (303 files), 5114 tests passed with zero regressions.

## Verification

Slice-level verification gate:
- `uv run ruff check` → 0 errors (clean)
- `uv run mypy src/scc_cli` → 303 source files, 0 issues
- `uv run pytest -q` → 5114 passed, 23 skipped, 2 xfailed in 62.54s
- All task-level targeted test runs passed independently
- 106 net new tests from slice baseline (5008 → 5114)

## Requirements Advanced

- R001 — 106 new edge-case and regression-guard tests improve testability and changeability of the launch, resume, setup, and error surfaces. Auth bootstrap exception wrapping improves error quality at the shared entry point.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Docker-backed smoke checks (delete image → verify auto-build, delete auth volume → verify bootstrap) documented as manual verification items rather than executed — auto-mode cannot safely delete local Docker images/volumes. All other task objectives met as planned.

## Known Limitations

Docker-backed smoke checks remain manual verification items. orchestrator_handlers.py and worktree_commands.py have not yet been fully migrated to the shared preflight ensure_launch_ready() — tracked as existing deferred items.

## Follow-ups

None. All planned hardening objectives met. Remaining deferred items (orchestrator_handlers/worktree_commands preflight migration, start_claude rename, WorkContext.provider_id threading) are already tracked in PROJECT.md.

## Files Created/Modified

- `tests/test_workspace_provider_persistence.py` — New: 17 tests covering failed launch guard, KEEP_EXISTING consistency, and ask+workspace_last_used preselection
- `tests/test_resume_after_drift.py` — New: 22 tests covering resume with deleted auth/image, explicit --provider override, policy blocking, legacy None provider_id, and auth bootstrap failure wrapping
- `tests/test_setup_idempotency.py` — New: 16 tests verifying setup skips connected providers and handles re-run scenarios
- `tests/test_error_message_quality.py` — New: 51 tests asserting actionable error messages across all typed error classes and doctor checks
- `src/scc_cli/commands/launch/auth_bootstrap.py` — Added try/except wrapping raw bootstrap_auth exceptions in ProviderNotReadyError
- `src/scc_cli/docker/core.py` — Added legacy documentation comment block identifying Docker Desktop sandbox path
- `src/scc_cli/docker/launch.py` — Added legacy documentation comment block identifying Docker Desktop sandbox path
- `src/scc_cli/docker/sandbox.py` — Added legacy documentation comment block identifying Docker Desktop sandbox path
- `src/scc_cli/adapters/docker_sandbox_runtime.py` — Added legacy documentation comment block identifying Docker Desktop sandbox path
