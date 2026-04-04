# S01: Maintainability baseline and refactor queue

**Goal:** Establish a quantitative maintainability baseline (hotspot inventory, boundary-repair map, robustness-debt catalog) and protect the top split targets with characterization tests before S02 surgery begins.
**Demo:** After this: TBD

## Tasks
- [x] **T01: Produce ranked maintainability audit with hotspot inventory, boundary-repair map, and robustness-debt catalog** — Run live measurements against the codebase and produce a single consolidated MAINTAINABILITY-AUDIT.md that S02-S06 will consume as their planning input. Covers file-size census (all files >300 lines ranked by size with domain and layer-mixing tags), boundary violations (application→docker, core→marketplace, docker→presentation, docker internal cycles, Claude-specific shapes), and robustness debt (except-Exception sites with severity, unchecked subprocess calls, mutable module-level defaults, xfails, typing debt).

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
  - Estimate: 45m
  - Files: .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md
  - Verify: test -f .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md && grep -c '|' .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md | xargs test 20 -lt && grep -q 'HARD-FAIL\|MANDATORY-SPLIT' .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md && grep -q 'except Exception' .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md && grep -q 'subprocess' .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md && uv run ruff check && uv run mypy src/scc_cli && uv run pytest
- [x] **T02: Write characterization tests for top-4 mandatory-split targets before S02 surgery** — Add behavioral characterization tests for the four highest-priority split targets identified in T01's audit. These tests protect existing behavior before S02 surgery decomposes these modules. docker/launch.py already has existing tests in test_docker_launch_characterization.py — extend coverage there rather than duplicating.

Targets and approach:
1. `commands/launch/flow.py` (1447 lines) — Create `tests/test_launch_flow_characterization.py` targeting wizard state machine logic, session selection, CLI error paths. Use mock adapters from tests/fakes/.
2. `ui/dashboard/orchestrator.py` (1489 lines) — Create `tests/test_dashboard_orchestrator_characterization.py` targeting view building, event routing, effect result application, tab fallbacks, placeholder helpers.
3. `docker/launch.py` (874 lines) — Extend `tests/test_docker_launch_characterization.py` with safety-net policy chain, atomic file writing, run_sandbox failure branches, mount race detection.
4. `core/personal_profiles.py` (839 lines) — Create `tests/test_personal_profiles_characterization.py` targeting CRUD operations, listing edge cases, MCP merge, applied-state tracking.

Also create `tests/test_import_boundaries.py` to codify the boundary violations identified in T01 as test assertions.

Key constraints:
- Tests target pure application-layer logic rather than mocking full TUI interactions
- Use existing fakes/fixtures from tests/conftest.py and tests/fakes/
- No production source code modified
- Allowlist new test files in boundary guard with M005/S01/T02 tracking comment
  - Estimate: 1h30m
  - Files: tests/test_launch_flow_characterization.py, tests/test_dashboard_orchestrator_characterization.py, tests/test_docker_launch_characterization.py, tests/test_personal_profiles_characterization.py, tests/test_import_boundaries.py
  - Verify: uv run pytest tests/test_launch_flow_characterization.py tests/test_dashboard_orchestrator_characterization.py tests/test_docker_launch_characterization.py tests/test_personal_profiles_characterization.py tests/test_import_boundaries.py -v && uv run pytest && uv run mypy src/scc_cli && uv run ruff check
- [x] **T03: Added 197 characterization tests across 8 new files covering all testable top-20 split targets as safety net before S02 surgery** — 
  - Files: tests/**, plus all source files listed above
  - Verify: uv run pytest passes; characterization coverage exists for all top-20 split targets with at least the current public API behavior locked
- [x] **T04: Cataloged 63 defects (24 mutable globals, 19 subprocess handling, 20 silent swallows) with severity ratings and priority repair queue for S02** — 
  - Files: src/scc_cli/**/*.py
  - Verify: defect list covers all mutable globals, all unhandled subprocess sites, and all silent-swallow sites with severity ratings
