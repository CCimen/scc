---
id: M004
title: "Cross-Agent Runtime Safety"
status: complete
completed_at: 2026-04-04T13:38:04.270Z
key_decisions:
  - D016: Keep SafetyPolicy.rules as dict[str, Any] with standalone mapping function for fail-closed semantics
  - Core safety modules are pure functions with no I/O — engine orchestrates, rules analyze
  - Provider safety adapters contain zero verdict logic — engine is the single source of truth
  - Standalone evaluator is a stdlib-only fork with sync-guardrail, not a shared package
  - Shell wrappers use absolute REAL_BIN paths to prevent self-recursion
  - Fail-closed policy loader: any parse failure returns default-block policy
  - Doctor check uses raw org config (NormalizedOrgConfig strips safety_net)
  - Safety audit reader reuses bounded tail-read from launch audit
  - README positions safety engine as 'built-in' with plugin as 'additional coverage'
  - Runtime wrappers described as 'defense-in-depth' — topology+proxy remain the hard control
key_files:
  - src/scc_cli/core/safety_engine.py
  - src/scc_cli/core/shell_tokenizer.py
  - src/scc_cli/core/git_safety_rules.py
  - src/scc_cli/core/network_tool_rules.py
  - src/scc_cli/core/contracts.py
  - src/scc_cli/core/safety_policy_loader.py
  - src/scc_cli/ports/safety_engine.py
  - src/scc_cli/ports/safety_adapter.py
  - src/scc_cli/adapters/claude_safety_adapter.py
  - src/scc_cli/adapters/codex_safety_adapter.py
  - src/scc_cli/doctor/checks/safety.py
  - src/scc_cli/application/safety_audit.py
  - src/scc_cli/commands/support.py
  - images/scc-base/wrappers/scc_safety_eval/
  - images/scc-base/wrappers/bin/
  - tests/test_docs_truthfulness.py
  - tests/test_safety_engine_boundary.py
  - tests/test_safety_eval_sync.py
  - README.md
lessons_learned:
  - Lift-from-plugin pattern works well: copy verbatim, adapt return types, use adapted tests as characterization tests
  - Sync-guardrail tests (normalize imports + diff) are a cheap reliable way to keep forked modules in sync
  - The 4-touch-point wiring pattern (adapter file, bootstrap, fakes, inline constructions) scales well to new protocols like SafetyAdapter
  - File-existence guardrail tests add structural protection beyond behavioral tests
  - Milestone-level success criteria should be formally populated during planning, not compensated at validation time
---

# M004: Cross-Agent Runtime Safety

**Delivered a shared SCC-owned safety engine with typed verdicts, runtime wrappers for 7 tools, provider UX/audit adapters for Claude and Codex, fail-closed policy loading, operator diagnostics, and truthful documentation — all verified by 69 net new tests.**

## What Happened

M004 turned the safety direction into a real shared enforcement plane. The result is one SCC-owned safety baseline that both Claude and Codex providers consume, with provider-native integrations acting only as UX and audit helpers.

**S01 — Shared safety policy and verdict engine.** Lifted battle-tested parsing logic from the scc-safety-net plugin into core, adapted return types to typed SafetyVerdict contracts, and built DefaultSafetyEngine as the single orchestrator. The engine tokenizes commands, routes by family (git vs network tools), applies per-rule policy overrides, and fails closed on missing keys. All rule modules are pure functions with no I/O. A boundary guardrail test prevents plugin/provider imports from leaking into core safety.

**S02 — Runtime wrapper baseline in scc-base.** Created a standalone stdlib-only evaluator package (scc_safety_eval) for container image builds, plus 7 shell wrappers (git, curl, wget, ssh, scp, sftp, rsync) that intercept commands via PATH-first placement. Contract tests prove evaluator↔engine verdict equivalence. A sync-guardrail test catches drift between core and the standalone copy.

**S03 — Claude and Codex UX/audit adapters.** Built SafetyAdapter protocol and two implementations that wrap the shared engine with provider-specific UX formatting and structured AuditEvent emission. Adapters contain zero verdict logic — they are pure UX/audit wrappers. Blocked commands emit WARNING-severity events; allowed commands emit INFO.

**S04 — Fail-closed policy loading, audit surfaces, and operator diagnostics.** Created a typed SafetyPolicy loader that extracts policy from raw org config and falls back to default-block on any failure. Added a doctor safety-policy check, a bounded safety-audit reader over the canonical JSONL sink, an `scc support safety-audit` CLI command, and a support bundle safety section.

**S05 — Verification, docs truthfulness, and milestone closeout.** Updated README to truthfully reflect all M004 deliverables. Added 5 guardrail tests preventing safety documentation regression. Full exit gate: 3795 passed, ruff clean, mypy clean.

## Success Criteria Results

All success criteria met at the slice level (milestone-level criteria populated during validation):

- ✅ Shared safety engine with typed verdicts (S01)
- ✅ Runtime wrappers for 7 tools in scc-base (S02)
- ✅ Provider UX/audit adapters for Claude and Codex (S03)
- ✅ Fail-closed policy loading and truthful diagnostics (S04)
- ✅ Truthful documentation and guardrail tests (S05)
- ✅ Full exit gate: 3795 passed, 23 skipped, 4 xfailed, ruff clean, mypy clean (261 files)

## Definition of Done Results

- ✅ `uv run ruff check` — All checks passed
- ✅ `uv run mypy src/scc_cli` — Success: no issues found in 261 source files
- ✅ `uv run pytest --rootdir "$PWD" -q` — 3795 passed, 23 skipped, 4 xfailed
- ✅ No stale safety claims in README (10 guardrail tests confirm)
- ✅ Core safety modules have no forbidden imports (boundary guardrail test)
- ✅ Evaluator↔engine verdicts are equivalent (contract tests)
- ✅ Core↔evaluator code hasn't drifted (sync-guardrail tests)

## Requirement Outcomes

### R001 — Maintainability (validated → still validated)
Advanced by all 5 slices. Key evidence:
- Pure-function rule modules with no I/O (S01)
- Sync-guardrail test preventing core↔evaluator drift (S02)
- Provider adapters with zero verdict logic — clear separation of concerns (S03)
- Reused established patterns for policy loading, doctor checks, audit readers (S04)
- 10 docs truthfulness guardrail tests preventing documentation regression (S05)

No requirements invalidated or re-scoped.

## Deviations

None.

## Follow-ups

None.
