---
id: T02
parent: S03
milestone: M001
key_files:
  - tests/test_config_inheritance.py
  - tests/test_config_explain.py
  - tests/test_network_policy.py
  - src/scc_cli/core/network_policy.py
key_decisions:
  - Characterize the truthful policy ordering directly in tests instead of relying only on indirect merge behavior.
  - Assert the exact locked-down-web blocked_by reason so later refactors cannot preserve the block while changing its diagnostic contract silently.
duration: 
verification_result: passed
completed_at: 2026-04-03T15:32:24.111Z
blocker_discovered: false
---

# T02: Locked the truthful policy-ordering and block-reason contract with focused config-policy characterization tests.

**Locked the truthful policy-ordering and block-reason contract with focused config-policy characterization tests.**

## What Happened

I reviewed the existing config inheritance and config-explain coverage and found that the merge behavior itself was already well represented, but the newly adopted truthful policy ordering was not stated directly anywhere. To lock that down, I added a small `tests/test_network_policy.py` module covering the ordering of open, web-egress-enforced, and locked-down-web, and I tightened the locked-down-web MCP blocking test to assert the exact `blocked_by` diagnostic string. Then I ran the focused config-policy test set to confirm that the helper ordering, inheritance behavior, and config warnings all still agree under the new vocabulary.

## Verification

Ran the focused config-policy characterization suite covering config inheritance, config explain warnings, and the new network-policy helper tests. All targeted tests passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_config_inheritance.py tests/test_config_explain.py tests/test_network_policy.py` | 0 | ✅ pass | 5442ms |

## Deviations

I added a small dedicated network-policy helper test module rather than expanding the existing inheritance file further, because the missing contract was the truthful ordering itself.

## Known Issues

Existing config coverage was already broad, so this task focused on making the truthful ordering and block-reason contract explicit rather than adding more overlapping merge fixtures.

## Files Created/Modified

- `tests/test_config_inheritance.py`
- `tests/test_config_explain.py`
- `tests/test_network_policy.py`
- `src/scc_cli/core/network_policy.py`
