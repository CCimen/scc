---
id: T03
parent: S04
milestone: M006-d622bc
key_files:
  - src/scc_cli/doctor/checks/environment.py
  - src/scc_cli/doctor/checks/__init__.py
  - src/scc_cli/doctor/core.py
  - tests/test_doctor_image_check.py
key_decisions:
  - WARNING severity for missing provider image — only needed for scc start, not general usage
  - Provider image check gated on docker_ok in run_doctor() — no point checking images if Docker is unreachable
  - Falls back to claude image ref for unknown/unset provider_id
duration: 
verification_result: passed
completed_at: 2026-04-05T01:15:11.295Z
blocker_discovered: false
---

# T03: Added check_provider_image() doctor check that detects missing provider agent images and returns exact docker build command as fix_commands

**Added check_provider_image() doctor check that detects missing provider agent images and returns exact docker build command as fix_commands**

## What Happened

Implemented check_provider_image() in environment.py following the existing check pattern (subprocess + CheckResult). The function resolves the active provider via config.get_selected_provider(), maps it to the image ref from image_contracts.py, runs docker image inspect, and returns a CheckResult with fix_commands containing the exact docker build -t <ref> images/scc-agent-<provider>/ invocation on failure. Added the check to both run_all_checks() and run_doctor() (gated behind docker_ok). Created 10 tests covering happy paths, error paths, fallback behavior, and integration with run_doctor.

## Verification

All four verification gates pass: (1) uv run pytest tests/test_doctor_image_check.py -v --no-cov — 10 passed, (2) uv run ruff check — clean, (3) uv run mypy — no issues, (4) uv run pytest --rootdir "$PWD" -q --no-cov — 4627 passed, 0 failures

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_doctor_image_check.py -v --no-cov` | 0 | ✅ pass | 60ms |
| 2 | `uv run ruff check src/scc_cli/doctor/checks/environment.py src/scc_cli/doctor/core.py` | 0 | ✅ pass | 500ms |
| 3 | `uv run mypy src/scc_cli/doctor/checks/environment.py src/scc_cli/doctor/core.py` | 0 | ✅ pass | 500ms |
| 4 | `uv run pytest --rootdir "$PWD" -q --no-cov` | 0 | ✅ pass | 63330ms |

## Deviations

Renamed _IMAGE_MAP to image_map inside function body to satisfy ruff N806.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/doctor/checks/environment.py`
- `src/scc_cli/doctor/checks/__init__.py`
- `src/scc_cli/doctor/core.py`
- `tests/test_doctor_image_check.py`
