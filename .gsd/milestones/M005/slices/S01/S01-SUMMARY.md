---
id: S01
parent: M005
milestone: M005
provides:
  - MAINTAINABILITY-AUDIT.md hotspot inventory with ranked split targets for S02 decomposition planning
  - 315 characterization + boundary tests as safety net before S02 surgery
  - GLOBAL-STATE-SUBPROCESS-DEFECTS.md priority repair queue for S04 subprocess hardening
  - Import boundary guard (test_import_boundaries.py) for ongoing enforcement
requires:
  []
affects:
  - S02
  - S03
  - S04
  - S05
key_files:
  - .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md
  - .gsd/milestones/M005/slices/S01/GLOBAL-STATE-SUBPROCESS-DEFECTS.md
  - tests/test_launch_flow_characterization.py
  - tests/test_dashboard_orchestrator_characterization.py
  - tests/test_docker_launch_characterization.py
  - tests/test_personal_profiles_characterization.py
  - tests/test_compute_effective_config_characterization.py
  - tests/test_app_dashboard_characterization.py
  - tests/test_marketplace_materialize_characterization.py
  - tests/test_setup_characterization.py
  - tests/test_team_commands_characterization.py
  - tests/test_worktree_use_cases_characterization.py
  - tests/test_wizard_characterization.py
  - tests/test_config_commands_characterization.py
  - tests/test_import_boundaries.py
key_decisions:
  - Skipped docker/credentials.py and ui/settings.py characterization: no extractable pure logic — need integration-level tests in S05
  - Audit items P14–P20 are code changes not characterization targets — routed to S02/S04 as defect repair work
  - Characterization tests target pure application-layer logic via mock adapters rather than full TUI interactions
patterns_established:
  - Characterization test pattern: mock adapters from tests/fakes/ to isolate pure application logic from infrastructure
  - Import boundary guard pattern: test_import_boundaries.py uses AST-based import scanning to enforce layer boundaries mechanically
  - Maintainability audit format: ranked hotspot tables with domain/layer-mixing/split-tag classification for planning input
  - Defect catalog format: categorized by type (mutable state, subprocess, silent swallow) with severity ratings and priority repair queue
observability_surfaces:
  - none
drill_down_paths:
  - .gsd/milestones/M005/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M005/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M005/slices/S01/tasks/T03-SUMMARY.md
  - .gsd/milestones/M005/slices/S01/tasks/T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-04T14:38:17.568Z
blocker_discovered: false
---

# S01: Maintainability baseline and refactor queue

**Established quantitative maintainability baseline (272-line audit, 153-line defect catalog) and 315 characterization + boundary tests protecting all top split targets before S02 surgery.**

## What Happened

S01 delivered three outputs that S02–S06 consume as planning inputs:

**1. Maintainability Audit (T01)** — MAINTAINABILITY-AUDIT.md is a 272-line ranked inventory covering: (a) 63 files >300 lines with domain classification and layer-mixing tags, identifying 3 HARD-FAIL (>1100 lines) and 12 MANDATORY-SPLIT (>800 lines) targets; (b) top-25 largest functions by AST analysis; (c) boundary violations across 5 violation types (application→docker, core→marketplace, docker→presentation, docker internal cycles, Claude-specific shapes); (d) robustness debt (except-Exception sites, unchecked subprocess calls, mutable module-level defaults, xfails, typing debt).

**2. Characterization Tests (T02 + T03)** — 315 tests across 13 files locking the current behavior of all high-priority split targets before S02 surgery begins. T02 created the initial 4 files (87 tests) for the top mandatory-split targets: launch/flow.py, dashboard/orchestrator.py, docker/launch.py, core/personal_profiles.py. T03 extended coverage with 8 more files (197 tests) plus updated the import boundary guard (31 tests). Final coverage spans: compute_effective_config (63 tests), app_dashboard (40 tests), dashboard orchestrator (26 tests), docker launch (27 tests), marketplace_materialize (24 tests), setup (19 tests), team_commands (17 tests), worktree_use_cases (16 tests), personal_profiles (17 tests), launch_flow (17 tests), wizard (10 tests), config_commands (8 tests), and import_boundaries (31 tests).

**3. Defect Catalog (T04)** — GLOBAL-STATE-SUBPROCESS-DEFECTS.md catalogs 63 defects across 3 categories: 24 global mutable state issues (3 singleton mutations, 7 module-level Console instances, 12 unfrozen config dicts, 1 lru_cache with Docker probe side effect), 19 subprocess handling defects (12 missing timeouts including 4 high-severity, 3 silently discarded returncodes, 4 missing FileNotFoundError guards), and 20 silent exception swallowing sites (13 bare pass swallows, 7 overly broad catches). Includes a priority repair queue with 5 immediate fixes and 7 next-batch items for S04 consumption.

No production source code was modified. All work is analysis artifacts and test files. The full suite (4079 passed, 23 skipped, 4 xfailed) passes cleanly with ruff and mypy clean.

## Verification

All slice-level verification gates passed:
- `uv run pytest --rootdir "$PWD" -q` → 4079 passed, 23 skipped, 4 xfailed (65.53s)
- `uv run ruff check` → All checks passed
- `uv run mypy src/scc_cli` → Success: no issues found in 261 source files
- `uv run pytest tests/test_*_characterization.py tests/test_import_boundaries.py -q` → 315 passed (3.07s)
- `test -f .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md` → exists (272 lines)
- `test -f .gsd/milestones/M005/slices/S01/GLOBAL-STATE-SUBPROCESS-DEFECTS.md` → exists (153 lines)

## Requirements Advanced

- R001 — Established quantitative baseline for maintainability with 272-line audit, 63-defect catalog, and 315 characterization tests; all downstream slices S02–S06 now have concrete ranked inputs for decomposition and hardening work.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

T03 skipped docker/credentials.py and ui/settings.py characterization — both are subprocess-heavy or TUI-coupled with no extractable pure logic to characterize. Items P14–P20 from the audit are boundary guards, robustness changes, or typing debt — not characterization targets. T04 deliverable is the catalog document rather than code changes, since it's analysis-only work.

## Known Limitations

Characterization tests cover pure application-layer logic and import boundaries but do not cover heavy TUI-coupled modules (ui/settings.py) or pure subprocess wrappers (docker/credentials.py). These modules will need different testing strategies (integration tests with container fixtures) in S02/S05.

## Follow-ups

S02 should consume the MAINTAINABILITY-AUDIT.md hotspot inventory and MANDATORY-SPLIT tags to prioritize module decomposition. S04 should consume GLOBAL-STATE-SUBPROCESS-DEFECTS.md priority repair queue for subprocess hardening and silent-swallow cleanup. S05 should use the characterization test baseline to measure coverage elevation.

## Files Created/Modified

- `.gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md` — 272-line ranked maintainability audit: 63 files >300 lines with domain/layer-mixing/split tags, top-25 functions, boundary violations, robustness debt
- `.gsd/milestones/M005/slices/S01/GLOBAL-STATE-SUBPROCESS-DEFECTS.md` — 153-line defect catalog: 24 mutable globals, 19 subprocess handling, 20 silent swallows with severity ratings and priority repair queue
- `tests/test_launch_flow_characterization.py` — 17 characterization tests for commands/launch/flow.py wizard state machine
- `tests/test_dashboard_orchestrator_characterization.py` — 26 characterization tests for ui/dashboard/orchestrator.py view building and event routing
- `tests/test_docker_launch_characterization.py` — 27 characterization tests for docker/launch.py safety-net policy chain and sandbox launch
- `tests/test_personal_profiles_characterization.py` — 17 characterization tests for core/personal_profiles.py CRUD and MCP merge
- `tests/test_compute_effective_config_characterization.py` — 63 characterization tests for application/compute_effective_config.py pattern matching and MCP filtering
- `tests/test_app_dashboard_characterization.py` — 40 characterization tests for application/dashboard.py view models and effect application
- `tests/test_marketplace_materialize_characterization.py` — 24 characterization tests for marketplace/materialize.py name validation and manifest I/O
- `tests/test_setup_characterization.py` — 19 characterization tests for setup.py config preview and proposed config assembly
- `tests/test_team_commands_characterization.py` — 17 characterization tests for commands/team.py plugin display and config validation
- `tests/test_worktree_use_cases_characterization.py` — 16 characterization tests for application/worktree/use_cases.py selection and shell resolution
- `tests/test_wizard_characterization.py` — 10 characterization tests for ui/wizard.py path normalization and answer factories
- `tests/test_config_commands_characterization.py` — 8 characterization tests for commands/config.py enforcement status and advisory warnings
- `tests/test_import_boundaries.py` — 31 import boundary guard tests enforcing layer separation mechanically via AST scanning
