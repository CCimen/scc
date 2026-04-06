---
id: S01
parent: M009-xwi4bt
milestone: M009-xwi4bt
provides:
  - Unified preflight path: all launch sites use collect_launch_readiness() + ensure_launch_ready()
  - Auth bootstrap actually fires when auth is missing (silent gap closed)
  - Canonical auth messaging lives in preflight._ensure_auth() only
  - auth_bootstrap.py is a deprecated redirect — safe to delete in future cleanup
requires:
  []
affects:
  - S02
key_files:
  - src/scc_cli/commands/launch/preflight.py
  - src/scc_cli/commands/launch/flow.py
  - src/scc_cli/commands/launch/flow_interactive.py
  - src/scc_cli/commands/launch/auth_bootstrap.py
  - src/scc_cli/commands/worktree/worktree_commands.py
  - src/scc_cli/ui/dashboard/orchestrator_handlers.py
  - tests/test_launch_preflight.py
  - tests/test_launch_preflight_guardrail.py
  - tests/test_auth_vocabulary_guardrail.py
  - tests/test_start_codex_auth_bootstrap.py
key_decisions:
  - D049: D048 superseded — flow.py and flow_interactive.py now use shared preflight before plan construction, not inline ensure_provider_image/ensure_provider_auth after conflict resolution
  - Readiness check placed before plan construction to fail faster and match dashboard/worktree pattern
  - Resume and dry-run paths skip readiness entirely
  - auth_bootstrap.py kept as deprecated redirect rather than deleted, for test compatibility
  - Optional provider parameter added to _ensure_auth for redirect compatibility
  - Deferred import of get_agent_provider inside _ensure_auth to satisfy D046 architecture guard
patterns_established:
  - All five launch sites now follow the same three-function preflight sequence: resolve_launch_provider() → collect_launch_readiness() → ensure_launch_ready()
  - Auth bootstrap is invoked inside ensure_launch_ready via _ensure_auth — no caller needs to separately manage auth
  - The anti-drift guardrail in test_launch_preflight_guardrail.py covers all migrated files, preventing regression to inline ensure_provider_image/ensure_provider_auth calls
  - Deprecated redirect pattern: auth_bootstrap.py delegates to the canonical implementation in preflight._ensure_auth rather than being deleted outright, preserving test compatibility
observability_surfaces:
  - Auth bootstrap failures are wrapped as ProviderNotReadyError with actionable guidance — consistent across all five launch paths
  - Auth vocabulary guardrail (test_auth_vocabulary_guardrail.py) now checks preflight.py as the canonical auth messaging source
drill_down_paths:
  - .gsd/milestones/M009-xwi4bt/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M009-xwi4bt/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M009-xwi4bt/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-06T16:59:40.982Z
blocker_discovered: false
---

# S01: Unify all launch paths on shared preflight and fix auth bootstrap gap

**All five launch sites now call collect_launch_readiness() + ensure_launch_ready() through the shared preflight module, with bootstrap_auth() actually invoked when auth is missing, and auth messaging centralized in one function.**

## What Happened

This slice closed two structural gaps in the launch preflight system and completed the migration that M008 started.

**T01 — Fixed the silent auth gap.** The shared ensure_launch_ready() showed an auth bootstrap notice but never called provider.bootstrap_auth(). Added an `adapters` parameter so _ensure_auth() can resolve the provider adapter via get_agent_provider() and call bootstrap_auth() after the notice. Exception handling mirrors the old auth_bootstrap.py: ProviderNotReadyError passes through, other exceptions get wrapped. Three new tests prove the bootstrap call, exception wrapping, and passthrough behavior. All callers (worktree_commands.py, orchestrator_handlers.py) updated.

**T02 — Migrated the last two launch sites.** flow.py start() and flow_interactive.py run_start_wizard_flow() replaced their inline ensure_provider_image + ensure_provider_auth calls with collect_launch_readiness() + ensure_launch_ready(). The readiness check is placed after provider resolution but before plan construction — this is strictly better than the old position (after conflict resolution) because it fails faster and avoids unnecessary plan construction. Resume and dry-run paths skip readiness entirely. The anti-drift guardrail now bans the old functions from all migrated files. D048 is superseded by D049.

**T03 — Centralized auth messaging.** With all launch sites on shared preflight, auth_bootstrap.py had zero non-test callers. Reduced it to a deprecated redirect that builds a minimal LaunchReadiness and delegates to preflight._ensure_auth(). Added an optional `provider` parameter to _ensure_auth() for redirect compatibility. The vocabulary guardrail test now checks preflight.py as the canonical auth messaging location.

## Verification

Exit gate: `uv run ruff check` (0 errors), `uv run mypy src/scc_cli` (303 files, 0 issues), `uv run pytest -q` (5117 passed, 23 skipped, 2 xfailed). Targeted tests: test_launch_preflight.py (53 passed), test_launch_preflight_guardrail.py (7 passed), test_auth_vocabulary_guardrail.py (5 passed), test_start_dryrun.py (10 passed, 4 skipped), test_integration.py (20 passed), test_start_codex_auth_bootstrap.py (3 passed). grep confirms ensure_provider_image and ensure_provider_auth are absent from flow.py and flow_interactive.py. grep confirms no non-test imports from auth_bootstrap module.

## Requirements Advanced

- R001 — Eliminated duplicated auth/image bootstrap logic from flow.py and flow_interactive.py. Auth messaging centralized from two modules (auth_bootstrap.py + preflight.py) to one (_ensure_auth in preflight.py). Anti-drift guardrail prevents regression.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

T02 placed the readiness check before plan construction (not after conflict resolution as originally specced). This is a deliberate improvement — fails faster and matches the dashboard/worktree pattern. D048 superseded by D049.

## Known Limitations

auth_bootstrap.py still exists as a deprecated redirect for test compatibility. A future cleanup can delete it entirely once tests are updated to use preflight directly. The optional `provider` parameter on _ensure_auth() is a backward-compat convenience for the redirect — it could be removed when auth_bootstrap.py is deleted.

## Follow-ups

Delete auth_bootstrap.py entirely after updating its test consumers to use preflight._ensure_auth directly. Remove the optional `provider` parameter from _ensure_auth() at the same time.

## Files Created/Modified

- `src/scc_cli/commands/launch/preflight.py` — Added adapters parameter to ensure_launch_ready() and _ensure_auth(). _ensure_auth now calls bootstrap_auth() via get_agent_provider() after showing the auth notice. Added optional provider parameter for deprecated redirect compatibility.
- `src/scc_cli/commands/launch/flow.py` — Replaced inline ensure_provider_image + ensure_provider_auth with collect_launch_readiness() + ensure_launch_ready(). Readiness check before plan construction. Resume and dry-run paths skip readiness.
- `src/scc_cli/commands/launch/flow_interactive.py` — Replaced inline ensure_provider_image + ensure_provider_auth with collect_launch_readiness() + ensure_launch_ready(). Same pattern as flow.py.
- `src/scc_cli/commands/launch/auth_bootstrap.py` — Reduced to deprecated redirect delegating to preflight._ensure_auth(). Preserves old ensure_provider_auth signature for test compatibility.
- `src/scc_cli/commands/worktree/worktree_commands.py` — Updated ensure_launch_ready() call to pass adapters parameter.
- `src/scc_cli/ui/dashboard/orchestrator_handlers.py` — Updated ensure_launch_ready() call to pass adapters parameter.
- `tests/test_launch_preflight.py` — Added 3 new tests for bootstrap_auth call, exception wrapping, and ProviderNotReadyError passthrough. Updated existing tests for adapters parameter.
- `tests/test_launch_preflight_guardrail.py` — Extended anti-drift guardrail to ban ensure_provider_image/ensure_provider_auth from flow.py and flow_interactive.py.
- `tests/test_auth_vocabulary_guardrail.py` — Updated to check preflight.py as canonical auth messaging location.
- `tests/test_start_codex_auth_bootstrap.py` — Updated to mock shared preflight functions instead of inline image/auth calls.
- `tests/test_workspace_provider_persistence.py` — Updated mocks for shared preflight migration.
- `tests/test_cli.py` — Updated mocks for shared preflight migration.
- `tests/test_launch_preflight_characterization.py` — Updated mocks for shared preflight migration.
- `tests/test_resume_after_drift.py` — Updated for ensure_launch_ready adapters parameter.
