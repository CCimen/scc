---
id: T01
parent: S03
milestone: M007-cqttot
key_files:
  - src/scc_cli/core/errors.py
  - src/scc_cli/core/contracts.py
  - src/scc_cli/doctor/types.py
  - src/scc_cli/doctor/checks/environment.py
  - src/scc_cli/doctor/checks/__init__.py
  - tests/test_doctor_provider_errors.py
key_decisions:
  - Auth file names mapped per provider in local dict (claude → .credentials.json, codex → auth.json) with .credentials.json as fallback
  - Two-step Docker probe: volume inspect then docker run alpine test -f to avoid permission issues
duration: 
verification_result: passed
completed_at: 2026-04-05T13:17:56.803Z
blocker_discovered: false
---

# T01: Added ProviderNotReadyError, ProviderImageMissingError, AuthReadiness dataclass, CheckResult.category field, and check_provider_auth() with 23 passing tests

**Added ProviderNotReadyError, ProviderImageMissingError, AuthReadiness dataclass, CheckResult.category field, and check_provider_auth() with 23 passing tests**

## What Happened

Added two typed provider errors following the InvalidProviderError pattern, AuthReadiness frozen dataclass for auth credential status, category field on CheckResult for doctor output grouping, and check_provider_auth() that probes Docker volumes for provider auth files. All 23 new tests pass, mypy and ruff clean, full suite passes with 4698 tests.

## Verification

uv run pytest tests/test_doctor_provider_errors.py -v → 23 passed. uv run mypy on all 4 modified source files → no issues. uv run ruff check → all passed. Full test suite → 4698 passed, 0 failures.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_doctor_provider_errors.py -v` | 0 | ✅ pass | 9600ms |
| 2 | `uv run mypy src/scc_cli/core/errors.py src/scc_cli/core/contracts.py src/scc_cli/doctor/types.py src/scc_cli/doctor/checks/environment.py` | 0 | ✅ pass | 5000ms |
| 3 | `uv run ruff check src/scc_cli/core/errors.py src/scc_cli/core/contracts.py src/scc_cli/doctor/types.py src/scc_cli/doctor/checks/environment.py` | 0 | ✅ pass | 4100ms |
| 4 | `uv run pytest --no-header -q` | 0 | ✅ pass | 53200ms |

## Deviations

Renamed local variable _AUTH_FILES to auth_files to satisfy ruff N806. No behavioral change.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/core/errors.py`
- `src/scc_cli/core/contracts.py`
- `src/scc_cli/doctor/types.py`
- `src/scc_cli/doctor/checks/environment.py`
- `src/scc_cli/doctor/checks/__init__.py`
- `tests/test_doctor_provider_errors.py`
