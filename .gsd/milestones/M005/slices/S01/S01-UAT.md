# S01: Maintainability baseline and refactor queue — UAT

**Milestone:** M005
**Written:** 2026-04-04T14:38:17.568Z

## UAT: S01 — Maintainability baseline and refactor queue

### Preconditions
- Working directory: `scc-sync-1.7.3`
- Python environment: `uv sync` completed
- All prior milestones (M001–M004) passing

---

### TC-01: Maintainability audit artifact exists and is complete
**Steps:**
1. Verify file exists: `test -f .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md`
2. Verify it contains ranked hotspot tables: `grep -c '^|' .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md` → should be ≥20
3. Verify HARD-FAIL tags present: `grep -q 'HARD-FAIL' .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md`
4. Verify MANDATORY-SPLIT tags present: `grep -q 'MANDATORY-SPLIT' .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md`
5. Verify boundary violation section: `grep -q 'Boundary' .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md`
6. Verify robustness debt section: `grep -q 'except Exception\|subprocess\|typing' .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md`

**Expected:** All checks pass. Audit has 3 HARD-FAIL and 12 MANDATORY-SPLIT targets identified.

---

### TC-02: Defect catalog artifact exists and is actionable
**Steps:**
1. Verify file exists: `test -f .gsd/milestones/M005/slices/S01/GLOBAL-STATE-SUBPROCESS-DEFECTS.md`
2. Verify mutable globals section: `grep -q 'Global Mutable State' .gsd/milestones/M005/slices/S01/GLOBAL-STATE-SUBPROCESS-DEFECTS.md`
3. Verify subprocess section: `grep -q 'Subprocess' .gsd/milestones/M005/slices/S01/GLOBAL-STATE-SUBPROCESS-DEFECTS.md`
4. Verify silent swallow section: `grep -q 'Silent\|swallow' .gsd/milestones/M005/slices/S01/GLOBAL-STATE-SUBPROCESS-DEFECTS.md`
5. Verify severity ratings: `grep -q '🔴\|🟡\|🟢' .gsd/milestones/M005/slices/S01/GLOBAL-STATE-SUBPROCESS-DEFECTS.md`
6. Verify priority repair queue: `grep -q 'Priority\|Immediate\|Next' .gsd/milestones/M005/slices/S01/GLOBAL-STATE-SUBPROCESS-DEFECTS.md`

**Expected:** All checks pass. 63 defects cataloged with severity ratings and prioritized repair queue.

---

### TC-03: Characterization tests for top-4 mandatory-split targets pass
**Steps:**
1. Run: `uv run pytest tests/test_launch_flow_characterization.py tests/test_dashboard_orchestrator_characterization.py tests/test_docker_launch_characterization.py tests/test_personal_profiles_characterization.py -v`
2. Verify test count: ≥87 tests passing across the 4 files

**Expected:** All pass. These lock the behavior of the 4 highest-priority split targets (flow.py 1447 lines, orchestrator.py 1489 lines, docker/launch.py 874 lines, personal_profiles.py 839 lines).

---

### TC-04: Extended characterization tests for remaining split targets pass
**Steps:**
1. Run: `uv run pytest tests/test_compute_effective_config_characterization.py tests/test_app_dashboard_characterization.py tests/test_marketplace_materialize_characterization.py tests/test_setup_characterization.py tests/test_team_commands_characterization.py tests/test_worktree_use_cases_characterization.py tests/test_wizard_characterization.py tests/test_config_commands_characterization.py -v`
2. Verify test count: ≥197 tests passing across the 8 files

**Expected:** All pass. Coverage spans compute_effective_config, app_dashboard, marketplace_materialize, setup, team_commands, worktree_use_cases, wizard, config_commands.

---

### TC-05: Import boundary guard tests pass
**Steps:**
1. Run: `uv run pytest tests/test_import_boundaries.py -v`
2. Verify ≥31 boundary guard assertions

**Expected:** All pass. These mechanically enforce layer separation (e.g. core must not import from application, commands must not import adapters directly).

---

### TC-06: Full test suite regression check
**Steps:**
1. Run: `uv run pytest --rootdir "$PWD" -q`
2. Verify: ≥4079 passed, 0 failed
3. Run: `uv run ruff check`
4. Run: `uv run mypy src/scc_cli`

**Expected:** Full suite green. No regressions introduced by characterization tests. ruff and mypy clean.

---

### TC-07: No production source code modified
**Steps:**
1. Run: `git diff --name-only HEAD -- src/scc_cli/` (if available)
2. Verify characterization tests only import from production code, never modify it
3. Verify all new files are in `tests/` or `.gsd/milestones/M005/slices/S01/`

**Expected:** Zero production source files changed. All outputs are analysis artifacts or test files.

---

### Edge Cases

### EC-01: Characterization tests don't break when run in isolation
**Steps:**
1. Run each characterization test file individually: `uv run pytest tests/test_<name>_characterization.py -v` for each of the 12 files
2. Verify each file passes independently without order dependencies

**Expected:** Every file passes independently — no test-ordering or shared-state leakage.

### EC-02: Import boundary tests catch actual violations
**Steps:**
1. Examine `tests/test_import_boundaries.py` to verify it uses AST-based scanning (not string matching)
2. Verify it covers the boundary types from the audit: application→docker, core→marketplace, docker→presentation

**Expected:** Boundary tests use structural analysis and cover the key violation patterns identified in the audit.
