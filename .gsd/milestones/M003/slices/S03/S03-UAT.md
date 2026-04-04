# S03: Enforced web-egress topology and proxy ACLs — UAT

**Milestone:** M003
**Written:** 2026-04-04T09:58:31.536Z

## UAT: S03 — Enforced web-egress topology and proxy ACLs

### Preconditions
- Python 3.10+ with uv installed
- Working directory: `scc-sync-1.7.3`
- All dependencies installed via `uv sync`

---

### TC-01: Egress plan generation for web-egress-enforced mode
**Steps:**
1. Run `uv run python -c "from scc_cli.core.egress_policy import build_egress_plan; from scc_cli.core.enums import NetworkPolicy; plan = build_egress_plan(NetworkPolicy.WEB_EGRESS_ENFORCED); print(f'enforced={plan.enforced_by_runtime}, rules={len(plan.egress_rules)}')"` 
**Expected:** Output shows `enforced=True` and at least 6 default deny rules (loopback, 3 private CIDRs, link-local, metadata).

### TC-02: Egress plan generation for locked-down-web mode
**Steps:**
1. Run `uv run python -c "from scc_cli.core.egress_policy import build_egress_plan; from scc_cli.core.enums import NetworkPolicy; plan = build_egress_plan(NetworkPolicy.LOCKED_DOWN_WEB); print(f'enforced={plan.enforced_by_runtime}, rules={len(plan.egress_rules)}, note={plan.note}')"` 
**Expected:** Output shows `enforced=True`, `rules=0`, and a note mentioning `--network=none`.

### TC-03: Egress plan generation for open mode
**Steps:**
1. Run `uv run python -c "from scc_cli.core.egress_policy import build_egress_plan; from scc_cli.core.enums import NetworkPolicy; plan = build_egress_plan(NetworkPolicy.OPEN); print(f'enforced={plan.enforced_by_runtime}, rules={len(plan.egress_rules)}')"` 
**Expected:** Output shows `enforced=False` and `rules=0`.

### TC-04: Squid ACL compilation produces valid deny-before-allow ordering
**Steps:**
1. Run `uv run python -c "from scc_cli.core.egress_policy import build_egress_plan, compile_squid_acl; from scc_cli.core.enums import NetworkPolicy; from scc_cli.core.contracts import EgressRule; plan = build_egress_plan(NetworkPolicy.WEB_EGRESS_ENFORCED, egress_rules=(EgressRule(target='api.example.com', action='allow'),)); acl = compile_squid_acl(plan); lines = acl.strip().split(chr(10)); print('deny_before_allow:', any('deny' in l for l in lines[:len(lines)//2])); print('ends_deny_all:', lines[-1])"` 
**Expected:** `deny_before_allow: True` and last line is `http_access deny all`.

### TC-05: Squid ACL for open mode produces allow all
**Steps:**
1. Run `uv run python -c "from scc_cli.core.egress_policy import build_egress_plan, compile_squid_acl; from scc_cli.core.enums import NetworkPolicy; plan = build_egress_plan(NetworkPolicy.OPEN); acl = compile_squid_acl(plan); print(acl.strip())"` 
**Expected:** Output is `http_access allow all`.

### TC-06: Proxy sidecar image files are well-formed
**Steps:**
1. Verify `images/scc-egress-proxy/Dockerfile` contains `FROM alpine:3.19`, `squid` install, `EXPOSE 3128`, and a `HEALTHCHECK`
2. Verify `images/scc-egress-proxy/squid.conf.template` contains `# SCC_ACL_RULES_START` and `# SCC_ACL_RULES_END` markers
3. Verify `images/scc-egress-proxy/entrypoint.sh` contains `exec squid` and references `/etc/squid/acl-rules.conf`
**Expected:** All three files exist with the expected content markers.

### TC-07: NetworkTopologyManager creates internal network and dual-homed proxy
**Steps:**
1. Run `uv run pytest tests/test_egress_topology.py::TestNetworkTopologyManagerSetup -v -q`
**Expected:** All setup tests pass, confirming: internal network creation, proxy container start with correct labels and volume mount, bridge connection for dual-homing, and IP extraction from the correct internal network.

### TC-08: NetworkTopologyManager teardown is idempotent
**Steps:**
1. Run `uv run pytest tests/test_egress_topology.py::TestNetworkTopologyManagerTeardown -v -q`
**Expected:** Teardown tests pass, confirming: proxy removal and network removal even when resources are already gone.

### TC-09: OCI adapter uses --network for enforced mode
**Steps:**
1. Run `uv run pytest tests/test_oci_sandbox_runtime.py::TestNetworkEnforcement -v -q`
**Expected:** All 5 tests pass confirming: enforced mode adds explicit `--network` flag, locked-down adds `--network none`, open mode has no `--network` flag, proxy env vars injected for enforced mode.

### TC-10: OCI adapter wires topology lifecycle
**Steps:**
1. Run `uv run pytest tests/test_oci_egress_integration.py -v -q`
**Expected:** All 11 tests pass confirming: topology setup before docker create, network name passed to create, locked-down skips topology, remove() calls teardown, open mode unchanged, and the guardrail that enforced mode never produces a default network.

### TC-11: Full test suite regression check
**Steps:**
1. Run `uv run pytest --rootdir "$PWD" -q`
**Expected:** 3402+ passed, 23 skipped, 4 xfailed. No failures or unexpected test errors.

### Edge Cases

### TC-12: Empty destination sets and egress rules
**Steps:**
1. Run `uv run pytest tests/test_egress_policy.py -k "empty" -v -q`
**Expected:** Tests confirm empty tuples produce valid plans without errors.

### TC-13: Topology setup failure triggers cleanup
**Steps:**
1. Run `uv run pytest tests/test_egress_topology.py -k "failure" -v -q`
**Expected:** Tests confirm that when proxy start fails, the network is still cleaned up.
