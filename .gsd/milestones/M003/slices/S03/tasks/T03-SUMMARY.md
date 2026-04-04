---
id: T03
parent: S03
milestone: M003
key_files:
  - src/scc_cli/adapters/oci_sandbox_runtime.py
  - tests/test_oci_sandbox_runtime.py
  - tests/test_oci_egress_integration.py
key_decisions:
  - Proxy env vars injected as -e flags in docker create
  - Topology teardown in both stop() and remove() with None reset
  - collect_proxy_env() merged into proxy_env for enforced mode parity
  - _build_create_cmd accepts network_name and proxy_env as keyword-only params
duration: 
verification_result: passed
completed_at: 2026-04-04T09:54:01.011Z
blocker_discovered: false
---

# T03: Wire egress topology into OciSandboxRuntime with network-enforcement guardrails and 16 new tests

**Wire egress topology into OciSandboxRuntime with network-enforcement guardrails and 16 new tests**

## What Happened

Integrated NetworkTopologyManager into OciSandboxRuntime.run() for web-egress-enforced mode with proxy env injection, --network none for locked-down-web, backward-compatible open mode, topology teardown in stop()/remove(), and 16 new tests including a regression guardrail. For enforced mode, run() builds an egress plan, compiles Squid ACLs, creates topology, and passes the internal network name and proxy env to _build_create_cmd(). Host proxy env is merged via collect_proxy_env(). _teardown_topology() helper is called by both stop() and remove().

## Verification

All four verification gates pass: pytest on new tests (50 passed), ruff check (all clean), mypy (no issues in 248 files), full test suite (3402 passed, 23 skipped, 4 xfailed).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_oci_sandbox_runtime.py tests/test_oci_egress_integration.py -q` | 0 | ✅ pass | 1230ms |
| 2 | `uv run ruff check` | 0 | ✅ pass | 1000ms |
| 3 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 5000ms |
| 4 | `uv run pytest --rootdir "$PWD" -q` | 0 | ✅ pass | 54440ms |

## Deviations

Added 5th test to TestNetworkEnforcement for None/unset policy case. Added 4 extra topology teardown safety tests. Both additive.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/adapters/oci_sandbox_runtime.py`
- `tests/test_oci_sandbox_runtime.py`
- `tests/test_oci_egress_integration.py`
