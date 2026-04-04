---
id: T03
parent: S03
milestone: M001
key_files:
  - tests/test_docker_policy.py
  - tests/test_docker_policy_integration.py
  - tests/test_plugin_isolation.py
  - src/scc_cli/docker/launch.py
key_decisions:
  - Characterize the current safety baseline at the sandbox launch boundary, not only in pure helper tests.
  - Make the fail-closed default visible in a high-level test by asserting that sandbox launch still writes `{"action": "block"}` when no org config is provided.
duration: 
verification_result: passed
completed_at: 2026-04-03T15:34:26.210Z
blocker_discovered: false
---

# T03: Locked the current safety-net baseline with a launch-boundary test proving fail-closed default policy injection.

**Locked the current safety-net baseline with a launch-boundary test proving fail-closed default policy injection.**

## What Happened

I audited the current safety-net coverage and found that the helper functions for extracting, validating, and defaulting safety-net policy were already well tested, including fail-closed behavior. The missing characterization was at the launch boundary: a clear statement that sandbox launch still writes the default block policy even when no org config is present. I added that high-level test to the existing plugin-isolation/launch-area suite and then ran the focused safety-net test set covering helper behavior, policy file writing/integration, and the launch boundary. All targeted tests passed, which means the current safety-net behavior is now characterized where it actually exists in this codebase.

## Verification

Ran the focused safety-net characterization suite covering pure policy helpers, integration writing behavior, and the launch-boundary plugin-isolation tests. All targeted tests passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_docker_policy.py tests/test_docker_policy_integration.py tests/test_plugin_isolation.py` | 0 | ✅ pass | 4308ms |

## Deviations

I targeted the current safety-net seam that actually exists in this repo—policy extraction/validation and sandbox injection—rather than inventing direct destructive-git or network-tool runtime tests that are not implemented here yet.

## Known Issues

This repo’s current safety-net seam is policy extraction, validation, and sandbox injection. Direct cross-agent command-family enforcement for destructive git and explicit network tools is still future work, so this task characterizes the current baseline rather than a not-yet-built SafetyEngine.

## Files Created/Modified

- `tests/test_docker_policy.py`
- `tests/test_docker_policy_integration.py`
- `tests/test_plugin_isolation.py`
- `src/scc_cli/docker/launch.py`
