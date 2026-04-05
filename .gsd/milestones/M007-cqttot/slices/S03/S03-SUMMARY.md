---
id: S03
parent: M007-cqttot
milestone: M007-cqttot
provides:
  - ProviderNotReadyError and ProviderImageMissingError typed errors for use in launch and preflight paths
  - check_provider_auth() exported from doctor/checks/__init__.py and doctor/__init__.py
  - CheckResult.category field for downstream grouping/filtering
  - --provider flag on scc doctor command
requires:
  - slice: S01
    provides: ProviderRuntimeSpec registry and get_runtime_spec() fail-closed lookup
affects:
  - S05
key_files:
  - src/scc_cli/core/errors.py
  - src/scc_cli/core/contracts.py
  - src/scc_cli/doctor/types.py
  - src/scc_cli/doctor/core.py
  - src/scc_cli/doctor/render.py
  - src/scc_cli/doctor/serialization.py
  - src/scc_cli/doctor/checks/environment.py
  - src/scc_cli/doctor/checks/__init__.py
  - src/scc_cli/commands/admin.py
  - tests/test_doctor_provider_errors.py
  - tests/test_doctor_provider_wiring.py
key_decisions:
  - Category assignment uses a name→category map in core.py with _assign_category() applied post-collection, preserving categories already set by check functions
  - Render grouping uses fixed category order (backend→provider→config→worktree→general) with bold cyan section headers
  - Auth file names mapped per provider via local dict (claude → .credentials.json, codex → auth.json) with .credentials.json fallback for unknown providers
patterns_established:
  - Doctor checks can set their own category at creation time; _assign_category() only overrides when category is still 'general'
  - CLI --provider flag validates against KNOWN_PROVIDERS before entering any business logic — early exit with code 2
observability_surfaces:
  - scc doctor --provider codex scopes checks to Codex-specific readiness
  - Doctor JSON output includes category field for each check
  - Doctor table output groups checks by category with section headers
drill_down_paths:
  - .gsd/milestones/M007-cqttot/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M007-cqttot/slices/S03/tasks/T02-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-05T13:31:07.877Z
blocker_discovered: false
---

# S03: Doctor provider-awareness and typed provider errors

**Doctor is provider-aware: --provider flag scopes checks, output groups by category, and two typed provider errors exist with actionable messages.**

## What Happened

This slice made `scc doctor` provider-aware across two tasks.

T01 added all new types and check logic as pure additive work — no existing control flow changed. Two typed errors (ProviderNotReadyError, ProviderImageMissingError) follow the existing InvalidProviderError pattern with auto-populated user_message/suggested_action and exit_code=3. AuthReadiness frozen dataclass models auth credential status. CheckResult gained a `category` field (default 'general') for output grouping. `check_provider_auth()` uses a two-step Docker probe (volume inspect → alpine test -f) to check provider auth files, with provider-specific auth file names resolved from a local mapping dict. 23 tests cover all paths including timeout, missing volume, unknown provider fallback, and Docker-not-found.

T02 wired all T01 additions into the existing doctor pipeline. `run_doctor()` accepts `provider_id` and threads it to both `check_provider_image()` and `check_provider_auth()`. A `_CATEGORY_MAP` and `_assign_category()` helper classifies checks into backend/provider/config/worktree/general categories post-collection, preserving categories already set by check functions. `doctor_cmd` gained a `--provider` flag validated against KNOWN_PROVIDERS (exit code 2 for unknown providers). `render_doctor_results()` sorts checks by category order and inserts bold cyan section headers. `build_doctor_json_data()` includes category in each check dict. 20 tests cover category assignment, provider threading, CLI flag validation, JSON serialization, and render grouping.

## Verification

Slice verification gate: `uv run pytest tests/test_doctor_provider_wiring.py tests/test_doctor_provider_errors.py tests/test_doctor_image_check.py tests/test_doctor_checks.py -v` → 101 passed. `uv run mypy src/scc_cli/doctor/core.py src/scc_cli/doctor/render.py src/scc_cli/doctor/serialization.py src/scc_cli/commands/admin.py` → no issues. `uv run ruff check src/scc_cli/doctor/ src/scc_cli/commands/admin.py` → all passed. Full suite: `uv run pytest -q` → 4718 passed, 23 skipped, 2 xfailed.

## Requirements Advanced

- R001 — Doctor decomposition: typed errors, categorized output, and provider-scoped checks improve testability (43 new tests) and maintainability of the doctor subsystem

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None. Both tasks completed as planned.

## Known Limitations

check_provider_auth() requires Docker to be available — it probes Docker volumes directly. On systems without Docker, the check reports 'could not verify' rather than failing hard.

## Follow-ups

None.

## Files Created/Modified

- `src/scc_cli/core/errors.py` — Added ProviderNotReadyError and ProviderImageMissingError with auto-populated messages
- `src/scc_cli/core/contracts.py` — Added AuthReadiness frozen dataclass for auth credential status
- `src/scc_cli/doctor/types.py` — Added category field to CheckResult (default 'general')
- `src/scc_cli/doctor/core.py` — Added provider_id parameter to run_doctor(), _assign_category() helper, check_provider_auth call
- `src/scc_cli/doctor/render.py` — Category-based sorting and section headers in render_doctor_results()
- `src/scc_cli/doctor/serialization.py` — Added category to JSON output
- `src/scc_cli/doctor/checks/environment.py` — Added check_provider_auth(), provider_id param on check_provider_image()
- `src/scc_cli/doctor/checks/__init__.py` — Re-exported check_provider_auth
- `src/scc_cli/doctor/__init__.py` — Re-exported check_provider_auth
- `src/scc_cli/commands/admin.py` — Added --provider flag to doctor_cmd with validation
- `tests/test_doctor_provider_errors.py` — 23 tests for typed errors, AuthReadiness, CheckResult.category, check_provider_auth
- `tests/test_doctor_provider_wiring.py` — 20 tests for category assignment, provider threading, CLI flag, JSON, render grouping
