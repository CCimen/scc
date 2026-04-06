---
verdict: pass
remediation_round: 0
---

# Milestone Validation: M009-xwi4bt

## Success Criteria Checklist
### Success Criteria (derived from Vision + Slice "After this")

- [x] **All five launch sites use shared preflight sequence** — grep confirms flow.py, flow_interactive.py, worktree_commands.py, and orchestrator_handlers.py (two handlers) all import and call `collect_launch_readiness()` + `ensure_launch_ready()` from preflight.py. No inline `ensure_provider_image`/`ensure_provider_auth` calls outside preflight.py.
- [x] **ensure_launch_ready actually calls bootstrap_auth()** — preflight.py line 373 calls `provider.bootstrap_auth()` inside `_ensure_auth()`. Three tests prove: call happens when auth missing (interactive), exceptions wrapped as ProviderNotReadyError, ProviderNotReadyError passes through.
- [x] **auth_bootstrap.py eliminated or trivial** — 68 lines, reduced to a deprecated redirect. No production code imports `ensure_provider_auth` from it. Only `show_auth_bootstrap_panel` from `render` module is still imported (different module, different function).
- [x] **Auth messaging in one place** — `_ensure_auth()` in preflight.py is the sole canonical auth messaging location. Vocabulary guardrail test confirms.
- [x] **setup.py _render_provider_status shows four-state readiness** — line 460 calls `_three_tier_status(provider_id, state)`, same helper used by `show_setup_complete` at lines 390 and 396. Both surfaces share identical vocabulary.
- [x] **No structural asymmetry across launch paths** — all five sites follow resolve_launch_provider → collect_launch_readiness → ensure_launch_ready. Anti-drift guardrail in test_launch_preflight_guardrail.py prevents regression.

## Slice Delivery Audit
| Slice | Claimed Deliverable | Delivered | Evidence |
|-------|--------------------|-----------| ---------|
| S01 | All five launch sites on shared preflight; bootstrap_auth() actually called; auth_bootstrap.py eliminated or trivial; auth messaging centralized | ✅ Yes | grep confirms 5 sites using shared preflight; preflight.py:373 calls bootstrap_auth(); auth_bootstrap.py is 68-line deprecated redirect; no production imports of ensure_provider_auth from auth_bootstrap; 65 targeted tests pass; D049 recorded superseding D048 |
| S02 | _render_provider_status uses _three_tier_status; same as show_setup_complete | ✅ Yes | setup.py:460 calls _three_tier_status(); lines 390,396 use same helper in show_setup_complete; provider preference hints added to next-steps |

## Cross-Slice Integration
S01 provides the unified preflight path that S02 depends on for consistent vocabulary. No boundary mismatch — S02 builds on top of S01's auth vocabulary normalization and the _three_tier_status() helper that was already available pre-M009. No cross-slice data or contract conflicts.

## Requirement Coverage
**R001 (maintainability):** Advanced by both slices. S01 eliminated duplicated auth/image bootstrap logic from flow.py and flow_interactive.py, centralized auth messaging from two modules to one. S02 eliminated duplicated inline status logic in setup.py. Both reduce maintenance surface and inconsistency risk. R001 status remains "validated" — this milestone strengthens the evidence.

## Verification Class Compliance
### Contract Verification
- **Status: ✅ PASS**
- Fresh run: `uv run ruff check` — All checks passed (0 errors)
- Fresh run: `uv run mypy src/scc_cli` — Success: no issues found in 303 source files
- Fresh run: `uv run pytest -q` — 5117 passed, 23 skipped, 2 xfailed in 63.22s
- Test count (5117) exceeds the 5114+ threshold from planning.

### Integration Verification
- **Status: ✅ PASS**
- All five launch paths confirmed via grep: flow.py:338/342, flow_interactive.py:721/725, worktree_commands.py:267/271, orchestrator_handlers.py:249/251 and 439/441
- All five import from preflight module, all use collect_launch_readiness → ensure_launch_ready
- grep confirms no ensure_provider_image/ensure_provider_auth calls outside preflight.py (only definition in provider_image.py and the single canonical consumer in preflight.py:300/302)
- Anti-drift guardrail (test_launch_preflight_guardrail.py) covers all migrated files

### Operational Verification
- **Status: ✅ PASS**
- setup.py _render_provider_status (line 460) and show_setup_complete (lines 390, 396) both call _three_tier_status() — no duplication
- Auth bootstrap messaging lives solely in preflight._ensure_auth() — vocabulary guardrail test confirms
- auth_bootstrap.py has zero non-test production importers (grep verified)

### UAT Verification
- **Status: ⚠️ PARTIAL (acceptable)**
- UAT checklists written for both S01 and S02 with detailed test cases
- S01 UAT test cases 1-7 are all automatable and covered by the test suite (bootstrap invocation, exception wrapping, grep verification, guardrail tests, full suite regression)
- S02 UAT test cases 1-5 describe manual UI verification of the setup wizard — these require an interactive terminal session and are not automatable in CI. However, the structural claim (both surfaces call the same _three_tier_status helper) is mechanically verified by grep.
- No UAT gap blocks milestone completion.


## Verdict Rationale
All success criteria met with fresh evidence. Both slices delivered exactly what was claimed. The exit gate is fully green (ruff clean, mypy clean, 5117 tests pass). The five-site preflight convergence is structurally verified by grep and mechanically guarded by anti-drift tests. Auth bootstrap actually fires (proven by 3 targeted tests). Auth messaging lives in one canonical location. Setup surfaces share the same helper. The only minor item is that auth_bootstrap.py still exists as a 68-line deprecated redirect rather than being fully deleted — this is a documented follow-up, not a gap. S02 UAT test cases for manual UI verification are structural rather than interactive, but the underlying claim is mechanically verified. No material gaps found.
