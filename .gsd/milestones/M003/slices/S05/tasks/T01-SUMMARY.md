---
id: T01
parent: S05
milestone: M003
key_files:
  - src/scc_cli/application/compute_effective_config.py
  - src/scc_cli/commands/config.py
  - tests/test_config_explain.py
  - README.md
key_decisions:
  - README Requires line lists Docker generically (Engine, Desktop, OrbStack, Colima) per Constitution §3
duration: 
verification_result: passed
completed_at: 2026-04-04T11:02:21.839Z
blocker_discovered: false
---

# T01: Updated all stale network-mode vocabulary (isolated→locked-down-web, corp-proxy-only→web-egress-enforced, unrestricted→open) in source, tests, and README; removed Docker Desktop hard-dependency claim

**Updated all stale network-mode vocabulary (isolated→locked-down-web, corp-proxy-only→web-egress-enforced, unrestricted→open) in source, tests, and README; removed Docker Desktop hard-dependency claim**

## What Happened

Fixed six stale network-mode strings across four files. In compute_effective_config.py, updated two blocked_by diagnostic strings from 'isolated' to 'locked-down-web'. In config.py, updated warning message from 'corp-proxy-only' to 'web-egress-enforced'. In test_config_explain.py, updated fixture values and docstring from 'corp-proxy' to 'web-egress-enforced'. In README.md, generalized Docker requirement per Constitution §3, rewrote enforcement scope with topology-based description and IPv4-only disclosure, changed example JSON from 'unrestricted' to 'open', and updated troubleshooting table.

## Verification

All five verification checks pass: 31/31 pytest tests pass with updated vocabulary, zero occurrences of stale 'network_policy=isolated' in compute_effective_config.py, zero occurrences of 'corp-proxy-only' in config.py, zero occurrences of '"unrestricted"' in README.md, and no Docker Desktop hard requirement in README.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest --rootdir "$PWD" tests/test_config_explain.py -q` | 0 | ✅ pass | 2020ms |
| 2 | `grep -c 'network_policy=isolated' src/scc_cli/application/compute_effective_config.py` | 0 | ✅ pass | 50ms |
| 3 | `grep -c 'corp-proxy-only' src/scc_cli/commands/config.py` | 0 | ✅ pass | 50ms |
| 4 | `grep -c '"unrestricted"' README.md` | 0 | ✅ pass | 50ms |
| 5 | `! grep -q 'Requires.*Docker Desktop' README.md` | 0 | ✅ pass | 50ms |

## Deviations

The edit tool initially reported success for README changes but did not persist them. Used absolute paths and sed as fallback to apply the README edits.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/application/compute_effective_config.py`
- `src/scc_cli/commands/config.py`
- `tests/test_config_explain.py`
- `README.md`
