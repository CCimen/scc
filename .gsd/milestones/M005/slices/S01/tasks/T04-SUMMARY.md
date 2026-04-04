---
id: T04
parent: S01
milestone: M005
key_files:
  - .gsd/milestones/M005/slices/S01/GLOBAL-STATE-SUBPROCESS-DEFECTS.md
key_decisions:
  - (none)
duration: 
verification_result: passed
completed_at: 2026-04-04T14:33:20.721Z
blocker_discovered: false
---

# T04: Cataloged 63 defects (24 mutable globals, 19 subprocess handling, 20 silent swallows) with severity ratings and priority repair queue for S02

**Cataloged 63 defects (24 mutable globals, 19 subprocess handling, 20 silent swallows) with severity ratings and priority repair queue for S02**

## What Happened

Systematically scanned all 161 Python source files under src/scc_cli/ using AST-based analysis and targeted grep. Identified 24 global mutable state issues (3 singleton mutations via global keyword, 7 module-level Console instances, 12 unfrozen config dicts, 1 lru_cache with Docker probe side effect), 19 subprocess handling defects (12 missing timeouts including 4 high-severity, 3 silently discarded returncodes, 4 missing FileNotFoundError guards), and 20 silent exception swallowing sites (13 bare pass swallows, 7 overly broad catches). Produced priority repair queue with 5 immediate fixes and 7 next-batch items.

## Verification

Catalog file exists with 63 defect entries covering all categories. All entries have severity ratings. ruff check, mypy, and pytest all pass (no code changes in this analysis task).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 67000ms |
| 3 | `uv run pytest` | 0 | ✅ pass | 65270ms |
| 4 | `test -f .gsd/milestones/M005/slices/S01/GLOBAL-STATE-SUBPROCESS-DEFECTS.md` | 0 | ✅ pass | 50ms |

## Deviations

None. Task plan listed src/scc_cli/**/*.py as expected output (the scan target) — deliverable is the catalog document since this is analysis-only.

## Known Issues

None.

## Files Created/Modified

- `.gsd/milestones/M005/slices/S01/GLOBAL-STATE-SUBPROCESS-DEFECTS.md`
