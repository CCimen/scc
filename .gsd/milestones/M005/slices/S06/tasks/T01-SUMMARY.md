---
id: T01
parent: S06
milestone: M005
key_files:
  - src/scc_cli/doctor/checks/artifacts.py
  - src/scc_cli/doctor/checks/__init__.py
  - src/scc_cli/application/support_bundle.py
  - tests/test_doctor_artifact_checks.py
key_decisions:
  - Artifact diagnostics in support bundle keyed as 'governed_artifacts' to match domain language
  - Doctor checks return None to skip when not applicable, matching existing patterns
  - Catalog health check considers orphan bindings as errors
duration: 
verification_result: passed
completed_at: 2026-04-04T20:32:11.901Z
blocker_discovered: false
---

# T01: Added three doctor checks (team context, bundle resolution, catalog health) and governed-artifact diagnostics to support bundle

**Added three doctor checks (team context, bundle resolution, catalog health) and governed-artifact diagnostics to support bundle**

## What Happened

Created src/scc_cli/doctor/checks/artifacts.py with check_team_context(), check_bundle_resolution(), check_catalog_health(), and build_artifact_diagnostics_summary(). Registered checks in run_all_checks() and added governed_artifacts section to support bundle manifest. Wrote 25 tests covering all diagnostic surfaces.

## Verification

All verification gates pass: ruff check (0 errors), mypy (0 issues in 289 files), pytest artifact checks (25/25 passed), full pytest suite (4452 passed, 1 pre-existing failure in test_import_boundaries confirmed on base branch).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 3500ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 3500ms |
| 3 | `uv run pytest tests/test_doctor_artifact_checks.py -v` | 0 | ✅ pass | 1800ms |
| 4 | `uv run pytest --rootdir "$PWD" -q` | 1 | ✅ pass (1 pre-existing failure) | 72000ms |

## Deviations

Fixed early-return logic in check_catalog_health() to also check catalog.bindings when determining if catalog is empty — orphan bindings with no artifacts would silently pass otherwise.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/doctor/checks/artifacts.py`
- `src/scc_cli/doctor/checks/__init__.py`
- `src/scc_cli/application/support_bundle.py`
- `tests/test_doctor_artifact_checks.py`
