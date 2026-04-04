# S04: Policy integration, provider destination validation, and operator diagnostics — UAT

**Milestone:** M003
**Written:** 2026-04-04T10:42:06.827Z

## UAT: S04 — Policy integration, provider destination validation, and operator diagnostics

### Preconditions
- Python 3.10+ with uv available
- Working directory: scc-sync-1.7.3/
- Docker daemon is not required (tests mock runtime probes)

---

### TC-01: Provider Destination Registry Resolution

**Goal:** Verify the destination registry correctly resolves known provider sets and rejects unknown ones.

1. Run `uv run pytest --rootdir "$PWD" tests/test_destination_registry.py -q`
2. **Expected:** 17 tests pass
3. Verify `anthropic-core` resolves to DestinationSet with `api.anthropic.com`
4. Verify `openai-core` resolves to DestinationSet with `api.openai.com`
5. Verify resolving an unknown name raises ValueError
6. Verify empty input returns empty tuple

### TC-02: Rule Generation From Destination Sets

**Goal:** Verify destination sets correctly convert to EgressRule allow objects.

1. Run `uv run pytest --rootdir "$PWD" tests/test_destination_registry.py -k "rule" -q`
2. **Expected:** All rule-generation tests pass
3. Verify generated rules have `allow=True` and reason containing `provider-core:`
4. Verify multiple sets produce combined rules covering all destinations

### TC-03: SandboxSpec Carries Destination Sets

**Goal:** Verify destination_sets field is available on SandboxSpec and defaults safely.

1. Construct a SandboxSpec without destination_sets → field defaults to `()`
2. Construct a SandboxSpec with resolved DestinationSet tuples → field carries them through
3. **Expected:** No existing SandboxSpec construction sites break (frozen dataclass with default)

### TC-04: OCI Adapter Threads Destination Rules Into Egress Plan

**Goal:** Verify the OCI adapter converts SandboxSpec destination sets into allow rules in the egress plan.

1. Run `uv run pytest --rootdir "$PWD" tests/test_oci_egress_integration.py -k "destination" -q`
2. **Expected:** Tests pass confirming that destination sets on SandboxSpec produce matching allow rules in the egress plan
3. Verify allow rules contain provider hostnames from the destination set

### TC-05: Enforced-Mode Preflight Blocks Unresolvable Destinations

**Goal:** Verify preflight validation catches unresolvable destination sets before launch.

1. Run `uv run pytest --rootdir "$PWD" tests/test_launch_preflight.py -k "enforced" -q`
2. **Expected:** Tests pass
3. Verify that preflight with `web-egress-enforced` policy and an unknown destination set raises LaunchPolicyBlockedError
4. Verify that preflight with `web-egress-enforced` policy and valid destination sets passes

### TC-06: Doctor Check Reports Runtime Backend

**Goal:** Verify `scc doctor` runtime backend check works across all backend states.

1. Run `uv run pytest --rootdir "$PWD" tests/test_doctor_checks.py -k "runtime_backend" -q`
2. **Expected:** 4 tests pass covering docker-sandbox, oci, daemon-unavailable, and probe-exception scenarios
3. Verify docker-sandbox case returns passed=True with "docker-sandbox" in message
4. Verify oci case returns passed=True with "oci" in message
5. Verify daemon-unavailable returns passed=False with warning severity
6. Verify probe exception returns passed=False without crashing

### TC-07: Support Bundle Includes Effective Egress Section

**Goal:** Verify support bundle manifest includes the effective_egress section with runtime, policy, and destination data.

1. Run `uv run pytest --rootdir "$PWD" tests/test_support_bundle.py -k "effective_egress" -q`
2. **Expected:** 2 tests pass
3. Verify the effective_egress section includes runtime_backend, network_policy, and resolved_destination_sets keys
4. Verify that when the runtime probe fails, the section still includes partial data (network_policy and resolved_destination_sets) rather than crashing

### TC-08: No Regression Across Full Suite

**Goal:** Verify the 30 new tests integrate without breaking existing functionality.

1. Run `uv run pytest --rootdir "$PWD" -q`
2. **Expected:** 3432+ tests pass, 0 failures
3. Run `uv run mypy src/scc_cli`
4. **Expected:** Success: no issues found in 249 source files
5. Run `uv run ruff check`
6. **Expected:** All checks passed

### Edge Cases

- **Empty destination sets on SandboxSpec:** Egress plan should proceed normally without additional allow rules
- **Multiple provider sets resolved together:** Combined rules should contain all hosts from all sets
- **Probe failure during support bundle:** Section should degrade gracefully with partial data, never crash
- **TYPE_CHECKING import for DestinationSet in models.py:** mypy should validate types correctly despite the guard
