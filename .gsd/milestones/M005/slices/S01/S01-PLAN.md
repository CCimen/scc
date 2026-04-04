# S01: Maintainability baseline and refactor queue

**Goal:** Hotspots, mandatory split targets, boundary leaks, guardrail gaps, and characterization-test needs are ranked and explicit in a single audit artifact, and the top split targets are protected by characterization tests before S02 surgery begins.
**Demo:** After this: TBD

## Tasks
- [x] **T01: Produced ranked maintainability audit with 184 table rows covering 63 hotspot files, 15 boundary violations, 87 except-Exception sites, 71 unchecked subprocess calls, and top-20 action queue** — Combine the hotspot inventory, boundary-repair map, and robustness-debt catalog into a single comprehensive audit artifact at `.gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md`. This artifact is the input for all S02-S06 planning.

The audit must contain three major sections:

**Section 1 — Ranked Hotspot Inventory:**
- Run `find src/scc_cli -name '*.py' | xargs wc -l | sort -rn` to get the live file-size census.
- Produce a ranked table of all files > 300 lines with columns: Rank, File (relative path), Lines, Domain cluster (commands/ui/application/docker/marketplace/core/other), Layer-mixing assessment (Yes/No + brief note).
- Tag each file > 800 lines as MANDATORY-SPLIT. Tag files > 1100 lines as HARD-FAIL.
- Include a top-10 largest functions table using AST analysis: `import ast; for each top file, parse and find functions > 150 lines`.

**Section 2 — Boundary-Repair Map:**
- Scan for docker imports outside adapter/runtime seams: `grep -rn 'from scc_cli.docker' src/scc_cli/ | grep -v 'adapters/' | grep -v 'docker/'`
- Scan for core-to-marketplace leakage: `grep -rn 'from scc_cli.marketplace' src/scc_cli/core/`
- Scan for presentation-to-runtime coupling: `grep -rn 'from.*console' src/scc_cli/docker/`
- Identify import cycles: check docker.core -> docker.launch and similar bidirectional imports.
- Catalog Claude-specific shapes in marketplace pipeline: files referencing `.claude`, `claude-plugins-official`, Claude-specific paths.
- Present all findings in a table with columns: Source file:line, Import target, Violation type, Severity.

**Section 3 — Robustness-Debt Catalog:**
- Count and list all `except Exception` sites: `grep -rn 'except Exception' src/scc_cli/` grouped by file with severity (HIGH for runtime/credential/docker ops, MEDIUM for application logic, LOW for cleanup/diagnostic).
- Count and list unchecked subprocess calls: `grep -rn 'subprocess.run' src/scc_cli/` — note which use `check=True`, which capture stderr, which set timeouts.
- Identify mutable module-level defaults: `grep -rn 'DEFAULT_\|_DEFAULTS\|DETECTION_ORDER\|INSTALL_COMMANDS\|BLOCK_MESSAGES\|_RULE_NAMES\|_NETWORK_POLICY' src/scc_cli/` — assess mutability risk.
- Count typing debt: `dict[str, Any]` references, `cast()` calls, `TypeAlias = dict` patterns.
- List existing quality xfails from test files with what each masks.

Constraints:
- Do NOT modify any production code.
- All numbers must come from live codebase scans, not copied from the research doc (though the research doc confirms what to expect).
- Use markdown tables for all structured data.
- End the document with a 'Priority Queue for S02-S06' section that ranks the top-20 action items across all three categories.
  - Estimate: 1h
  - Files: .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md
  - Verify: test -f .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md && grep -c '^|' .gsd/milestones/M005/slices/S01/MAINTAINABILITY-AUDIT.md | xargs test 20 -le
- [x] **T02: Added 87 characterization tests across 4 files covering top-4 mandatory-split targets as safety net before S02 surgery** — Write characterization tests that capture current behavior of the top-4 mandatory-split targets. These tests protect against accidental behavior changes when S02 decomposes these modules. The targets are:

1. **`commands/launch/flow.py`** — `interactive_start` (534 lines) and `start` (293 lines). Current tests are AST-level guardrails only. Write behavioral tests that verify:
   - `start()` returns early with appropriate error when no git repo is found
   - `start()` handles team override parameter correctly
   - `interactive_start()` delegates to resume helpers when resume context is provided
   - Test file: `tests/test_launch_flow_characterization.py`

2. **`ui/dashboard/orchestrator.py`** — `run_dashboard` (232 lines) and action handlers. Only 6% coverage. Write tests that verify:
   - `run_dashboard` handles empty session list gracefully
   - Dashboard action dispatch routes to correct handlers
   - Team switch flow is invoked when team switch is requested
   - Test file: `tests/test_dashboard_orchestrator_characterization.py`

3. **`docker/launch.py`** — `run_sandbox` (216 lines). 54% coverage. Write tests that verify:
   - Safety policy injection is applied to container config
   - Container name generation follows expected format
   - Failure branches (docker not available, image pull failure) produce correct errors
   - Test file: `tests/test_docker_launch_characterization.py`

4. **`core/personal_profiles.py`** — Only 7 tests for 839 lines. Write tests that verify:
   - Profile CRUD operations (create, read, update, delete)
   - Profile listing returns expected structure
   - Marketplace-state interaction (load/save managed state)
   - Edge cases: nonexistent profile, duplicate name, empty profile list
   - Test file: `tests/test_personal_profiles_characterization.py`

**Testing patterns to follow:**
- Use existing `tests/conftest.py` fixtures (`temp_dir`, `temp_git_repo`, `build_fake_adapters`)
- Use existing `tests/fakes/` for fake adapters where needed
- Use `unittest.mock.patch` for heavy external dependencies (docker, git, subprocess, filesystem)
- Use `from __future__ import annotations` in all new test files
- Each test function should have a docstring explaining what behavior it captures
- Mark any test that cannot be made fully deterministic with `pytest.mark.skip` and a note, rather than writing a flaky test

**Constraints:**
- Do NOT modify any production code.
- All tests must pass when run individually AND as part of the full suite.
- Tests must not make network calls, start containers, or access real filesystem paths outside temp dirs.
- Target: at least 3-5 meaningful behavioral tests per module (12-20 total new tests).
  - Estimate: 2h
  - Files: tests/test_launch_flow_characterization.py, tests/test_dashboard_orchestrator_characterization.py, tests/test_docker_launch_characterization.py, tests/test_personal_profiles_characterization.py
  - Verify: uv run pytest tests/test_launch_flow_characterization.py tests/test_dashboard_orchestrator_characterization.py tests/test_docker_launch_characterization.py tests/test_personal_profiles_characterization.py -v && uv run mypy src/scc_cli && uv run ruff check
- [ ] **T03: Add characterization tests for all high-priority split targets** — 
  - Files: tests/**, plus all source files listed above
  - Verify: uv run pytest passes; characterization coverage exists for all top-20 split targets with at least the current public API behavior locked
- [ ] **T04: Catalog global mutable state and subprocess handling defects** — 
  - Files: src/scc_cli/**/*.py
  - Verify: defect list covers all mutable globals, all unhandled subprocess sites, and all silent-swallow sites with severity ratings
