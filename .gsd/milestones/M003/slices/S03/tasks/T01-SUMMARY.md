---
id: T01
parent: S03
milestone: M003
key_files:
  - src/scc_cli/core/egress_policy.py
  - tests/test_egress_policy.py
key_decisions:
  - Squid ACL uses numbered acl names (deny_1, allow_1) for deterministic output
  - IP literals and CIDRs use dst directive; hostnames use dstdomain directive
  - OPEN mode produces http_access allow all; LOCKED_DOWN_WEB produces http_access deny all
duration: 
verification_result: passed
completed_at: 2026-04-04T09:41:44.796Z
blocker_discovered: false
---

# T01: Added build_egress_plan() and compile_squid_acl() pure functions with 19 tests covering all three network policy modes, default deny rules, and ACL compilation ordering

**Added build_egress_plan() and compile_squid_acl() pure functions with 19 tests covering all three network policy modes, default deny rules, and ACL compilation ordering**

## What Happened

Created src/scc_cli/core/egress_policy.py with two public functions: build_egress_plan() converts NetworkPolicy mode + destination sets + egress rules into a NetworkPolicyPlan with correct default deny rules for loopback, private CIDRs, link-local, and metadata endpoints; compile_squid_acl() compiles the plan into valid Squid ACL syntax with deny-before-allow ordering and a terminal http_access directive. Created tests/test_egress_policy.py with 19 tests organized into four classes covering mode behavior, rule composition, edge cases, and ACL compilation invariants. All functions are pure with no subprocess or Docker dependency.

## Verification

All three slice-level verification commands pass:\n- uv run pytest tests/test_egress_policy.py -q: 19 passed, 100% coverage on egress_policy.py\n- uv run ruff check src/scc_cli/core/egress_policy.py tests/test_egress_policy.py: all checks passed\n- uv run mypy src/scc_cli/core/egress_policy.py: no issues found

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_egress_policy.py -q` | 0 | ✅ pass | 1090ms |
| 2 | `uv run ruff check src/scc_cli/core/egress_policy.py tests/test_egress_policy.py` | 0 | ✅ pass | 1000ms |
| 3 | `uv run mypy src/scc_cli/core/egress_policy.py` | 0 | ✅ pass | 1000ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/core/egress_policy.py`
- `tests/test_egress_policy.py`
