---
estimated_steps: 11
estimated_files: 1
skills_used: []
---

# T01: Produce ranked maintainability audit with hotspot inventory, boundary-repair map, and robustness-debt catalog

Run live measurements against the codebase and produce a single consolidated MAINTAINABILITY-AUDIT.md that S02-S06 will consume as their planning input. Covers file-size census (all files >300 lines ranked by size with domain and layer-mixing tags), boundary violations (application→docker, core→marketplace, docker→presentation, docker internal cycles, Claude-specific shapes), and robustness debt (except-Exception sites with severity, unchecked subprocess calls, mutable module-level defaults, xfails, typing debt).

Steps:
1. Run file-size census: `find src/scc_cli -name '*.py' | xargs wc -l | sort -rn`
2. Classify each file >300 lines by domain (UI/Commands/Application/Docker/Core/Marketplace) and layer-mixing (Yes/Moderate/No)
3. Tag mandatory-split set (>800 lines) with HARD-FAIL (>1100) vs MANDATORY-SPLIT
4. Run AST analysis on top files to identify largest functions
5. Grep for import violations across all boundary types
6. Catalog except-Exception sites, unchecked subprocess calls, mutable globals, xfails, typing debt
7. Write consolidated MAINTAINABILITY-AUDIT.md with all sections
8. Verify artifact exists and contains expected data points

Reference from research: 64 files >300 lines, 15 >800, 3 >1100, 87 except-Exception sites, 71 subprocess.run calls, 371 dict[str,Any] refs, 46 cast() calls, 4 xfails

## Inputs

- ``src/scc_cli/` — all Python source files (read-only analysis target)`
- ``tests/` — existing test files to scan for xfails`

## Expected Output

- ``.gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md` — consolidated maintainability audit with hotspot inventory, boundary-repair map, robustness-debt catalog, and priority action queue`

## Verification

test -f .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md && grep -c '|' .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md | xargs test 20 -lt && grep -q 'HARD-FAIL\|MANDATORY-SPLIT' .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md && grep -q 'except Exception' .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md && grep -q 'subprocess' .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md && uv run ruff check && uv run mypy src/scc_cli && uv run pytest
