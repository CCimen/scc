# S01: Unify all launch paths on shared preflight and fix auth bootstrap gap — UAT

**Milestone:** M009-xwi4bt
**Written:** 2026-04-06T16:59:40.983Z

## UAT: Unify all launch paths on shared preflight and fix auth bootstrap gap

### Prerequisites
- SCC repo at M009/S01 completion point
- `uv sync` completed
- All tests passing: `uv run pytest -q`

### Test Case 1: Auth bootstrap is invoked when auth is missing (T01 core fix)

**Steps:**
1. Run `uv run pytest tests/test_launch_preflight.py::TestEnsureLaunchReady::test_interactive_auth_missing_calls_show_notice_and_bootstrap -v`
2. Verify the test passes — confirms bootstrap_auth() is called after show_notice() when auth_status is MISSING in interactive mode.

**Expected:** Test passes. The mock for bootstrap_auth() is called exactly once.

### Test Case 2: Auth bootstrap exception wrapping (T01 error handling)

**Steps:**
1. Run `uv run pytest tests/test_launch_preflight.py::TestEnsureLaunchReady::test_bootstrap_auth_failure_wraps_as_provider_not_ready -v`
2. Run `uv run pytest tests/test_launch_preflight.py::TestEnsureLaunchReady::test_bootstrap_auth_provider_not_ready_passes_through -v`

**Expected:** Both pass. Generic exceptions from bootstrap_auth() become ProviderNotReadyError. Already-typed ProviderNotReadyError passes through unchanged.

### Test Case 3: flow.py no longer uses inline image/auth calls (T02 migration)

**Steps:**
1. Run `grep -n 'ensure_provider_image\|ensure_provider_auth' src/scc_cli/commands/launch/flow.py`
2. Run `grep -n 'ensure_provider_image\|ensure_provider_auth' src/scc_cli/commands/launch/flow_interactive.py`

**Expected:** Both greps return empty — no matches. The inline calls have been replaced with shared preflight.

### Test Case 4: Anti-drift guardrail covers migrated files (T02 guardrail)

**Steps:**
1. Run `uv run pytest tests/test_launch_preflight_guardrail.py::TestProviderResolutionAntiDrift -v`

**Expected:** All 3 tests pass:
- `test_migrated_files_do_not_call_resolution_functions` — flow.py and flow_interactive.py don't call choose_start_provider or resolve_launch_provider_id
- `test_migrated_files_import_from_preflight` — both import from preflight module
- `test_preflight_is_sole_wrapper_of_choose_start_provider` — only preflight.py wraps choose_start_provider

### Test Case 5: auth_bootstrap.py is a deprecated redirect (T03 centralization)

**Steps:**
1. Run `grep -rn 'from.*auth_bootstrap' src/scc_cli/ --include='*.py' | grep -v __pycache__`
2. Verify that no results reference `ensure_provider_auth` from `auth_bootstrap` module (matches for `show_auth_bootstrap_panel` from `render` module are expected false positives)
3. Run `wc -l src/scc_cli/commands/launch/auth_bootstrap.py`

**Expected:** Step 1 returns only `render` module imports (show_auth_bootstrap_panel), not auth_bootstrap.ensure_provider_auth. Step 3 shows ~20 lines (thin redirect, not the original ~50 line implementation).

### Test Case 6: Resume path skips readiness (T02 ordering)

**Steps:**
1. Run `uv run pytest tests/test_start_codex_auth_bootstrap.py -v`

**Expected:** All 3 tests pass, including the test that verifies readiness is skipped when provider is already ready (no unnecessary readiness checks on resume).

### Test Case 7: Full suite regression check

**Steps:**
1. Run `uv run ruff check`
2. Run `uv run mypy src/scc_cli`
3. Run `uv run pytest -q`

**Expected:** ruff clean, mypy 303 files with 0 issues, 5117 passed / 23 skipped / 2 xfailed.

### Edge Cases

- **Non-interactive mode with missing auth:** ensure_launch_ready raises ProviderNotReadyError with actionable message (no bootstrap_auth call in non-interactive mode). Covered by `test_non_interactive_auth_missing_raises`.
- **Both image and auth missing:** ensure_launch_ready fixes image first, then auth. Covered by `test_both_missing_fixes_image_then_auth`.
- **Dry-run path:** Skips readiness check entirely (no image pull, no auth bootstrap). Covered by test_start_dryrun.py tests mocking the preflight path.
