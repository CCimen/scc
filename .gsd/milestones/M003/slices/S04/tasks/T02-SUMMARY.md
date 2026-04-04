---
id: T02
parent: S04
milestone: M003
key_files:
  - src/scc_cli/ports/models.py
  - src/scc_cli/application/start_session.py
  - src/scc_cli/adapters/oci_sandbox_runtime.py
  - src/scc_cli/application/launch/preflight.py
  - tests/test_oci_egress_integration.py
  - tests/test_launch_preflight.py
key_decisions:
  - destination_sets field uses TYPE_CHECKING import to avoid circular dependency
  - Destination resolution in _build_sandbox_spec only for OCI backend
  - Enforced-mode preflight wraps resolve ValueError into LaunchPolicyBlockedError
duration: 
verification_result: passed
completed_at: 2026-04-04T10:21:30.534Z
blocker_discovered: false
---

# T02: Wired provider destination sets from SandboxSpec through OCI adapter egress plan and added enforced-mode preflight validation for unresolvable destinations

**Wired provider destination sets from SandboxSpec through OCI adapter egress plan and added enforced-mode preflight validation for unresolvable destinations**

## What Happened

Added destination_sets field to SandboxSpec, wired _build_sandbox_spec() to resolve provider destinations via the registry for OCI backends, threaded destination-derived allow rules into build_egress_plan() in OciSandboxRuntime.run(), and extended evaluate_launch_preflight() with enforced-mode destination resolvability validation. Added 7 new tests covering destination-aware egress plan construction and enforced-mode preflight edge cases. All 3426 tests pass, mypy clean, ruff clean.

## Verification

Ran targeted test suite (50 tests across 4 files), full test suite (3426 passed, 23 skipped, 4 xfailed), mypy (no issues in 249 files), and ruff check (all passed after import sort fix).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest --rootdir "$PWD" tests/test_oci_egress_integration.py tests/test_launch_preflight.py tests/test_start_session_image_routing.py tests/test_egress_policy.py -q` | 0 | ✅ pass | 820ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 5000ms |
| 3 | `uv run ruff check` | 0 | ✅ pass | 300ms |
| 4 | `uv run pytest --rootdir "$PWD" -q` | 0 | ✅ pass | 35940ms |

## Deviations

Used TYPE_CHECKING guard for DestinationSet import in models.py to avoid circular dependency. Added local import inside _build_sandbox_spec() for runtime type satisfaction.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/ports/models.py`
- `src/scc_cli/application/start_session.py`
- `src/scc_cli/adapters/oci_sandbox_runtime.py`
- `src/scc_cli/application/launch/preflight.py`
- `tests/test_oci_egress_integration.py`
- `tests/test_launch_preflight.py`
