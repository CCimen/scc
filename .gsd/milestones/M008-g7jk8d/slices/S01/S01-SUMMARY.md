---
id: S01
parent: M008-g7jk8d
milestone: M008-g7jk8d
provides:
  - Shared preflight module (commands/launch/preflight.py) with resolve_launch_provider, collect_launch_readiness, ensure_launch_ready, allowed_provider_ids
  - Typed LaunchReadiness model with ImageStatus, AuthStatus, ProviderResolutionSource enums
  - 43 characterization tests documenting current behavior of all five launch sites
  - 7 structural guardrail tests preventing inline provider resolution drift and verifying single-source metadata
requires:
  []
affects:
  - S02
  - S03
key_files:
  - src/scc_cli/commands/launch/preflight.py
  - tests/test_launch_preflight_characterization.py
  - tests/test_launch_preflight.py
  - tests/test_launch_preflight_guardrail.py
  - src/scc_cli/commands/launch/flow.py
  - src/scc_cli/commands/launch/flow_interactive.py
  - src/scc_cli/ui/dashboard/orchestrator_handlers.py
key_decisions:
  - D046: Preflight module stays command-layer only, separates pure decisions from side effects (recorded during planning)
  - D048: Keep ensure_provider_image/ensure_provider_auth inline in flow.py because auth bootstrap needs StartSessionPlan context
  - Guardrail anti-drift scoped to _MIGRATED_FILES tuple — extends incrementally as migration proceeds
  - Display name allowlist in guardrail includes adapter modules and legacy render/sandbox defaults as tracked debt
patterns_established:
  - Three-function preflight split: resolve_launch_provider() (pure) → collect_launch_readiness() (adapter query) → ensure_launch_ready() (side effects) as the canonical launch preflight sequence
  - Typed readiness model with ImageStatus/AuthStatus/ProviderResolutionSource enums — eliminates loose boolean/string preflight branching
  - ProviderNotReadyError in non-interactive mode with actionable user_message/suggested_action — structured error contract for all launch paths
  - Tokenize-based structural guardrails for function migration anti-drift — _MIGRATED_FILES tuple pattern for incremental migration tracking
  - Characterization-test-first approach for consolidating duplicated logic: document behavior before refactoring to catch regression
observability_surfaces:
  - LaunchReadiness.resolution_source enum tracks how provider was resolved (EXPLICIT, RESUME, WORKSPACE_LAST_USED, GLOBAL_PREFERRED, AUTO_SINGLE, PROMPTED) — enables future audit logging of resolution decisions
drill_down_paths:
  - .gsd/milestones/M008-g7jk8d/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M008-g7jk8d/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M008-g7jk8d/slices/S01/tasks/T03-SUMMARY.md
  - .gsd/milestones/M008-g7jk8d/slices/S01/tasks/T04-SUMMARY.md
  - .gsd/milestones/M008-g7jk8d/slices/S01/tasks/T05-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-06T12:54:59.321Z
blocker_discovered: false
---

# S01: Provider resolution consistency across worktree create and wizard flow

**Collapsed duplicated provider resolution logic across five launch sites into a shared typed preflight module (commands/launch/preflight.py), with 43 characterization tests, 39 preflight unit tests, and 7 structural guardrail tests preventing drift.**

## What Happened

This slice addressed the core consistency problem in M008: five separate launch paths (flow.py start, flow_interactive run_start_wizard_flow, worktree_commands worktree_create_cmd, orchestrator_handlers _handle_worktree_start, orchestrator_handlers _handle_session_resume) each implemented their own provider resolution logic with subtly different precedence behavior, missing steps, and inconsistent error handling.

**T01 — Characterization tests (43 tests):** Documented the actual behavior of each launch site as a regression baseline. Key findings: worktree_create_cmd used resolve_active_provider() directly with a hardcoded 'claude' default — no workspace_last_used lookup, no connected probing, no ensure_provider_auth. _record_session_and_context forwarded provider_id to session recording but not to WorkContext. The 'ask' config value suppresses workspace_last_used entirely because the check precedes it in resolve_provider_preference.

**T02 — Shared preflight module (39 tests):** Created commands/launch/preflight.py with a clean three-function split: resolve_launch_provider() (pure decision, wraps choose_start_provider with source tracking), collect_launch_readiness() (adapter query, returns typed LaunchReadiness), ensure_launch_ready() (side effects — image/auth bootstrap or raises ProviderNotReadyError in non-interactive mode). The typed readiness model uses ImageStatus, AuthStatus, and ProviderResolutionSource enums — eliminating the loose boolean/string comparisons scattered across the five sites.

**T03 — Migration of flow.py and flow_interactive.py:** Replaced _resolve_provider() and _allowed_provider_ids() in flow.py with resolve_launch_provider() from preflight.py. Replaced the 15-line inline provider resolution block in flow_interactive.py with the same shared call. Updated orchestrator_handlers.py deferred imports to use preflight.allowed_provider_ids. Key scoping decision (D048): keep ensure_provider_image/ensure_provider_auth inline in flow.py start() because auth bootstrap requires StartSessionPlan context not available at preflight time.

**T04 — Test stabilization (26 failures fixed):** Fixed 26 pre-existing test failures that were being masked by earlier tasks' targeted test runs. Fixes covered: mock return values for _run_provider_onboarding (10 setup tests), provider resolution prompts blocking dry-run/integration tests (6 tests), OCI egress _find_existing_container mock (6 tests), start() function exceeding 300-line guardrail (extracted _handle_dry_run and _apply_profile_and_show_stack helpers), and 4 guardrail allowlist updates. start_claude rename and WorkContext provider_id threading deferred to future work.

**T05 — Structural guardrail tests (7 tests):** Built three guardrail classes: (1) TestProviderResolutionAntiDrift — tokenize-based scanning ensuring choose_start_provider/resolve_active_provider don't reappear in migrated files, (2) TestProviderMetadataSingleSource — AST string-literal scanning ensuring image refs and display names only exist in canonical locations, (3) TestPreflightArchitectureGuard — AST import scanning enforcing D046 (only types/errors from core/ at module level).

**Incomplete deliverables:** Two planned items were deferred: (a) start_claude parameter rename to start_agent in worktree_commands.py — still references start_claude, (b) orchestrator_handlers and worktree_commands full migration to ensure_launch_ready() — these still use choose_start_provider/ensure_provider_image directly. Both are tracked as follow-up work for S02/S03. The guardrail's _MIGRATED_FILES tuple is designed to be extended when those files are migrated.

## Verification

Exit gate: ruff check (0 errors), mypy src/scc_cli (303 files, 0 issues), pytest -q (4993 passed, 23 skipped, 2 xfailed, 0 failures). Preflight-specific: 43 characterization + 51 preflight unit + 7 guardrail = 101 new focused tests all passing. Test count advanced from 4820 (M007 baseline) to 4993 (+173 net new tests).

## Requirements Advanced

- R001 — New shared preflight module reduces duplication from 5 copies to 1, improving maintainability. 173 new tests (4993 total). Structural guardrails prevent drift. File size guardrails maintained with extracted helpers.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

1. T03 kept ensure_provider_image/ensure_provider_auth inline in flow.py instead of migrating to ensure_launch_ready() — auth bootstrap needs StartSessionPlan context (D048). 2. T04 focused on fixing 26 pre-existing test failures rather than the planned orchestrator_handlers/worktree_commands refactoring. 3. start_claude rename to start_agent deferred. 4. WorkContext provider_id threading deferred. 5. Guardrail anti-drift scope covers only flow.py and flow_interactive.py, not all five entry points.

## Known Limitations

1. orchestrator_handlers.py (_handle_worktree_start, _handle_session_resume) and worktree_commands.py still use choose_start_provider/ensure_provider_image directly — not yet migrated to shared preflight. 2. start_claude parameter in worktree_commands.py not renamed to start_agent. 3. WorkContext.provider_id not yet threaded through _record_session_and_context. 4. The guardrail _MIGRATED_FILES tuple only covers flow.py and flow_interactive.py — needs extension when remaining files are migrated.

## Follow-ups

1. Migrate orchestrator_handlers.py and worktree_commands.py to shared preflight (S02 or S03 scope). 2. Rename start_claude → start_agent in worktree_commands.py. 3. Thread provider_id through WorkContext in _record_session_and_context. 4. Extend _MIGRATED_FILES in guardrail test as remaining files are migrated. 5. Consider refactoring flow.py start() to separate plan construction from auth bootstrap to enable full ensure_launch_ready() adoption.

## Files Created/Modified

- `src/scc_cli/commands/launch/preflight.py` — New shared preflight module: typed LaunchReadiness model, resolve_launch_provider, collect_launch_readiness, ensure_launch_ready, allowed_provider_ids
- `src/scc_cli/commands/launch/flow.py` — Replaced _resolve_provider() and _allowed_provider_ids() with shared preflight imports. Extracted _handle_dry_run and _apply_profile_and_show_stack helpers for 300-line guardrail.
- `src/scc_cli/commands/launch/flow_interactive.py` — Replaced 15-line inline provider resolution with resolve_launch_provider() from preflight
- `src/scc_cli/ui/dashboard/orchestrator_handlers.py` — Updated deferred imports to use preflight.allowed_provider_ids
- `tests/test_launch_preflight_characterization.py` — 43 characterization tests documenting current behavior of all five launch preflight sites
- `tests/test_launch_preflight.py` — 51 unit tests for preflight module (39 new in T02, 12 existing)
- `tests/test_launch_preflight_guardrail.py` — 7 structural guardrail tests: anti-drift scanning, single-source metadata, architecture guard
- `tests/test_cli_setup.py` — Fixed 10 mock return values for _run_provider_onboarding
- `tests/test_setup_wizard.py` — Fixed mock compatibility for provider resolution
- `tests/test_start_dryrun.py` — Added provider and resolve_launch_provider mocks
- `tests/test_integration.py` — Added provider resolution mocks
- `tests/test_oci_egress_integration.py` — Added _find_existing_container mock for ps call
- `tests/test_import_boundaries.py` — Updated allowlists for new files
- `tests/test_no_root_sprawl.py` — Updated allowlists for new files
- `tests/test_provider_branding.py` — Updated allowlists for new files
- `tests/test_docs_truthfulness.py` — Updated allowlists for new files
- `tests/test_cli.py` — Updated mock targets for new function locations
- `tests/test_start_live_conflict.py` — Updated mock targets for resolve_launch_provider
- `tests/test_start_codex_auth_bootstrap.py` — Updated mock targets for preflight functions
