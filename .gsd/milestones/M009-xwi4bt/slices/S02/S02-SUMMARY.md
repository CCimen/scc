---
id: S02
parent: M009-xwi4bt
milestone: M009-xwi4bt
provides:
  - Consistent three-tier readiness vocabulary across all setup surfaces
  - Provider preference hints in setup completion next-steps
requires:
  - slice: S01
    provides: Unified preflight path with consistent auth vocabulary
affects:
  []
key_files:
  - src/scc_cli/setup.py
key_decisions:
  - Reused existing _three_tier_status() helper in _render_provider_status rather than duplicating logic
patterns_established:
  - All setup readiness surfaces (onboarding panel and completion summary) use the single _three_tier_status() helper — no inline status logic
observability_surfaces:
  - none
drill_down_paths:
  - .gsd/milestones/M009-xwi4bt/slices/S02/tasks/T01-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-06T17:08:40.988Z
blocker_discovered: false
---

# S02: Setup three-tier consistency and final verification

**_render_provider_status now uses _three_tier_status() so both the onboarding status panel and the completion summary show identical four-state readiness vocabulary, plus provider preference hints in setup next-steps.**

## What Happened

This was a small, focused slice with a single task. The setup wizard's _render_provider_status() had inline two-tier logic ("auth cache present" / "sign-in needed") while show_setup_complete() already used the shared _three_tier_status() helper for four-state readiness display (launch-ready / auth cache present / image available / sign-in needed). T01 replaced the inline logic with a call to _three_tier_status(provider_id, state), making both surfaces consistent.

Additionally, the setup completion next-steps block now includes `scc provider show` and `scc provider set` hints so users know how to manage provider preferences immediately after setup.

## Verification

Exit gate fully green: `uv run ruff check` (0 issues), `uv run mypy src/scc_cli` (303 files, 0 issues), `uv run pytest -q` (5117 passed, 23 skipped, 2 xfailed). grep confirms _render_provider_status calls _three_tier_status at line 460, matching the same helper used by show_setup_complete at lines 390 and 396.

## Requirements Advanced

- R001 — Eliminated duplicated inline status logic in setup.py; both readiness surfaces now share one helper, reducing maintenance surface and inconsistency risk.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

None.

## Follow-ups

None.

## Files Created/Modified

- `src/scc_cli/setup.py` — Replaced inline two-tier status logic in _render_provider_status with _three_tier_status() call; added scc provider show/set hints to setup completion next-steps
