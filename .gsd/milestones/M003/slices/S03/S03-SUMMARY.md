---
id: S03
parent: M003
milestone: M003
provides:
  - NetworkTopologyManager adapter for creating/tearing down enforced egress topology
  - build_egress_plan() and compile_squid_acl() pure functions for ACL generation
  - EgressTopologyInfo dataclass for topology metadata
  - OCI adapter network enforcement for all three NetworkPolicy modes
  - Squid proxy sidecar image definition (images/scc-egress-proxy/)
requires:
  - slice: S01
    provides: RuntimeProbe protocol and RuntimeInfo for runtime detection
  - slice: S02
    provides: OciSandboxRuntime adapter with _build_create_cmd and _run_docker patterns
affects:
  - S04
  - S05
key_files:
  - src/scc_cli/core/egress_policy.py
  - src/scc_cli/adapters/egress_topology.py
  - src/scc_cli/adapters/oci_sandbox_runtime.py
  - images/scc-egress-proxy/Dockerfile
  - images/scc-egress-proxy/squid.conf.template
  - images/scc-egress-proxy/entrypoint.sh
  - tests/test_egress_policy.py
  - tests/test_egress_topology.py
  - tests/test_oci_egress_integration.py
key_decisions:
  - D014: Enforced web-egress uses internal Docker network + dual-homed Squid proxy sidecar as hard enforcement boundary
  - Squid ACL uses numbered acl names (deny_1, allow_1) for deterministic output
  - IP literals and CIDRs use dst directive; hostnames use dstdomain directive
  - Local _run_docker helper in egress_topology.py avoids cross-adapter coupling with oci_sandbox_runtime.py
  - Proxy env vars injected as -e flags in docker create for enforced mode
  - Topology teardown in both stop() and remove() with None reset for safety
patterns_established:
  - Three-layer egress enforcement: pure policy (core/egress_policy.py) → infrastructure adapter (adapters/egress_topology.py) → runtime integration (adapters/oci_sandbox_runtime.py)
  - Dual-homed proxy sidecar pattern: proxy on both internal and bridge networks, agent on internal only
  - ACL injection via volume mount + entrypoint sed replacement between marker comments
  - Idempotent teardown pattern that catches both CalledProcessError and SandboxLaunchError
  - Guardrail test pattern: assert enforced mode never produces default network (prevents regression)
observability_surfaces:
  - Docker label scc.egress-proxy=true on proxy containers (filter via docker ps --filter label=scc.egress-proxy)
  - Docker network naming convention scc-egress-{session_id} (filter via docker network ls --filter name=scc-egress-)
  - SandboxLaunchError includes failing command and stderr for topology setup failures
drill_down_paths:
  - .gsd/milestones/M003/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M003/slices/S03/tasks/T02-SUMMARY.md
  - .gsd/milestones/M003/slices/S03/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-04T09:58:31.536Z
blocker_discovered: false
---

# S03: Enforced web-egress topology and proxy ACLs

**Built the enforced web-egress topology: pure egress policy and ACL compilation, Squid proxy sidecar image, Docker network topology manager, and full OCI adapter integration with 49 new tests across three layers.**

## What Happened

S03 delivers the hard enforcement boundary for web-egress network policy. The work was split into three layers — pure policy logic, infrastructure adapter, and runtime integration — each independently testable and composed at the OCI adapter level.

**T01 — Pure egress policy and ACL compilation (19 tests)**
Created `src/scc_cli/core/egress_policy.py` with two public functions. `build_egress_plan()` converts a `NetworkPolicy` mode plus optional destination sets and egress rules into a `NetworkPolicyPlan`. For `WEB_EGRESS_ENFORCED`, it produces default deny rules covering IP literals, loopback (127.0.0.0/8), private CIDRs (10/8, 172.16/12, 192.168/16), link-local (169.254/16), and the cloud metadata endpoint (169.254.169.254), followed by any explicit allow rules. For `LOCKED_DOWN_WEB`, it returns a deny-all plan. For `OPEN`, no rules and `enforced_by_runtime=False`. `compile_squid_acl()` converts the plan into valid Squid ACL config with numbered acl names, deny-before-allow ordering, and a terminal `http_access deny all` (enforced) or `http_access allow all` (open) directive. CIDRs and IPs use the `dst` directive; hostnames use `dstdomain`. All 19 tests pass covering mode behavior, rule composition, edge cases, and ACL invariants.

**T02 — Squid proxy sidecar image and NetworkTopologyManager (14 tests)**
Created the `images/scc-egress-proxy/` directory with a Dockerfile (Alpine 3.19 + Squid), `squid.conf.template` (with ACL injection markers, safe port defaults, stdout logging, no cache), and `entrypoint.sh` (injects volume-mounted ACL rules via sed replacement at startup). The `NetworkTopologyManager` adapter in `src/scc_cli/adapters/egress_topology.py` orchestrates four Docker commands in `setup()`: create an internal-only network, start the proxy container with ACL config volume-mounted, connect the proxy to the default bridge for dual-homing, and inspect the proxy for its internal IP. `teardown()` is fully idempotent, catching both CalledProcessError and SandboxLaunchError. A local `_run_docker` helper avoids coupling with `oci_sandbox_runtime.py` while following the same SandboxLaunchError wrapping pattern. The `EgressTopologyInfo` frozen dataclass carries network name, proxy container name, and proxy endpoint. 14 mocked subprocess tests cover happy path, teardown, and failure modes including partial-setup cleanup.

**T03 — OCI adapter integration and guardrails (16 tests)**
Wired the topology into `OciSandboxRuntime.run()`. For `web-egress-enforced`, `run()` builds an egress plan, compiles Squid ACLs, creates topology via `NetworkTopologyManager`, and passes the internal network name plus proxy env vars (`HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`) to `_build_create_cmd()`. Host proxy env is merged via `collect_proxy_env()` for parity with DockerSandboxRuntime. For `locked-down-web`, `_build_create_cmd()` adds `--network none`. For `open` or unset, behavior is unchanged (backward compatible). `_teardown_topology()` is called by both `stop()` and `remove()` with None-reset for safety. 16 new tests include a guardrail that prevents regression to the default bridge for enforced mode. Full suite passes: 3402 tests, 23 skipped, 4 xfailed.

The three-layer separation keeps security-critical ACL logic as pure functions (easy to audit), infrastructure management in a dedicated adapter (easy to mock), and orchestration in the existing runtime adapter (consistent with S02 patterns).

## Verification

All verification gates passed:
1. `uv run pytest tests/test_egress_policy.py tests/test_egress_topology.py tests/test_oci_sandbox_runtime.py tests/test_oci_egress_integration.py -q` → 83 passed
2. `uv run ruff check` → all clean
3. `uv run mypy src/scc_cli` → no issues in 248 source files
4. `test -f images/scc-egress-proxy/Dockerfile && test -f images/scc-egress-proxy/squid.conf.template && test -f images/scc-egress-proxy/entrypoint.sh` → all exist
5. `uv run pytest --rootdir "$PWD" -q` → 3402 passed, 23 skipped, 4 xfailed (full suite, no regressions)

## Requirements Advanced

- R001 — Egress enforcement split into three cohesive, independently testable layers (pure policy, infrastructure adapter, runtime integration) with 49 new tests. Each module has a single responsibility. The local _run_docker pattern avoids cross-adapter coupling.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Minor additive deviations only: T01 produced 19 tests (plan asked 12+), T02 produced 14 tests (plan asked 8+), T03 produced 16 tests (plan asked for fewer). All were additive coverage improvements, no plan changes required.

## Known Limitations

The Squid proxy sidecar image is defined but not yet built or published to any registry. S04 or operator workflow will need to build the image before enforced mode works end-to-end. The ACL compilation handles HTTP/HTTPS-focused egress only (per D008); raw TCP/UDP or non-HTTP protocols are not filtered by the proxy.

## Follow-ups

S04 needs to wire policy integration so that effective network policy from org/team config reaches the OCI adapter. The proxy image build step needs to be documented or automated (S05 docs scope). CONNECT method handling for HTTPS through the proxy is configured in squid.conf.template but not explicitly tested at the integration level.

## Files Created/Modified

- `src/scc_cli/core/egress_policy.py` — New: pure functions build_egress_plan() and compile_squid_acl() for network policy plan creation and Squid ACL compilation
- `src/scc_cli/adapters/egress_topology.py` — New: NetworkTopologyManager class and EgressTopologyInfo dataclass for Docker network topology orchestration
- `src/scc_cli/adapters/oci_sandbox_runtime.py` — Modified: integrated egress topology into run(), _build_create_cmd(), stop(), and remove() for all three network policy modes
- `images/scc-egress-proxy/Dockerfile` — New: Alpine 3.19 + Squid proxy sidecar image definition with healthcheck
- `images/scc-egress-proxy/squid.conf.template` — New: Squid config template with ACL injection markers, safe port defaults, stdout logging
- `images/scc-egress-proxy/entrypoint.sh` — New: entrypoint script that injects volume-mounted ACL rules via sed and runs squid in foreground
- `tests/test_egress_policy.py` — New: 19 tests for egress plan builder and ACL compiler covering all modes and edge cases
- `tests/test_egress_topology.py` — New: 14 mocked subprocess tests for NetworkTopologyManager setup, teardown, and failure modes
- `tests/test_oci_sandbox_runtime.py` — Modified: added TestNetworkEnforcement class with 5 tests for _build_create_cmd network policy handling
- `tests/test_oci_egress_integration.py` — New: 11 integration-level tests for OCI adapter egress topology wiring and guardrails
