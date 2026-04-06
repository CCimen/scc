---
id: S02
parent: M008-g7jk8d
milestone: M008-g7jk8d
provides:
  - Three-tier auth vocabulary used consistently across all provider-facing surfaces
  - Docker Desktop confined to infrastructure layers — no active user-facing references
  - Shared get_agent_provider() dispatch helper available for any module needing provider→adapter lookup
  - 15 new guardrail tests preventing auth vocabulary, Docker Desktop, and dispatch consolidation regression
requires:
  - slice: S01
    provides: Shared preflight module (commands/launch/preflight.py) with provider resolution and LaunchReadiness model
affects:
  - S03
key_files:
  - src/scc_cli/commands/launch/provider_choice.py
  - src/scc_cli/commands/launch/dependencies.py
  - src/scc_cli/setup.py
  - src/scc_cli/doctor/checks/environment.py
  - src/scc_cli/commands/admin.py
  - src/scc_cli/commands/worktree/container_commands.py
  - tests/test_auth_vocabulary_guardrail.py
  - tests/test_lifecycle_inventory_consistency.py
  - tests/test_docs_truthfulness.py
  - tests/test_doctor_provider_errors.py
key_decisions:
  - Three-tier auth vocabulary: 'auth cache present' (file exists), 'image available' (image present), 'launch-ready' (both) — enforced by tokenize-based guardrail tests
  - Docker Desktop references confined to docker/, adapters/, core/errors.py, doctor/ layers only — active commands/ paths use 'Docker' or 'container runtime'
  - Shared get_agent_provider(adapters, provider_id) in dependencies.py replaces hardcoded dispatch dicts in provider_choice.py and setup.py
  - prune_cmd intentionally keeps broader image-based inventory (not label-based) for orphan cleanup
patterns_established:
  - Tokenize-based vocabulary guardrail: scan source files for banned terms using Python's tokenize module (not regex) to avoid false positives from comments and strings. See test_auth_vocabulary_guardrail.py.
  - Lifecycle inventory consistency guardrail: test that verifies all command surfaces (list, stop, prune, status, dashboard) use the same inventory source function. See test_lifecycle_inventory_consistency.py.
  - Docker Desktop boundary guardrail: scanning test that prevents Docker Desktop references from leaking into active user-facing paths. See test_docs_truthfulness.py.
observability_surfaces:
  - none
drill_down_paths:
  - .gsd/milestones/M008-g7jk8d/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M008-g7jk8d/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M008-g7jk8d/slices/S02/tasks/T03-SUMMARY.md
  - .gsd/milestones/M008-g7jk8d/slices/S02/tasks/T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-06T13:24:36.486Z
blocker_discovered: false
---

# S02: Auth/readiness wording truthfulness, Docker Desktop cleanup, and adapter dispatch consolidation

**Fixed 6 misleading auth-status strings with three-tier vocabulary, removed Docker Desktop from active user-facing paths, consolidated provider adapter dispatch into shared get_agent_provider() helper, and added 15 new guardrail tests (5008 total).**

## What Happened

S02 delivered three complementary improvements to cross-flow consistency and truthfulness.

**Auth vocabulary truthfulness (T01):** Audited four user-facing modules (provider_choice.py, setup.py, doctor/checks/environment.py, auth_bootstrap.py) for misleading auth/readiness vocabulary. Fixed 6 strings: 'connected' → 'auth cache present' and 'sign-in required' → 'sign-in needed' in provider choice; 'ready' → 'auth cache present' and 'not connected' → 'sign-in needed' in setup summary; 'not connected' → 'sign-in incomplete' in setup error panel; 'auth cache not ready' → 'auth cache missing' in doctor checks. The canonical three-tier vocabulary is now: 'auth cache present' (file exists), 'image available' (container image present), 'launch-ready' (both). Created tests/test_auth_vocabulary_guardrail.py with 5 tokenize-based scanning tests preventing vocabulary regression.

**Docker Desktop cleanup (T02):** Fixed 2 Docker Desktop references in active commands/ paths: admin.py error message ('Ensure Docker Desktop is running' → 'Ensure Docker is running') and container_commands.py comment ('Docker Desktop' → 'containers not created by SCC'). Docker Desktop references are now confined to docker/, adapters/, core/errors.py, and doctor/ layers only. Added boundary guardrail in test_docs_truthfulness.py. Created tests/test_lifecycle_inventory_consistency.py with 7 tests verifying scc list/stop/prune/status and dashboard actions all use the same SCC-managed inventory source. Also fixed 2 stale test assertions in test_doctor_provider_errors.py that T01 broke.

**Adapter dispatch consolidation (T03):** Extracted get_agent_provider(adapters, provider_id) in dependencies.py as a shared dispatch surface using the existing _PROVIDER_DISPATCH table. Replaced hardcoded adapters_by_provider dict in provider_choice.py:collect_provider_readiness() and provider_map dict in setup.py:_run_provider_onboarding(). Verified init.py template uses 'Sandboxed Coding CLI' per D045. Added 3 guardrail tests preventing re-introduction of hardcoded dispatch dicts and verifying branding.

**Full verification (T04):** All 6 exit gate checks passed: ruff clean, mypy clean (303 files), 5008 tests (0 failures, 23 skipped, 2 xfailed), no Docker Desktop in commands/, branding consistent ('Sandboxed Coding CLI' only).

## Verification

Slice-level verification rerun confirmed all gates:
1. `uv run ruff check` — clean
2. `uv run mypy src/scc_cli` — 303 files, 0 issues
3. `uv run pytest tests/test_auth_vocabulary_guardrail.py tests/test_docs_truthfulness.py tests/test_lifecycle_inventory_consistency.py tests/test_start_provider_choice.py -v` — 56 pass
4. `uv run pytest -q` — 5008 passed, 23 skipped, 2 xfailed (62s)
5. `rg 'Docker Desktop' src/scc_cli/commands/` — no matches
6. `rg 'Sandboxed Cod' src/scc_cli/ | grep -v 'Sandboxed Coding CLI'` — no non-conforming variants

## Requirements Advanced

- R001 — 15 new guardrail tests (auth vocabulary, Docker Desktop boundary, lifecycle inventory consistency, dispatch consolidation, branding) bring total guardrail tests to 40+. Adapter dispatch consolidated from 3 sites to 1 shared helper.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

T01 fixed two additional strings not in original plan: 'auth cache not ready' → 'auth cache missing' in doctor checks, and 'not connected' → 'sign-in incomplete' in setup error panel (discovered during audit). T02 fixed 2 stale test assertions in test_doctor_provider_errors.py that were broken by T01's wording changes.

## Known Limitations

None.

## Follow-ups

None.

## Files Created/Modified

- `src/scc_cli/commands/launch/provider_choice.py` — Auth vocabulary: 'connected' → 'auth cache present', 'sign-in required' → 'sign-in needed'. Replaced hardcoded adapters_by_provider dict with get_agent_provider() call.
- `src/scc_cli/setup.py` — Auth vocabulary: 'ready' → 'auth cache present', 'not connected' → 'sign-in needed/incomplete'. Replaced hardcoded provider_map dict with get_agent_provider() call.
- `src/scc_cli/doctor/checks/environment.py` — Auth vocabulary: 'auth cache not ready' → 'auth cache missing'.
- `src/scc_cli/commands/admin.py` — Docker Desktop: 'Ensure Docker Desktop is running' → 'Ensure Docker is running'.
- `src/scc_cli/commands/worktree/container_commands.py` — Docker Desktop: removed 'Docker Desktop' from prune_cmd comment.
- `src/scc_cli/commands/launch/dependencies.py` — Added get_agent_provider(adapters, provider_id) shared dispatch helper.
- `tests/test_auth_vocabulary_guardrail.py` — New: 5 tokenize-based tests scanning for banned auth vocabulary terms.
- `tests/test_lifecycle_inventory_consistency.py` — New: 7 tests verifying command surfaces use consistent SCC-managed inventory.
- `tests/test_docs_truthfulness.py` — Added Docker Desktop boundary guardrail + 3 dispatch/branding guardrail tests.
- `tests/test_doctor_provider_errors.py` — Fixed 2 stale assertions broken by T01 vocabulary changes.
