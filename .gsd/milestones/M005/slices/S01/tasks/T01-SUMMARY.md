---
id: T01
parent: S01
milestone: M005
key_files:
  - .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md
key_decisions:
  - Severity thresholds: >1100 lines = HARD-FAIL, >800 lines = MANDATORY-SPLIT, >300 lines = tracked
  - except-Exception severity classified by domain: docker/credentials/safety = HIGH, application/command = MEDIUM, cleanup/diagnostic = LOW
duration: 
verification_result: passed
completed_at: 2026-04-04T13:50:58.292Z
blocker_discovered: false
---

# T01: Produced ranked maintainability audit with 184 table rows covering 63 hotspot files, 15 boundary violations, 87 except-Exception sites, 71 unchecked subprocess calls, and top-20 action queue

**Produced ranked maintainability audit with 184 table rows covering 63 hotspot files, 15 boundary violations, 87 except-Exception sites, 71 unchecked subprocess calls, and top-20 action queue**

## What Happened

Ran live codebase scans against src/scc_cli/ (61,089 total lines) to produce MAINTAINABILITY-AUDIT.md. Section 1 found 3 HARD-FAIL files (>1100 lines) and 12 MANDATORY-SPLIT files (>800 lines), with AST analysis of the 25 largest functions (top: interactive_start at 534 lines). Section 2 mapped 4 docker-import violations, 1 critical core→marketplace dependency inversion, and ~20 hardcoded Claude paths in docker/credentials.py. Section 3 cataloged 87 bare except-Exception sites (11 HIGH), 71 subprocess.run calls with only 1 check=True and 1 timeout, 371 dict[str, Any] typing debt references, and 4 xfail markers. The Priority Queue ranks top-20 actions for S02–S06.

## Verification

Verified artifact exists, has 184 table rows (≥20 required), contains HARD-FAIL/MANDATORY-SPLIT tags and Priority Queue section. All slice verification commands pass: ruff check clean, mypy clean (261 files), pytest 3795 passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `test -f .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md` | 0 | ✅ pass | 50ms |
| 2 | `grep -c '^|' MAINTAINABILITY-AUDIT.md | xargs test 20 -le` | 0 | ✅ pass | 50ms |
| 3 | `uv run ruff check` | 0 | ✅ pass | 2000ms |
| 4 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 5000ms |
| 5 | `uv run pytest` | 0 | ✅ pass | 65000ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `.gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md`
