---
id: M009-xwi4bt
title: "Preflight Convergence and Auth Bootstrap Unification"
status: complete
completed_at: 2026-04-06T17:15:57.876Z
key_decisions:
  - D049: D048 superseded — flow.py and flow_interactive.py now use shared preflight before plan construction, not inline ensure_provider_image/ensure_provider_auth. The ordering constraint D048 cited was narrower than assumed — auth bootstrap only needs provider_id and the adapter, not the full StartSessionPlan.
key_files:
  - src/scc_cli/commands/launch/preflight.py
  - src/scc_cli/commands/launch/flow.py
  - src/scc_cli/commands/launch/flow_interactive.py
  - src/scc_cli/commands/launch/auth_bootstrap.py
  - src/scc_cli/commands/worktree/worktree_commands.py
  - src/scc_cli/ui/dashboard/orchestrator_handlers.py
  - src/scc_cli/setup.py
  - tests/test_launch_preflight.py
  - tests/test_launch_preflight_guardrail.py
  - tests/test_auth_vocabulary_guardrail.py
lessons_learned:
  - When a function uses deferred imports to satisfy architecture guards, test mocks must patch the definition site of the deferred import, not the consumer module — this is the opposite of the usual rule for re-exported names because deferred imports bind fresh on each call.
  - When deprecating a module by making it a thin redirect, keep the old signature alive for test compatibility rather than deleting outright. An optional parameter on the canonical function may be needed for backward-compat when the redirect cannot construct all dependencies.
  - Placing readiness checks before plan construction (not after) is strictly better — it fails faster and avoids unnecessary plan work when the provider isn't ready. D048's ordering constraint assumption was narrower than assumed.
---

# M009-xwi4bt: Preflight Convergence and Auth Bootstrap Unification

**All five launch paths now use the same three-function preflight sequence with auth bootstrap actually firing, auth messaging in one place, and setup showing consistent three-tier readiness.**

## What Happened

M009 closed the last structural asymmetries in the launch preflight system that M008 had mostly unified.

**S01 (high risk, 3 tasks)** fixed a silent auth bootstrap gap where ensure_launch_ready() showed the auth notice but never called provider.bootstrap_auth(), then migrated the final two launch sites (flow.py start() and flow_interactive.py run_start_wizard_flow()) from inline ensure_provider_image + ensure_provider_auth to the shared collect_launch_readiness() + ensure_launch_ready() path. The readiness check was placed before plan construction (not after conflict resolution as D048 originally assumed), which is strictly better — fails faster and avoids unnecessary plan work when the provider isn't ready. D048 was superseded by D049. Auth messaging was centralized by reducing auth_bootstrap.py to a deprecated redirect delegating to preflight._ensure_auth(), with the canonical auth vocabulary living in one function. The anti-drift guardrail was extended to cover all migrated files.

**S02 (low risk, 1 task)** replaced inline two-tier status logic in setup.py's _render_provider_status() with a call to the existing _three_tier_status() helper, making both the onboarding panel and completion summary show identical four-state readiness vocabulary. Provider preference hints (scc provider show/set) were added to setup next-steps.

Net result: 3 new tests (5117 total), zero regressions, ruff clean, mypy 303 files 0 issues.

## Success Criteria Results

- ✅ **flow.py and flow_interactive.py use collect_launch_readiness() + ensure_launch_ready()** — Confirmed via grep: flow.py imports and calls both at lines 41/338/342; flow_interactive.py at lines 85/721/725. No ensure_provider_image/ensure_provider_auth calls remain.
- ✅ **ensure_launch_ready() actually performs auth bootstrap** — preflight.py line 373 calls `provider.bootstrap_auth()` inside `_ensure_auth()`. Three tests (test_launch_preflight.py) prove the call, exception wrapping, and passthrough behavior.
- ✅ **auth_bootstrap.py reduced to thin redirect** — 68 lines, 1 function, marked `.. deprecated::`, delegates to `preflight._ensure_auth()`.
- ✅ **Auth error messages live in exactly one module** — All auth messaging lives in `preflight._ensure_auth()`. auth_bootstrap.py only delegates.
- ✅ **setup.py _render_provider_status() uses _three_tier_status()** — Line 460 calls `_three_tier_status(provider_id, state)`, matching show_setup_complete() at lines 390/396.
- ✅ **No inline ensure_provider_image/ensure_provider_auth outside preflight.py** — grep confirms zero hits in flow.py, flow_interactive.py, worktree_commands.py, and orchestrator_handlers.py. The only definition-site reference is in provider_image.py (the function definition itself).
- ✅ **Full suite passes with zero regressions** — 5117 passed, 23 skipped, 2 xfailed (above 5114 baseline).
- ✅ **Ruff clean, mypy 303 files 0 issues** — Both pass cleanly.

## Definition of Done Results

- ✅ **All slices complete with passing exit gates** — S01 (3 tasks) and S02 (1 task) both complete with passing verification.
- ✅ **No ensure_provider_image or ensure_provider_auth imports remain in flow.py, flow_interactive.py, orchestrator_handlers.py, or worktree_commands.py** — grep confirms zero hits across all four files.
- ✅ **auth_bootstrap.py reduced to one-line redirect** — 68-line deprecated module with a single function that delegates to preflight._ensure_auth().
- ✅ **Setup shows consistent three-tier readiness in all provider status surfaces** — Both _render_provider_status (line 460) and show_setup_complete (lines 390/396) use _three_tier_status().
- ✅ **KNOWLEDGE.md updated** — Two new lessons added: deferred import mock patching rule and deprecated-module redirect pattern.

## Requirement Outcomes

### R001: Maintainability in touched high-churn areas
**Status: validated → validated (reinforced)**

Evidence: Eliminated duplicated auth/image bootstrap logic from flow.py and flow_interactive.py. Auth messaging centralized from two modules (auth_bootstrap.py + preflight.py) to one (_ensure_auth in preflight.py). Inline status logic in setup.py consolidated to shared _three_tier_status() helper. Anti-drift guardrail extended to prevent regression across all five migrated files. Net improvement: fewer code paths to maintain, one canonical auth messaging location, consistent readiness vocabulary across all surfaces.

## Deviations

S01/T02 placed the readiness check before plan construction rather than after conflict resolution as originally assumed by D048. This was a deliberate improvement — fails faster and matches the dashboard/worktree pattern. D048 superseded by D049.

## Follow-ups

- Delete auth_bootstrap.py entirely after updating test consumers to use preflight._ensure_auth directly, and remove the optional `provider` parameter from _ensure_auth() at the same time.
- start_claude parameter rename to start_agent in worktree_commands.py (carried from M008).
- WorkContext.provider_id threading through _record_session_and_context (carried from M008).
