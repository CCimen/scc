# S01: Provider resolution consistency across worktree create and wizard flow — UAT

**Milestone:** M008-g7jk8d
**Written:** 2026-04-06T12:54:59.321Z

## UAT: S01 — Provider resolution consistency across worktree create and wizard flow

### Preconditions
- SCC repo at scc-sync-1.7.3 with all S01 changes applied
- Python 3.10+, uv available
- No Docker required (all tests mock infrastructure)

### Test 1: Shared preflight module exists and exports correct API
**Steps:**
1. Run: `python -c "from scc_cli.commands.launch.preflight import resolve_launch_provider, collect_launch_readiness, ensure_launch_ready, allowed_provider_ids, LaunchReadiness, ImageStatus, AuthStatus, ProviderResolutionSource, ProviderNotReadyError; print('OK')"`
**Expected:** Prints "OK" — all public symbols importable.

### Test 2: Provider resolution in flow.py uses shared preflight
**Steps:**
1. Run: `rg '_resolve_provider|_allowed_provider_ids' src/scc_cli/commands/launch/flow.py`
**Expected:** No matches. Both private functions removed; flow.py imports from preflight.

2. Run: `rg 'from .preflight import resolve_launch_provider' src/scc_cli/commands/launch/flow.py`
**Expected:** Match found — flow.py imports resolve_launch_provider.

### Test 3: Provider resolution in flow_interactive.py uses shared preflight
**Steps:**
1. Run: `rg 'from .preflight import resolve_launch_provider' src/scc_cli/commands/launch/flow_interactive.py`
**Expected:** Match found — flow_interactive.py imports from shared preflight.

2. Run: `rg 'choose_start_provider' src/scc_cli/commands/launch/flow_interactive.py`
**Expected:** No matches. Direct calls to choose_start_provider removed.

### Test 4: Typed readiness model uses enums not strings/booleans
**Steps:**
1. Run: `rg 'class ImageStatus|class AuthStatus|class ProviderResolutionSource' src/scc_cli/commands/launch/preflight.py`
**Expected:** Three enum classes found.

2. Run: `rg '@dataclass\(frozen=True\)' src/scc_cli/commands/launch/preflight.py`
**Expected:** LaunchReadiness is a frozen dataclass.

### Test 5: Non-interactive mode raises typed error (not prompt)
**Steps:**
1. Run: `uv run pytest tests/test_launch_preflight.py -k 'non_interactive' -v`
**Expected:** All non-interactive tests pass, confirming ProviderNotReadyError is raised with user_message and suggested_action.

### Test 6: Characterization tests document all five launch sites
**Steps:**
1. Run: `uv run pytest tests/test_launch_preflight_characterization.py -v --co | grep 'test session'`
**Expected:** 43 test items collected across 8 test classes covering flow start, wizard flow, worktree create, handle_worktree_start, handle_session_resume, record_session_and_context, and non-interactive behaviors.

### Test 7: Structural guardrails prevent drift
**Steps:**
1. Run: `uv run pytest tests/test_launch_preflight_guardrail.py -v`
**Expected:** All 7 tests pass:
   - Anti-drift: no banned function calls in migrated files
   - Single-source: image refs and display names only in canonical locations
   - Architecture: preflight.py imports only types/errors from core/

### Test 8: D046 architecture guard — preflight stays command-layer
**Steps:**
1. Run: `uv run pytest tests/test_launch_preflight_guardrail.py -k 'architecture' -v`
**Expected:** Test verifies preflight.py has no top-level imports from core/ except types and errors.

### Test 9: Full test suite regression check
**Steps:**
1. Run: `uv run pytest -q`
**Expected:** 4993+ passed, 0 failures, 23 skipped, 2 xfailed.

### Test 10: Static analysis clean
**Steps:**
1. Run: `uv run ruff check`
**Expected:** All checks passed.

2. Run: `uv run mypy src/scc_cli`
**Expected:** Success: no issues found in 303 source files.

### Edge Cases

### Test 11: Guardrail catches if someone re-adds choose_start_provider to flow.py
**Steps:**
1. Temporarily add `choose_start_provider()` call to flow.py
2. Run: `uv run pytest tests/test_launch_preflight_guardrail.py::TestProviderResolutionAntiDrift -v`
**Expected:** Test fails, catching the regression.
3. Revert the change.

### Test 12: start_claude reference still exists (tracked debt)
**Steps:**
1. Run: `rg 'start_claude' src/scc_cli/commands/worktree/worktree_commands.py`
**Expected:** Matches found — this is tracked debt to be resolved in S02/S03.
