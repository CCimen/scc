# S03 — Research: Enforced Web-Egress Topology and Proxy ACLs

**Date:** 2026-04-04

## Summary

S03 must deliver the enforced web-egress topology described in Spec 04 and the PLAN: when `network_policy` is `web-egress-enforced`, the agent container must sit on an **internal-only** Docker network with no external connectivity, and a proxy sidecar must be the **only** component bridging internal and external networks. Proxy ACLs must evaluate both requested host and resolved IP/CIDR, denying IP literals, loopback, private, link-local, and metadata endpoints by default.

Today, **none of this exists.** The current codebase has:
- A `NetworkPolicy` enum with three modes (`open`, `web-egress-enforced`, `locked-down-web`).
- Policy computation that decides which mode applies (org → team → project merge in `compute_effective_config.py`).
- A `collect_proxy_env()` helper that forwards `HTTP_PROXY`/`HTTPS_PROXY`/`NO_PROXY` from the host into the container env.
- The `DockerSandboxRuntime` adapter calls `collect_proxy_env()` when `WEB_EGRESS_ENFORCED`, but only sets env vars — there is **no network isolation**, **no proxy sidecar**, **no ACL enforcement**.
- The `OciSandboxRuntime` adapter does not reference `network_policy` at all — it creates containers on the default bridge network with full internet access.
- `NetworkPolicyPlan`, `EgressRule`, and `DestinationSet` are defined as typed contracts in `core/contracts.py` but are **not consumed** anywhere in the codebase.

The work splits naturally into: (1) Docker network topology management (create internal network, attach containers), (2) proxy sidecar image and container lifecycle, (3) proxy ACL configuration that translates `NetworkPolicyPlan` → proxy rules, and (4) OCI adapter integration so `run()` enforces the topology when the spec says `web-egress-enforced`.

## Recommendation

**Build a typed `EgressTopology` adapter** that manages Docker network + proxy sidecar lifecycle, then integrate it into `OciSandboxRuntime.run()`. The Docker Desktop path (`DockerSandboxRuntime`) should remain untouched — Desktop's own sandbox networking is a separate enforcement mechanism. The OCI path is where SCC must enforce topology.

Approach:
1. Create an `scc-egress-proxy` image (Dockerfile + squid config) that runs a forward HTTP/HTTPS proxy with configurable ACL rules.
2. Create a `NetworkTopologyManager` (or similar) module in `src/scc_cli/adapters/` that can: create a named internal Docker network, start the proxy sidecar on that network + the default bridge, and return the network name + proxy endpoint for the agent container.
3. Extend `OciSandboxRuntime._build_create_cmd()` to attach the agent container to the internal-only network (via `--network`) and inject `HTTP_PROXY`/`HTTPS_PROXY` env vars pointing at the proxy sidecar.
4. Build an ACL compiler that converts `NetworkPolicyPlan.egress_rules` + `DestinationSet` entries into proxy-native config (squid ACL format or equivalent).
5. For `locked-down-web`, the agent container gets `--network=none` — no proxy, no connectivity at all.
6. Wire `SandboxSpec.network_policy` into the OCI adapter flow.

Use **Squid** as the proxy — it's mature, widely available as an Alpine package, supports HTTPS CONNECT tunneling without TLS interception, and has a well-understood ACL language for host + IP/CIDR matching. V1 scope is HTTP/HTTPS only (per PLAN), which Squid handles natively.

## Implementation Landscape

### Key Files

- `src/scc_cli/core/contracts.py` — Contains `NetworkPolicyPlan`, `EgressRule`, `DestinationSet` (already defined, not yet consumed). These are the input contracts for ACL compilation.
- `src/scc_cli/core/network_policy.py` — Contains `collect_proxy_env()` and policy rank helpers. Natural home for the ACL compiler (or a new `core/egress_policy.py`).
- `src/scc_cli/core/enums.py` — `NetworkPolicy` enum with the three modes.
- `src/scc_cli/adapters/oci_sandbox_runtime.py` — The primary integration point. `_build_create_cmd()` must add `--network <internal>` and proxy env. New lifecycle hooks for network/proxy setup and teardown.
- `src/scc_cli/adapters/docker_sandbox_runtime.py` — Should NOT be changed for topology (Desktop sandbox has its own isolation). But should get `network_policy` awareness for proxy env parity with the OCI path (it already has this partially).
- `src/scc_cli/ports/models.py` — `SandboxSpec` already has `network_policy: str | None`. This is the spec-level input.
- `src/scc_cli/application/start_session.py` — Already passes `network_policy` into `SandboxSpec`. May need to also build and pass `NetworkPolicyPlan` from `EffectiveConfig`.
- `images/scc-base/Dockerfile` — Existing base image. No change needed.
- `images/scc-agent-claude/Dockerfile` — Existing agent image. No change needed.
- `images/scc-egress-proxy/` — **New.** Squid-based proxy image with ACL-driven config.

### Build Order

**Phase 1 — Typed egress plan builder (pure logic, no Docker).** Build a function `build_egress_plan(network_policy, destination_sets, egress_rules) -> NetworkPolicyPlan` that populates the already-defined `NetworkPolicyPlan` contract. Add an ACL compiler `compile_squid_acl(plan: NetworkPolicyPlan) -> str` that produces a squid.conf snippet. Test this purely — no subprocess, no Docker. This is the riskiest piece conceptually (ACL correctness) and should be proven first.

**Phase 2 — Proxy sidecar image and network topology manager.** Create `images/scc-egress-proxy/Dockerfile` (Alpine + Squid) and `images/scc-egress-proxy/squid.conf.template`. Create `src/scc_cli/adapters/egress_topology.py` with a `NetworkTopologyManager` class that can: create an internal Docker network (`docker network create --internal scc-egress-<hash>`), start the proxy sidecar on both internal + default networks, connect/disconnect containers, and tear down the network. This needs subprocess mocking for tests.

**Phase 3 — OCI adapter integration.** Wire `NetworkTopologyManager` into `OciSandboxRuntime`: when `spec.network_policy == "web-egress-enforced"`, set up the topology before `docker create`, attach the agent to the internal network, inject proxy env. When `spec.network_policy == "locked-down-web"`, use `--network=none`. When `spec.network_policy is None or "open"`, do nothing (current behavior). Add proxy env forwarding to the OCI path (parity with Docker Desktop adapter).

**Phase 4 — Cleanup, diagnostics, and guardrail tests.** Add teardown for network/proxy on container stop/remove. Add a guardrail test that the OCI adapter's `_build_create_cmd` always produces `--network` when `network_policy != "open"`. Verify the full suite still passes.

### Verification Approach

- **Unit tests:** ACL compiler correctness (default deny IP literals, deny private CIDRs, allow specific hosts), topology manager subprocess mocking, OCI adapter `_build_create_cmd` output assertions with network flags.
- **Contract tests:** `NetworkPolicyPlan` → squid ACL roundtrip; plan builder produces expected default deny rules.
- **Guardrail test:** Tokenizer scan or static assertion that `OciSandboxRuntime._build_create_cmd` does not produce a container without `--network` when `network_policy` is enforced.
- **Standard gates:** `uv run ruff check`, `uv run mypy src/scc_cli`, `uv run pytest --rootdir "$PWD" -q`.

## Constraints

- **V1 is HTTP/HTTPS only** (per PLAN). No generic TCP/UDP proxy. Squid CONNECT handles HTTPS without TLS interception.
- **No Docker Desktop changes.** Desktop sandbox has its own network isolation; SCC should not try to layer additional isolation on top of it.
- **Constitution §3:** No Docker Desktop dependency. The topology must work with Docker Engine, OrbStack, Colima — any runtime that supports `docker network create --internal`.
- **Constitution §4:** "Security language must match actual enforcement." The `web-egress-enforced` mode must actually enforce through topology, not just set env vars.
- **`docker network create --internal`** disallows external connectivity on that network. This is a Docker Engine feature available on all OCI-compatible runtimes with the bridge driver. It is the mechanism that prevents the agent from reaching the internet directly.
- **Proxy sidecar needs dual network attachment:** internal (to receive agent requests) + default/external (to make outbound requests). Docker supports `docker network connect` to attach a container to a second network.
- **SandboxSpec.network_policy is already threaded** through `start_session.py` → `SandboxSpec` → adapter. No new wiring needed at the application layer for the basic flow.

## Common Pitfalls

- **DNS resolution in internal networks.** Docker internal networks don't provide DNS resolution to external hosts by default. The proxy sidecar must handle DNS resolution itself (Squid does this). The agent container should use the proxy for all name resolution — setting `NO_PROXY=""` and pointing `HTTP_PROXY`/`HTTPS_PROXY` at the sidecar's internal IP.
- **Container startup ordering.** The proxy sidecar must be running and reachable before the agent container starts using it. The topology manager must wait for the proxy to be healthy before returning.
- **Squid ACL evaluation order.** Squid evaluates ACLs top-to-bottom, first match wins. The default-deny rules (IP literals, private CIDRs, metadata endpoints) must come before allow rules. Incorrect ordering = security bypass.
- **Network cleanup on crash.** If SCC crashes, orphaned internal networks and proxy containers may remain. The cleanup path must be idempotent — `docker network rm` and `docker rm -f` handle already-gone resources gracefully.
- **`--network=none` for locked-down-web.** Docker's `--network=none` gives the container a loopback interface only — no network at all. This is the correct enforcement for `locked-down-web`.

## Open Risks

- **Squid image availability.** The `scc-egress-proxy` image must be available locally for the topology to work. Like the `scc-agent-claude` image (noted as a known limitation in S02), there's no image distribution strategy yet. For now, assume local builds.
- **Docker internal network support across runtimes.** While `docker network create --internal` is well-supported on Docker Engine, it may behave differently on Podman or non-standard runtimes. V1 targets Docker-compatible runtimes only; Podman support is a future concern.
- **Performance overhead of proxy sidecar.** Adding a proxy hop adds latency. For typical agent HTTP calls this should be negligible, but it's worth noting.
- **IP/CIDR ACL in squid.** Squid's `dst` ACL type supports IP addresses and CIDR ranges for destination matching. The `dstdomain` type handles hostname matching. Both are needed for the deny-private-CIDRs-plus-allow-specific-hosts pattern. Verify that squid's built-in ACL types cover all spec requirements (IP literals, loopback, link-local, metadata endpoints like 169.254.169.254).
