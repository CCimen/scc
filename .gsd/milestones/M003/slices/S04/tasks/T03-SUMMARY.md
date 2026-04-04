---
id: T03
parent: S04
milestone: M003
key_files:
  - src/scc_cli/doctor/checks/environment.py
  - src/scc_cli/doctor/checks/__init__.py
  - src/scc_cli/doctor/__init__.py
  - src/scc_cli/doctor/core.py
  - src/scc_cli/application/support_bundle.py
  - tests/test_doctor_checks.py
  - tests/test_support_bundle.py
key_decisions:
  - Runtime probe accessed via bootstrap.get_default_adapters() not direct adapter import, to respect import boundary enforcement
  - Effective egress section separates probe, config, and registry reads into independent try/except blocks so partial data survives failures
duration: 
verification_result: passed
completed_at: 2026-04-04T10:32:21.064Z
blocker_discovered: false
---

# T03: Added check_runtime_backend() doctor check and effective_egress support bundle section for runtime backend, network policy, and destination set diagnostics

**Added check_runtime_backend() doctor check and effective_egress support bundle section for runtime backend, network policy, and destination set diagnostics**

## What Happened

Added check_runtime_backend() to the doctor checks module — probes the Docker runtime via bootstrap.get_default_adapters().runtime_probe, reports preferred_backend (docker-sandbox/oci/unavailable), display_name, and version. Returns CheckResult with passed=True when daemon is reachable, warning severity when unreachable or on probe failure. Wired into run_all_checks(), run_doctor(), and doctor package exports.\n\nAdded effective_egress section to build_support_bundle_manifest() — includes runtime_backend (from probe), network_policy (from user config), and resolved_destination_sets (sorted names from PROVIDER_DESTINATION_SETS). Each subsection uses independent try/except so probe failures don't block config or registry reads.\n\nWrote 4 tests for check_runtime_backend() covering docker-sandbox, oci, daemon-unavailable, and probe-exception cases. Wrote 2 tests for effective_egress covering successful probe and probe-failure resilience. Updated existing TestRunAllChecks to mock the new check. Adapted direct adapter import to bootstrap route to respect import boundary enforcement.

## Verification

All verification commands pass: ruff check (0 issues), mypy src/scc_cli (0 issues in 249 files), pytest targeted (64 passed), pytest full suite (3432 passed, 0 failures).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 2000ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 8000ms |
| 3 | `uv run pytest --rootdir $PWD tests/test_doctor_checks.py tests/test_support_bundle.py -q` | 0 | ✅ pass (64 passed) | 2180ms |
| 4 | `uv run pytest --rootdir $PWD -q` | 0 | ✅ pass (3432 passed) | 37180ms |

## Deviations

Refactored from direct DockerRuntimeProbe adapter import to bootstrap.get_default_adapters().runtime_probe access to respect the import boundary test (test_only_bootstrap_imports_adapters). Architecturally cleaner than the plan's suggestion.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/doctor/checks/environment.py`
- `src/scc_cli/doctor/checks/__init__.py`
- `src/scc_cli/doctor/__init__.py`
- `src/scc_cli/doctor/core.py`
- `src/scc_cli/application/support_bundle.py`
- `tests/test_doctor_checks.py`
- `tests/test_support_bundle.py`
