# S02: Decompose oversized modules and repair boundaries — UAT

**Milestone:** M005
**Written:** 2026-04-04T17:11:48.938Z

## UAT: S02 — Decompose oversized modules and repair boundaries

### Preconditions
- Working directory: `scc-sync-1.7.3`
- Python environment: `uv sync` completed
- Baseline: S01 characterization tests and boundary tests exist

---

### Test 1: No file exceeds 800 lines
**Steps:**
1. Run: `python3 -c "from pathlib import Path; over=[f'{f} ({len(f.read_text().splitlines())}L)' for f in sorted(Path('src/scc_cli').rglob('*.py')) if len(f.read_text().splitlines()) > 800]; print('PASS: all under 800' if not over else 'FAIL: ' + ', '.join(over))"`

**Expected:** Output is `PASS: all under 800`

---

### Test 2: Boundary violation — no docker.core.ContainerInfo in application layer
**Steps:**
1. Run: `grep -rn "from.*docker\.core.*import.*ContainerInfo" src/scc_cli/application/ 2>/dev/null; echo "exit: $?"`

**Expected:** No output lines before the exit code. Exit code is 1 (no matches).

---

### Test 3: Boundary violation — no marketplace.managed in core layer
**Steps:**
1. Run: `grep -rn "from.*marketplace\.managed.*import\|from.*marketplace.*import.*load_managed" src/scc_cli/core/ 2>/dev/null; echo "exit: $?"`

**Expected:** No output lines before the exit code. Exit code is 1 (no matches).

---

### Test 4: Boundary violation — no console.err_line in docker layer
**Steps:**
1. Run: `grep -rn "from.*console.*import.*err_line" src/scc_cli/docker/ 2>/dev/null; echo "exit: $?"`

**Expected:** No output lines before the exit code. Exit code is 1 (no matches).

---

### Test 5: All 315 characterization + boundary tests pass
**Steps:**
1. Run: `uv run pytest tests/test_*_characterization.py tests/test_import_boundaries.py -q`

**Expected:** `315 passed` with zero failures.

---

### Test 6: Full test suite passes (4079+ tests)
**Steps:**
1. Run: `uv run pytest --rootdir "$PWD" -q`

**Expected:** `4079 passed` (or more), zero failures. Skipped/xfailed are acceptable.

---

### Test 7: Ruff lint clean
**Steps:**
1. Run: `uv run ruff check`

**Expected:** `All checks passed!`

---

### Test 8: Mypy type check clean
**Steps:**
1. Run: `uv run mypy src/scc_cli`

**Expected:** `Success: no issues found in 284 source files` (or more).

---

### Test 9: Backward-compatible imports preserved
**Steps:**
1. Run: `python3 -c "from scc_cli.application.dashboard import DashboardTab, load_status_tab_data; print('dashboard OK')"`
2. Run: `python3 -c "from scc_cli.application.worktree.use_cases import WorktreeInfo, enter_worktree_shell; print('worktree OK')"`
3. Run: `python3 -c "from scc_cli.core.personal_profiles import merge_personal_settings; print('profiles OK')"`
4. Run: `python3 -c "from scc_cli.commands.launch.flow import interactive_start; print('flow OK')"`

**Expected:** All four print their OK messages without ImportError.

---

### Test 10: Extracted files exist and are non-trivial
**Steps:**
1. Run: `for f in dashboard_models dashboard_loaders; do wc -l src/scc_cli/application/$f.py; done`
2. Run: `for f in models operations; do wc -l src/scc_cli/application/worktree/$f.py; done`
3. Run: `wc -l src/scc_cli/core/personal_profiles_merge.py`
4. Run: `wc -l src/scc_cli/docker/sandbox.py`
5. Run: `wc -l src/scc_cli/marketplace/materialize_git.py`
6. Run: `for f in flow_interactive flow_session; do wc -l src/scc_cli/commands/launch/$f.py; done`
7. Run: `for f in team_validate team_info; do wc -l src/scc_cli/commands/$f.py; done`
8. Run: `for f in config_validate config_inspect; do wc -l src/scc_cli/commands/$f.py; done`
9. Run: `for f in orchestrator_handlers orchestrator_menus orchestrator_container_actions _dashboard_actions; do wc -l src/scc_cli/ui/dashboard/$f.py; done`
10. Run: `for f in settings_profile wizard_pickers git_interactive_ops; do wc -l src/scc_cli/ui/$f.py; done`
11. Run: `for f in setup_ui setup_config; do wc -l src/scc_cli/$f.py; done`

**Expected:** All files exist and have >50 lines (non-trivial extraction, not stubs).

---

### Edge Case: DI parameter in merge_personal_settings
**Steps:**
1. Run: `python3 -c "
from scc_cli.core.personal_profiles_merge import merge_personal_settings
import inspect
sig = inspect.signature(merge_personal_settings)
assert 'managed_state_loader' in sig.parameters, 'DI parameter missing'
print('DI parameter present:', sig.parameters['managed_state_loader'].annotation)
"`

**Expected:** Output confirms `managed_state_loader` parameter exists with `Callable` type annotation.
