---
id: T01
parent: S02
milestone: M008-g7jk8d
key_files:
  - src/scc_cli/commands/launch/provider_choice.py
  - src/scc_cli/setup.py
  - src/scc_cli/doctor/checks/environment.py
  - tests/test_auth_vocabulary_guardrail.py
key_decisions:
  - 'sign-in incomplete' replaces 'not connected' in setup error panels
  - 'auth cache missing' replaces 'auth cache not ready' in doctor negative case
duration: 
verification_result: passed
completed_at: 2026-04-06T13:01:25.631Z
blocker_discovered: false
---

# T01: Fixed 6 misleading auth-status strings across provider_choice.py, setup.py, and doctor checks; added 5-test guardrail preventing vocabulary regression

**Fixed 6 misleading auth-status strings across provider_choice.py, setup.py, and doctor checks; added 5-test guardrail preventing vocabulary regression**

## What Happened

Audited four user-facing modules for auth/readiness vocabulary. Fixed 'connected'→'auth cache present' and 'sign-in required'→'sign-in needed' in provider_choice.py. Fixed 'ready'→'auth cache present' and 'not connected'→'sign-in needed' in setup.py summary display. Fixed 'not connected'→'sign-in incomplete' in setup.py error panel. Fixed 'auth cache not ready'→'auth cache missing' in doctor/checks/environment.py. auth_bootstrap.py was already truthful. Created tests/test_auth_vocabulary_guardrail.py with 5 tests using tokenize-based scanning for banned vocabulary terms.

## Verification

All 5 guardrail tests pass. All 59 provider choice/preflight tests pass. Full ruff check passes.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_auth_vocabulary_guardrail.py -v` | 0 | ✅ pass | 5500ms |
| 2 | `uv run ruff check` | 0 | ✅ pass | 4000ms |
| 3 | `uv run pytest tests/test_start_provider_choice.py tests/test_launch_preflight_guardrail.py tests/test_launch_preflight_characterization.py -v` | 0 | ✅ pass | 6100ms |

## Deviations

Also fixed 'auth cache not ready' → 'auth cache missing' in doctor checks (not in original plan but inconsistent). Fixed 'not connected' → 'sign-in incomplete' in setup error panel (discovered during audit).

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/commands/launch/provider_choice.py`
- `src/scc_cli/setup.py`
- `src/scc_cli/doctor/checks/environment.py`
- `tests/test_auth_vocabulary_guardrail.py`
