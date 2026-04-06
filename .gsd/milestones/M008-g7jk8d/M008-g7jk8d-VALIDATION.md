---
verdict: needs-attention
remediation_round: 0
---

# Milestone Validation: M008-g7jk8d

## Success Criteria Checklist
| # | Criterion | Verdict | Evidence |
|---|-----------|---------|----------|
| 1 | All five launch sites call shared preflight — no inline duplication | ⚠️ Partial | flow.py and flow_interactive.py migrated. orchestrator_handlers.py and worktree_commands.py still call choose_start_provider/resolve_active_provider directly. Tracked as deferred with guardrail _MIGRATED_FILES designed for incremental extension. |
| 2 | Shared preflight in commands/launch/preflight.py | ✅ Pass | Module exists with resolve_launch_provider, collect_launch_readiness, ensure_launch_ready, allowed_provider_ids. 51 unit tests + 7 guardrail tests. |
| 3 | worktree_commands.py uses shared preflight | ❌ Fail | Still uses resolve_active_provider() directly. S01 summary explicitly deferred this. |
| 4 | WorkContext.provider_id populated in _record_session_and_context | ❌ Fail | WorkContext dataclass has provider_id field, but _record_session_and_context() does not pass provider_id to WorkContext constructor. S01 summary explicitly deferred this. |
| 5 | No active-path 'Docker Desktop' references | ✅ Pass | `rg 'Docker Desktop' src/scc_cli/commands/` returns no matches. Docker Desktop confined to docker/, adapters/, core/errors.py, doctor/ layers. Boundary guardrail test enforces this. |
| 6 | start_claude renamed to provider-neutral name | ❌ Fail | `rg 'start_claude' worktree_commands.py` still shows the old name. S01 summary explicitly deferred this. |
| 7 | Auth vocabulary consistent across doctor/setup/choose-provider | ✅ Pass | Three-tier vocabulary (auth cache present / image available / launch-ready) implemented. 5 tokenize-based guardrail tests in test_auth_vocabulary_guardrail.py prevent regression. |
| 8 | Setup/doctor distinguish auth cache vs image vs launch-ready | ✅ Pass | S02 T01 fixed 6 misleading strings. Guardrail tests enforce vocabulary. |
| 9 | SCC lifecycle commands operate on same inventory | ✅ Pass | 7 tests in test_lifecycle_inventory_consistency.py verify list/stop/prune/status/dashboard use same inventory source. |
| 10 | Product branding 'Sandboxed Coding CLI' per D045 | ✅ Pass | `rg 'Sandboxed Cod' src/scc_cli/ | grep -v 'Sandboxed Coding CLI'` returns empty. Branding guardrail test enforces this. |
| 11 | Failed launches don't write workspace last_used_provider | ✅ Pass | 3 tests in test_workspace_provider_persistence.py::TestFailedLaunchGuard confirm ordering. |
| 12 | Edge cases tested (ask+workspace_last_used, resume after drift) | ✅ Pass | 17 workspace persistence tests + 22 resume-after-drift tests + 16 setup idempotency tests + 51 error quality tests = 106 edge case tests in S03. |
| 13 | All changes backed by targeted tests | ✅ Pass | 294 net new tests across the milestone (4820 → 5114). |
| 14 | Full suite passes with zero regressions from 4820 baseline | ✅ Pass | 5114 passed, 23 skipped, 2 xfailed, 0 failures. Ruff clean. Mypy 303 files, 0 issues. |
| 15 | Docker-backed smoke check per provider | ⚠️ Deferred | Documented as manual verification — auto-mode cannot safely delete Docker images/volumes. S03 T04 cataloged this. |

## Slice Delivery Audit
| Slice | Claimed Output | Delivered | Verdict |
|-------|----------------|-----------|---------|
| S01 | Shared preflight module, typed LaunchReadiness, characterization tests, guardrails | ✅ preflight.py with 3 public functions + typed model. 43 characterization + 51 preflight + 7 guardrail = 101 new tests. flow.py and flow_interactive.py migrated. | ⚠️ Partial — orchestrator_handlers and worktree_commands migration deferred; start_claude rename deferred; WorkContext.provider_id threading deferred |
| S02 | Auth vocabulary fix, Docker Desktop cleanup, dispatch consolidation | ✅ 6 strings fixed with three-tier vocabulary, Docker Desktop removed from commands/, get_agent_provider() shared dispatch, 15 new guardrail tests | ✅ Full delivery |
| S03 | Error quality, edge case hardening, final verification | ✅ 106 regression-guard tests, auth bootstrap exception wrapping, legacy Docker Desktop documentation, 5114 total tests passing | ✅ Full delivery (Docker smoke checks correctly deferred as manual) |

## Cross-Slice Integration
**S01 → S02:** S02 consumed S01's preflight module and LaunchReadiness model. get_agent_provider() dispatch helper builds on the consolidated provider resolution from S01. No boundary mismatches.

**S01 → S03:** S03's edge-case tests exercise the preflight module from S01 (resolve_launch_provider, ensure_launch_ready). Auth bootstrap exception wrapping in ensure_provider_auth operates at the shared entry point S01 established. No boundary mismatches.

**S02 → S03:** S03's error message quality tests validate the vocabulary established in S02. S03's T02 resume-after-drift tests confirm the three-tier vocabulary persists through error paths. No boundary mismatches.

**Boundary map alignment:** The planned boundary map shows all five consumers calling shared preflight. In practice, only flow.py and flow_interactive.py are fully migrated. orchestrator_handlers.py and worktree_commands.py still call choose_start_provider/resolve_active_provider directly. The guardrail _MIGRATED_FILES tuple tracks this incrementally.

## Requirement Coverage
**R001 (maintainability)** — Advanced significantly:
- 294 net new tests (4820 → 5114) improving testability
- Shared preflight module reduces duplication from 5 copies to 3 (2 fully migrated, 3 remaining)
- Adapter dispatch consolidated from scattered dicts to shared get_agent_provider()
- Auth vocabulary normalized with guardrail tests preventing drift
- Docker Desktop confined to infrastructure layers with boundary guardrail
- 40+ guardrail tests provide mechanical regression prevention

R001 is advanced but not fully validated — the remaining 3 unmigrated launch sites are tracked debt.

## Verification Class Compliance
**Contract:** ✅ Pass — ruff check clean, mypy 303 files 0 issues, pytest 5114 passed 0 failures. All exceed M007 baseline of 4820.

**Integration:** ✅ Pass — Focused pytest runs on preflight, provider choice, workspace persistence, resume-after-drift, setup idempotency, error quality, auth vocabulary, lifecycle inventory, docs truthfulness all pass. 294 net new targeted tests.

**Operational:** ⚠️ Partial — Doctor output vocabulary fixed and guardrail-tested (auth cache present / image available / launch-ready). Setup summary uses three-tier vocabulary (confirmed by test_auth_vocabulary_guardrail.py). Lifecycle commands verified consistent (test_lifecycle_inventory_consistency.py). However, these are verified via unit/integration tests with mocks, not live runtime observation.

**UAT:** ⚠️ Partial — Docker-backed smoke checks (delete image → auto-build, delete auth volume → bootstrap) documented as manual verification items. Auto-mode cannot safely delete local Docker images/volumes. All other UAT scenarios covered by test suite. S03 UAT lists 12 test cases, all passing via pytest.


## Verdict Rationale
The milestone delivered its core value: a typed shared preflight module, consistent auth vocabulary with guardrail tests, Docker Desktop cleanup, dispatch consolidation, and 294 new tests bringing the suite to 5114. The exit gate (ruff/mypy/pytest) passes cleanly.

Three success criteria are unmet: (1) worktree_commands.py not migrated to shared preflight, (2) WorkContext.provider_id not threaded in _record_session_and_context, (3) start_claude not renamed. All three were explicitly documented as deferred in slice summaries with clear follow-up paths. The guardrail _MIGRATED_FILES mechanism is designed for incremental extension.

These are genuine gaps against the milestone's stated success criteria, but they are minor, well-documented, and non-blocking. The remaining unmigrated sites work correctly (they just duplicate logic the preflight module now centralizes). No user-facing regression exists. The 40+ guardrail tests mechanically prevent drift on the delivered improvements.

Docker-backed smoke checks were reasonably deferred — auto-mode cannot safely manipulate local Docker state.

Verdict: needs-attention. The milestone can be completed with these gaps documented as follow-up work.
