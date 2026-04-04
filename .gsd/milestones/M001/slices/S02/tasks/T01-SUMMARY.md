---
id: T01
parent: S02
milestone: M001
key_files:
  - .gsd/milestones/M001/slices/S02/S02-PLAN.md
  - .gsd/milestones/M001/slices/S02/tasks/T01-PLAN.md
  - src/scc_cli/core/enums.py
  - src/scc_cli/marketplace/schema.py
  - src/scc_cli/schemas/org-v1.schema.json
  - README.md
key_decisions:
  - Scope the S02 migration to actual network-policy surfaces and not unrelated English prose using the same words.
  - Handle the migration in this order: core enums and typed schema first, then config logic and diagnostics, then examples/docs, then tests.
duration: 
verification_result: passed
completed_at: 2026-04-03T15:21:45.436Z
blocker_discovered: false
---

# T01: Mapped the legacy network-policy vocabulary by surface type and defined a safe migration order for S02.

**Mapped the legacy network-policy vocabulary by surface type and defined a safe migration order for S02.**

## What Happened

I searched the repo for the legacy network-policy terms and classified the results by surface type to define a safe migration order. The inventory confirmed that the meaningful rename targets are concentrated in core enums, marketplace and JSON schema types, application/config diagnostics, README examples, example org configs, and a large test surface. It also exposed unrelated prose uses of 'isolated' and 'unrestricted' that are not network-policy names and should be left alone, such as comments about isolated worktrees or unrestricted plugin semantics. Based on that inventory, the migration order for S02 is now clear: update value-bearing contract surfaces first, then user-facing diagnostics/docs/examples, then fix tests to match.

## Verification

Ran a repo-wide search for the legacy network terms and classified each hit by surface type. The command completed successfully and produced a clear breakdown of where the network-policy rename must happen versus where plain-English wording should stay untouched.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rg -n "unrestricted|corp-proxy-only|isolated" . --glob '!**/.venv/**'` | 0 | ✅ pass | 27ms |

## Deviations

None.

## Known Issues

The legacy vocabulary appears across multiple surface types: core (3), application (3), schema/config (6), examples (24), docs/planning (4), tests (58), and a few unrelated prose uses under other paths that should not be renamed mechanically.

## Files Created/Modified

- `.gsd/milestones/M001/slices/S02/S02-PLAN.md`
- `.gsd/milestones/M001/slices/S02/tasks/T01-PLAN.md`
- `src/scc_cli/core/enums.py`
- `src/scc_cli/marketplace/schema.py`
- `src/scc_cli/schemas/org-v1.schema.json`
- `README.md`
