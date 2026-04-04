---
id: S01
parent: M002
milestone: M002
provides:
  - A live provider-neutral launch-planning seam via `AgentProvider` and `AgentLaunchSpec`.
  - A reference Claude adapter and bootstrap wiring pattern that downstream provider slices can copy without leaking provider details into core contracts.
  - A contract and test harness that mechanically guards the provider seam during future refactors.
requires:
  []
affects:
  - S02
  - S03
  - S04
  - S05
key_files:
  - src/scc_cli/application/start_session.py
  - src/scc_cli/adapters/claude_agent_provider.py
  - src/scc_cli/core/contracts.py
  - src/scc_cli/ports/agent_provider.py
  - src/scc_cli/bootstrap.py
  - tests/test_application_start_session.py
  - tests/test_bootstrap.py
  - tests/test_core_contracts.py
key_decisions:
  - Port the M001 truthful network vocabulary into the diverged M002 worktree before adopting the live seam so contract imports and tests stay coherent.
  - Use `xfail(strict=True)` as the mechanical boundary gate for seam-migration tests, then remove the decorator when live wiring lands.
  - Keep provider settings payloads out of `AgentLaunchSpec.env`; file-based provider configuration travels via `artifact_paths`.
  - Make `agent_provider` optional on `StartSessionDependencies` and return `None` for `agent_launch_spec` in dry-run mode so older callers can migrate incrementally.
patterns_established:
  - Use `xfail(strict=True)` to gate seam migrations until live behavior lands, then remove the decorator instead of rewriting the assertion.
  - For file-based providers, keep `AgentLaunchSpec.env` clean and carry provider configuration artifacts in `artifact_paths`.
  - Treat `bootstrap.py` as the only adapter composition root; application and command layers consume adapter seams through bootstrap exports, not direct adapter imports.
  - When adding a provider to `DefaultAdapters`, update the adapter file, bootstrap wiring, fake-adapter factory, and any inline `DefaultAdapters(...)` constructions together.
observability_surfaces:
  - No new runtime observability endpoint was added in this slice; health is currently signaled by deterministic contract, bootstrap, and launch-path tests plus the green lint/type/test gate.
  - Authoritative launch-path diagnostics now live in `tests/test_application_start_session.py`, `tests/test_bootstrap.py`, and `tests/test_core_contracts.py`, which fail immediately if the seam is no longer wired or if provider-specific data leaks into core contracts.
drill_down_paths:
  - .gsd/milestones/M002/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M002/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-03T19:07:00.564Z
blocker_discovered: false
---

# S01: Live launch-path adoption of AgentProvider and AgentLaunchSpec

**Live start-session planning now routes launch preparation through `AgentProvider` and emits typed `AgentLaunchSpec` objects backed by hard-passing seam-boundary tests.**

## What Happened

S01 turned the provider seam from a planned abstraction into the live launch path. The slice began by backporting the M001 contract foundation into a worktree that had diverged before those files landed: typed launch/provider contracts were restored, the truthful network-policy vocabulary replaced the stale names that would have broken imports, and a fake provider plus seam-boundary tests were added to describe the intended end state. Those boundary tests used `xfail(strict=True)` so the suite would enforce the migration mechanically instead of relying on human bookkeeping.

After the contract layer existed, the slice cleaned up the small lint fallout from the new imports and then finished the real adoption work: `ClaudeAgentProvider` became a concrete `AgentProvider`, `bootstrap.py` started wiring `agent_provider` into `DefaultAdapters`, and `prepare_start_session()` began building a typed `agent_launch_spec` alongside the sandbox plan. The launch spec stays provider-neutral: file-based settings are referenced through `artifact_paths`, not stuffed into env vars, and unwired or dry-run paths intentionally return `None` so call sites can migrate incrementally.

The final result is that launch planning now consumes the provider seam end to end, the three S01 seam tests that started life as strict xfails are ordinary passing tests, and downstream slices inherited a stable pattern for future provider work: keep adapter composition in `bootstrap.py`, keep shared contracts typed and provider-neutral, and characterize every provider with the same minimal test shape.

## Verification

Executed every verification command defined in the slice plan and all passed in the worktree. `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_core_contracts.py` passed with 19 tests green. `uv run pytest tests/test_application_start_session.py tests/test_bootstrap.py tests/test_start_wizard_quick_resume_flow.py tests/test_start_wizard_workspace_quick_resume.py` passed with 13 tests green. The full gate `uv run ruff check && uv run mypy src/scc_cli && uv run pytest --tb=short -q` also passed: ruff clean, mypy clean on 236 source files, and pytest green at 3249 passed / 0 failed / 23 skipped / 3 xfailed / 1 xpassed. Because this slice changes real launch orchestration behavior, those tests are the authoritative health signal; there is no separate runtime status endpoint yet.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

The worktree branch predated M001, so the slice had to port the truthful network-policy vocabulary and typed contract files up front before any live launch-path adoption work could compile. T02 also spent a cycle on two auto-fixable lint regressions introduced by the contract import additions. Finally, two inline `DefaultAdapters(...)` constructions outside the shared fake-adapter factory had to be updated when `agent_provider` was added to the shared adapter bundle.

## Known Limitations

This slice does not yet validate provider-core destinations before launch and does not persist a durable launch audit record; those responsibilities remain in S04. Operational diagnostics are still test-driven rather than backed by a runtime status surface. The live path proven here is Claude-first; the seam is provider-neutral, but additional providers still depend on their own adapters and characterization tests.

## Follow-ups

S04 should add pre-launch validation that provider-core destinations are reachable before launch and should persist a durable audit record of launch decisions. S05 should build on the seam now that launch preparation is typed and live, especially for diagnostics and decomposition around launch planning.

## Files Created/Modified

- `src/scc_cli/application/start_session.py` — Introduced the live launch-path seam by building `agent_launch_spec` during start-session planning and by making the provider dependency optional for incremental adoption.
- `src/scc_cli/adapters/claude_agent_provider.py` — Added the reference `ClaudeAgentProvider` adapter that turns provider settings into a provider-neutral `AgentLaunchSpec`.
- `src/scc_cli/core/contracts.py` — Extended the typed contract surface with `AgentLaunchSpec` and `ProviderCapabilityProfile`, and migrated the worktree to the truthful network-policy vocabulary required by those contracts.
- `src/scc_cli/ports/agent_provider.py` — Added the `AgentProvider` protocol that providers must satisfy at the application boundary.
- `src/scc_cli/bootstrap.py` — Kept `bootstrap.py` as the only composition root by wiring `agent_provider` into `DefaultAdapters` and `get_default_adapters()`.
- `tests/test_application_start_session.py` — Added seam-boundary and contract tests that first gated the migration with `xfail(strict=True)` and then promoted to hard-passing tests once live wiring landed.
- `tests/test_bootstrap.py` — Pinned bootstrap composition behavior and provider availability in the default adapter bundle.
- `tests/test_core_contracts.py` — Characterized the provider-neutral contract shape, including artifact-path handling and the clean-env rule.
