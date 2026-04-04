---
id: S01
parent: M001
milestone: M001
provides:
  - A documented, green baseline for M001 work.
  - A confirmed canonical implementation root in both repo state and written guidance.
  - A scoped inventory of where legacy network vocabulary still needs migration.
requires:
  []
affects:
  - S02
  - S03
  - S04
key_files:
  - .gsd/milestones/M001/M001-ROADMAP.md
  - .gsd/milestones/M001/slices/S01/S01-PLAN.md
  - .gsd/milestones/M001/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M001/slices/S01/tasks/T03-SUMMARY.md
key_decisions:
  - Use the dirty but passing worktree as the real M001 starting baseline instead of assuming a clean repo.
  - Keep M001 slices in risk order: baseline truth, terminology migration, characterization coverage, then typed seam work.
  - Avoid unnecessary churn in guidance files when the repo root and written policy already align.
patterns_established:
  - Inventory the real working tree before planning refactors when the baseline may already be dirty.
  - Capture the full verification gate early and treat a passing baseline as a constraint for later slices.
  - Prefer guidance verification over gratuitous file churn when docs already match reality.
observability_surfaces:
  - Task summaries with explicit verification evidence for repo inventory and full gate status.
  - Structured milestone and slice plan artifacts under .gsd for downstream execution.
drill_down_paths:
  - .gsd/milestones/M001/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M001/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-03T15:20:53.650Z
blocker_discovered: false
---

# S01: Baseline truth and implementation-root freeze

**Established the real M001 baseline: one canonical repo root, a green verification gate, and a documented inventory of the dirty worktree and legacy-vocabulary hotspots.**

## What Happened

This slice converted the committed M001 roadmap into executable GSD plans and then established the actual starting state for the milestone. The repo inventory showed that active work is happening in scc-sync-1.7.3 on branch gsd/scc-v1, but the tree already contains a substantial uncommitted refactor across launch, runtime, doctor, errors, and tests. The hotspot search confirmed that the old network-policy vocabulary is still live across core enums, schemas, config logic, examples, docs, and tests. The key result from the slice was the full verification baseline: despite the dirty tree, ruff, mypy, and pytest all pass. Canonical-root guidance was then checked against the actual shell and git root and found to be already aligned, so no content edits were needed there.

## Verification

Verified the actual repo root, inventoried the working tree and M001 hotspots, and ran the full fixed verification gate successfully. The slice closes with command evidence for `git status`, `git diff --stat`, hotspot search, `pwd && git rev-parse --show-toplevel`, `uv run ruff check`, `uv run mypy src/scc_cli`, and `uv run pytest`.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

No code or doc content changes were required for canonical-root guidance because the existing written guidance already matched the actual repo state.

## Known Limitations

The working tree remains dirty with a substantial uncommitted refactor, so later slices still need to preserve the passing baseline carefully. Legacy network vocabulary remains widespread and is intentionally deferred to S02.

## Follow-ups

Watch the unrelated Docker sandbox warning emitted on stderr during one successful shell command; it may indicate startup noise that will matter later when improving diagnostics.

## Files Created/Modified

- `.gsd/milestones/M001/M001-ROADMAP.md` — Rendered structured milestone plan for M001 with slice-level execution order and verification contract.
- `.gsd/milestones/M001/slices/S01/S01-PLAN.md` — Rendered slice plan for baseline truth and implementation-root freeze.
- `.gsd/milestones/M001/slices/S01/tasks/T01-PLAN.md` — Captured the task plan for repo inventory and hotspot mapping.
- `.gsd/milestones/M001/slices/S01/tasks/T02-PLAN.md` — Captured the task plan for the full verification baseline.
- `.gsd/milestones/M001/slices/S01/tasks/T03-PLAN.md` — Captured the task plan for canonical-root guidance verification.
