# S02: Auth/readiness wording truthfulness, Docker Desktop cleanup, and adapter dispatch consolidation — UAT

**Milestone:** M008-g7jk8d
**Written:** 2026-04-06T13:24:36.486Z

## UAT: S02 — Auth/readiness wording truthfulness, Docker Desktop cleanup, and adapter dispatch consolidation

### Preconditions
- scc-sync-1.7.3 repo checked out
- `uv sync` completed
- Python 3.10+ with uv available

### Test Case 1: Auth vocabulary consistency in provider choice
**Steps:**
1. Open `src/scc_cli/commands/launch/provider_choice.py`
2. Search for 'connected' (as standalone auth descriptor) — should not appear
3. Search for 'sign-in required' — should not appear
4. Verify 'auth cache present' appears for positive auth state
5. Verify 'sign-in needed' appears for negative auth state

**Expected:** No banned vocabulary. Three-tier terms used consistently.

### Test Case 2: Auth vocabulary consistency in setup summary
**Steps:**
1. Open `src/scc_cli/setup.py`
2. Search for standalone 'ready' meaning auth cache — should not appear
3. Search for 'not connected' — should not appear
4. Verify 'auth cache present' and 'sign-in needed'/'sign-in incomplete' appear

**Expected:** Setup summary uses three-tier vocabulary without implying full connectivity.

### Test Case 3: Auth vocabulary in doctor checks
**Steps:**
1. Open `src/scc_cli/doctor/checks/environment.py`
2. Search for 'auth cache not ready' — should not appear
3. Verify 'auth cache missing' is used for negative case

**Expected:** Doctor uses 'auth cache missing', not 'not ready'.

### Test Case 4: Docker Desktop removed from active commands
**Steps:**
1. Run: `rg 'Docker Desktop' src/scc_cli/commands/`
2. Should return no matches (exit code 1)

**Expected:** Zero Docker Desktop references in commands/ directory.

### Test Case 5: Docker Desktop confined to infrastructure layers
**Steps:**
1. Run: `rg -l 'Docker Desktop' src/scc_cli/`
2. Verify matches are only in: docker/core.py, docker/launch.py, docker/sandbox.py, adapters/docker_sandbox_runtime.py, adapters/docker_runtime_probe.py, core/errors.py, doctor/

**Expected:** Docker Desktop references exist only in infrastructure/adapter layers.

### Test Case 6: Branding consistency
**Steps:**
1. Run: `rg 'Sandboxed Cod' src/scc_cli/`
2. Every match should contain 'Sandboxed Coding CLI' (not 'Code CLI' or other variants)
3. Check init.py template content for 'Sandboxed Coding CLI'

**Expected:** Only 'Sandboxed Coding CLI' appears across all surfaces.

### Test Case 7: Shared adapter dispatch
**Steps:**
1. Open `src/scc_cli/commands/launch/dependencies.py`
2. Verify `get_agent_provider(adapters, provider_id)` function exists
3. Open `src/scc_cli/commands/launch/provider_choice.py` — verify no local adapters_by_provider dict
4. Open `src/scc_cli/setup.py` — verify no local provider_map dict
5. Both should call `get_agent_provider()` from dependencies

**Expected:** Single dispatch surface, no hardcoded per-site dicts.

### Test Case 8: Guardrail test suite
**Steps:**
1. Run: `uv run pytest tests/test_auth_vocabulary_guardrail.py tests/test_docs_truthfulness.py tests/test_lifecycle_inventory_consistency.py -v`
2. All tests should pass

**Expected:** 5 auth vocab + ~39 truthfulness + 7 lifecycle = ~51 guardrail tests, all green.

### Test Case 9: Full regression
**Steps:**
1. Run: `uv run pytest -q`
2. Should report >= 5008 passed, 0 failures

**Expected:** No regressions from S02 changes.

### Edge Cases
- **Test Case 10:** Verify `ruff check` passes (no lint issues from vocabulary/dispatch changes)
- **Test Case 11:** Verify `mypy src/scc_cli` passes (type safety maintained after dispatch refactor)
- **Test Case 12:** Verify prune_cmd uses image-based inventory (broader than label-based) for orphan cleanup — this is intentional per T02 decision
