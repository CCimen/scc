---
id: T02
parent: S03
milestone: M003
key_files:
  - src/scc_cli/adapters/egress_topology.py
  - tests/test_egress_topology.py
  - images/scc-egress-proxy/Dockerfile
  - images/scc-egress-proxy/squid.conf.template
  - images/scc-egress-proxy/entrypoint.sh
key_decisions:
  - Local _run_docker helper instead of importing from oci_sandbox_runtime to avoid cross-adapter coupling
  - Proxy IP extracted from specific internal network via docker inspect format template
  - ACL rules volume-mounted via temp file and injected by entrypoint.sh sed replacement between marker comments
  - Teardown catches both CalledProcessError and SandboxLaunchError for full idempotency
duration: 
verification_result: passed
completed_at: 2026-04-04T09:47:39.929Z
blocker_discovered: false
---

# T02: Created Squid proxy sidecar image definition, NetworkTopologyManager adapter for Docker egress topology, and EgressTopologyInfo dataclass with 14 mocked subprocess tests

**Created Squid proxy sidecar image definition, NetworkTopologyManager adapter for Docker egress topology, and EgressTopologyInfo dataclass with 14 mocked subprocess tests**

## What Happened

Created the Docker network topology management layer for enforced web-egress. The scc-egress-proxy image is defined as Alpine 3.19 + Squid with a config template containing ACL injection markers, an entrypoint script that injects volume-mounted ACL rules at startup and runs squid in foreground, and a healthcheck. NetworkTopologyManager orchestrates four Docker commands in setup(): create internal network, start proxy container with ACL volume mount, connect proxy to bridge for dual-homing, inspect proxy for internal IP. Teardown is fully idempotent. A local _run_docker helper follows the same SandboxLaunchError pattern as oci_sandbox_runtime without importing it. 14 tests cover happy path, teardown, and all specified failure modes.

## Verification

All slice-level verification checks pass: pytest tests/test_egress_topology.py (14 passed), ruff check clean, mypy clean, all three image files exist. T01 regression tests still pass (19 tests). Total 33 tests across both test files.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_egress_topology.py -q` | 0 | ✅ pass | 1090ms |
| 2 | `uv run ruff check src/scc_cli/adapters/egress_topology.py tests/test_egress_topology.py` | 0 | ✅ pass | 500ms |
| 3 | `uv run mypy src/scc_cli/adapters/egress_topology.py` | 0 | ✅ pass | 1000ms |
| 4 | `test -f images/scc-egress-proxy/Dockerfile && test -f images/scc-egress-proxy/squid.conf.template && test -f images/scc-egress-proxy/entrypoint.sh` | 0 | ✅ pass | 10ms |

## Deviations

Added 6 extra tests beyond the required 8 (14 total) for better coverage. Used specific docker inspect --format with named network instead of iterating all networks.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/adapters/egress_topology.py`
- `tests/test_egress_topology.py`
- `images/scc-egress-proxy/Dockerfile`
- `images/scc-egress-proxy/squid.conf.template`
- `images/scc-egress-proxy/entrypoint.sh`
