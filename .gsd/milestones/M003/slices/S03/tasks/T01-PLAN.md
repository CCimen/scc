---
estimated_steps: 41
estimated_files: 4
skills_used: []
---

# T01: Build egress plan builder and Squid ACL compiler with full test coverage

## Description

Create the pure-logic layer that converts network policy mode + destination sets + egress rules into a `NetworkPolicyPlan`, then compiles that plan into a Squid ACL configuration string. This is the security-critical piece — ACL correctness determines whether the topology actually enforces policy. All work is pure functions with no subprocess or Docker dependency.

## Steps

1. Create `src/scc_cli/core/egress_policy.py` with two public functions:
   - `build_egress_plan(mode: NetworkPolicy, destination_sets: tuple[DestinationSet, ...] = (), egress_rules: tuple[EgressRule, ...] = ()) -> NetworkPolicyPlan` — For `OPEN`, returns a plan with `enforced_by_runtime=False` and no rules. For `WEB_EGRESS_ENFORCED`, returns a plan with default-deny rules (IP literals, loopback 127.0.0.0/8, private CIDRs 10.0.0.0/8 + 172.16.0.0/12 + 192.168.0.0/16, link-local 169.254.0.0/16, metadata 169.254.169.254) as deny rules, followed by any allow rules from `egress_rules`, with `enforced_by_runtime=True`. For `LOCKED_DOWN_WEB`, returns `enforced_by_runtime=True` with no rules and a note indicating `--network=none`.
   - `compile_squid_acl(plan: NetworkPolicyPlan) -> str` — Converts the plan's `egress_rules` into Squid ACL syntax. Uses `acl` + `http_access` directives. Deny rules use `dst` for CIDRs and `dstdomain` for hostnames. Allow rules use `dstdomain` for hostnames. Default final line: `http_access deny all`. Squid evaluates top-to-bottom first-match, so deny rules MUST come before allow rules.
2. Define private constants for the default deny targets (IP literal regex pattern, private CIDRs, link-local, metadata endpoint).
3. Create `tests/test_egress_policy.py` with comprehensive test coverage:
   - `test_open_mode_produces_no_rules` — OPEN mode returns empty rules, `enforced_by_runtime=False`.
   - `test_enforced_mode_has_default_deny_rules` — WEB_EGRESS_ENFORCED returns all default deny rules.
   - `test_locked_down_mode_has_no_rules` — LOCKED_DOWN_WEB returns `enforced_by_runtime=True`, empty rules, note about `--network=none`.
   - `test_enforced_mode_with_allow_rules` — Custom allow rules appear after default deny rules.
   - `test_enforced_mode_with_destination_sets` — Destination sets are threaded into the plan.
   - `test_compile_acl_deny_private_cidrs` — ACL output contains `acl` entries for all private CIDRs.
   - `test_compile_acl_deny_metadata` — ACL denies 169.254.169.254.
   - `test_compile_acl_allow_specific_hosts` — Allow rules produce `dstdomain` entries.
   - `test_compile_acl_deny_before_allow_ordering` — Deny `http_access` lines come before allow lines.
   - `test_compile_acl_ends_with_deny_all` — Final line is `http_access deny all`.
   - `test_compile_acl_open_mode_permits_all` — OPEN mode with no rules produces `http_access allow all`.
   - `test_compile_acl_locked_down_produces_deny_all` — LOCKED_DOWN_WEB produces only `http_access deny all`.
4. Run `uv run ruff check src/scc_cli/core/egress_policy.py tests/test_egress_policy.py` and `uv run mypy src/scc_cli/core/egress_policy.py`.
5. Run `uv run pytest tests/test_egress_policy.py -q` to confirm all tests pass.

## Must-Haves

- [ ] `build_egress_plan()` handles all three `NetworkPolicy` modes correctly
- [ ] Default deny rules cover IP literals, loopback, private CIDRs, link-local, metadata
- [ ] `compile_squid_acl()` produces valid Squid syntax with deny-before-allow ordering
- [ ] Final ACL line is always `http_access deny all` (for enforced) or `http_access allow all` (for open)
- [ ] All types are annotated; mypy clean
- [ ] 12+ unit tests covering plan builder and ACL compiler

## Verification

- `uv run pytest tests/test_egress_policy.py -q` — all tests pass
- `uv run ruff check src/scc_cli/core/egress_policy.py tests/test_egress_policy.py` — clean
- `uv run mypy src/scc_cli/core/egress_policy.py` — no issues

## Negative Tests

- **Malformed inputs**: empty destination set tuple, egress rule with empty target string
- **Boundary conditions**: enforced mode with zero allow rules (only deny), OPEN mode passed through compile_squid_acl

## Failure Modes

| Dependency | On error | On timeout | On malformed response |
|------------|----------|-----------|----------------------|
| NetworkPolicyPlan contract | TypeError from frozen dataclass — caught by type checker | N/A (pure function) | N/A |
| Squid ACL syntax | Invalid config crashes proxy at startup — caught by compile tests | N/A | N/A |

## Inputs

- ``src/scc_cli/core/contracts.py` — NetworkPolicyPlan, EgressRule, DestinationSet dataclasses (already defined, frozen, fields: mode, destination_sets, egress_rules, enforced_by_runtime, notes)`
- ``src/scc_cli/core/enums.py` — NetworkPolicy enum with OPEN, WEB_EGRESS_ENFORCED, LOCKED_DOWN_WEB values`
- ``src/scc_cli/core/network_policy.py` — existing collect_proxy_env() and policy_rank() helpers for reference`

## Expected Output

- ``src/scc_cli/core/egress_policy.py` — new module with build_egress_plan() and compile_squid_acl() public functions`
- ``tests/test_egress_policy.py` — 12+ unit tests covering all three modes, default deny rules, ACL compilation, ordering`

## Verification

uv run pytest tests/test_egress_policy.py -q && uv run ruff check src/scc_cli/core/egress_policy.py tests/test_egress_policy.py && uv run mypy src/scc_cli/core/egress_policy.py
