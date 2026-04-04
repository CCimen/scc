---
id: T01
parent: S04
milestone: M004
key_files:
  - src/scc_cli/core/safety_policy_loader.py
  - src/scc_cli/doctor/checks/safety.py
  - src/scc_cli/doctor/checks/__init__.py
  - src/scc_cli/doctor/core.py
  - tests/test_safety_policy_loader.py
  - tests/test_safety_doctor_check.py
key_decisions:
  - Used raw config.load_cached_org_config() for doctor check — NormalizedOrgConfig strips safety_net
  - Added _load_raw_org_config() indirection for clean mock patching
  - Duplicated validation logic from docker.launch to preserve core→docker boundary
duration: 
verification_result: passed
completed_at: 2026-04-04T13:08:22.251Z
blocker_discovered: false
---

# T01: Added fail-closed typed SafetyPolicy loader in core, doctor safety-policy check, and 31 tests with import guardrail

**Added fail-closed typed SafetyPolicy loader in core, doctor safety-policy check, and 31 tests with import guardrail**

## What Happened

Created core/safety_policy_loader.py with load_safety_policy() that extracts security.safety_net from raw org config dicts and returns a typed SafetyPolicy. Fail-closed: any parse error produces default SafetyPolicy(action="block"). Created doctor/checks/safety.py with check_safety_policy() that probes org config and reports PASS/WARNING/ERROR. Registered the check in both checks/__init__.py and core.py. Wrote 24 loader tests (default fallbacks, valid passthrough, rules extraction, return-type invariants, tokenize-based import guardrail) and 7 doctor check tests (valid config, missing config, missing section, invalid action, exception).

## Verification

All 31 targeted tests pass. ruff check clean. mypy clean (259 files). grep confirms no docker imports in safety_policy_loader.py. Full suite: 3777 passed, 23 skipped, 4 xfailed — no regressions.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_safety_policy_loader.py tests/test_safety_doctor_check.py -v` | 0 | ✅ pass | 4500ms |
| 2 | `uv run ruff check` | 0 | ✅ pass | 4700ms |
| 3 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4700ms |
| 4 | `grep -r 'from scc_cli.docker' src/scc_cli/core/safety_policy_loader.py` | 1 | ✅ pass | 100ms |
| 5 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 46200ms |

## Deviations

Used _load_raw_org_config() private indirection for testability instead of function-body import. Added extra tests beyond plan: non-dict fallbacks, missing-action fallback, source field, parametrized return-type invariant.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/core/safety_policy_loader.py`
- `src/scc_cli/doctor/checks/safety.py`
- `src/scc_cli/doctor/checks/__init__.py`
- `src/scc_cli/doctor/core.py`
- `tests/test_safety_policy_loader.py`
- `tests/test_safety_doctor_check.py`
