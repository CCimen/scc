---
id: T01
parent: S01
milestone: M001
key_files:
  - .gsd/milestones/M001/M001-ROADMAP.md
  - .gsd/milestones/M001/slices/S01/S01-PLAN.md
  - .gsd/milestones/M001/slices/S01/tasks/T01-PLAN.md
key_decisions:
  - Plan M001 as four slices in risk order: baseline truth, vocabulary migration, characterization coverage, then typed contracts/error-audit alignment.
  - Treat the existing dirty worktree as part of the real starting state for M001 instead of assuming a clean baseline.
duration: 
verification_result: passed
completed_at: 2026-04-03T15:17:26.246Z
blocker_discovered: false
---

# T01: Planned M001 into executable slices and captured the real repo baseline, including the active dirty worktree and legacy-vocabulary hotspots.

**Planned M001 into executable slices and captured the real repo baseline, including the active dirty worktree and legacy-vocabulary hotspots.**

## What Happened

I converted the committed M001 roadmap into executable GSD slices and then inventoried the actual starting state of the synced repo. The inventory confirmed that active work is happening on branch gsd/scc-v1 inside scc-sync-1.7.3, but the working tree is already dirty with a substantial uncommitted refactor across runtime, launch, doctor, error, and test surfaces. I also mapped the main M001 hotspots and confirmed that the old network-policy vocabulary is still present in core enums, marketplace/schema types, config logic, examples, README copy, and multiple tests. That gives the next tasks a grounded baseline instead of a fictional clean tree.

## Verification

Ran the planned inventory commands to capture branch status, diff size, and M001 hotspots. All inventory commands succeeded and showed that the repo root is correct, the tree is dirty, and the legacy network-policy names still appear widely across active M001 surfaces.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `git status --short --branch` | 0 | ✅ pass | 25ms |
| 2 | `git diff --stat` | 0 | ✅ pass | 22ms |
| 3 | `rg -n "unrestricted|corp-proxy-only|isolated|AgentProvider|AgentLaunchSpec|RuntimeInfo|NetworkPolicyPlan|SafetyVerdict|AuditEvent" -S . --glob '!**/.venv/**'` | 0 | ✅ pass | 25ms |

## Deviations

None.

## Known Issues

The working tree already contains a large uncommitted refactor touching launch/runtime/error paths. Legacy network mode names remain widespread across code, schema, examples, docs, and tests. The shell has python3 available but not python on PATH.

## Files Created/Modified

- `.gsd/milestones/M001/M001-ROADMAP.md`
- `.gsd/milestones/M001/slices/S01/S01-PLAN.md`
- `.gsd/milestones/M001/slices/S01/tasks/T01-PLAN.md`
