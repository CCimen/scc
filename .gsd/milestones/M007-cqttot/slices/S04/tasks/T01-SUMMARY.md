---
id: T01
parent: S04
milestone: M007-cqttot
key_files:
  - src/scc_cli/core/constants.py
  - src/scc_cli/docker/core.py
  - src/scc_cli/docker/credentials.py
  - src/scc_cli/docker/launch.py
  - src/scc_cli/adapters/oci_sandbox_runtime.py
  - src/scc_cli/application/start_session.py
key_decisions:
  - Localized constants in all consumer modules (docker/, adapters/, application/) not just docker/
  - Used underscore-prefixed names to signal module-private scope
  - Test files use aliased imports to minimize test churn
duration: 
verification_result: passed
completed_at: 2026-04-05T13:51:04.283Z
blocker_discovered: false
---

# T01: Localize 9 Claude-specific constants from core/constants.py into 5 consumer modules (docker/, adapters/, application/)

**Localize 9 Claude-specific constants from core/constants.py into 5 consumer modules (docker/, adapters/, application/)**

## What Happened

Scanned all imports of Claude-specific constants from core/constants.py. Extended scope beyond docker/ to also localize constants in adapters/oci_sandbox_runtime.py (AGENT_NAME, SANDBOX_DATA_VOLUME) and application/start_session.py (SANDBOX_IMAGE) — necessary to make the removal safe. Each consumer module got underscore-prefixed local constants. Updated 4 test files to import from localized sources. Stripped constants.py to product-level values only (CLI_VERSION, CURRENT_SCHEMA_VERSION, WORKTREE_BRANCH_PREFIX).

## Verification

ruff check: 0 errors. mypy src/scc_cli: 293 files clean. Full pytest: 4718 passed, 23 skipped, 2 xfailed. Targeted docker/adapter/start_session tests: 294 passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 4800ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4800ms |
| 3 | `uv run pytest` | 0 | ✅ pass | 51400ms |
| 4 | `uv run pytest tests/test_docker*.py tests/test_oci_sandbox_runtime.py tests/test_application_start_session.py tests/test_start_session_image_routing.py -v` | 0 | ✅ pass | 6100ms |

## Deviations

Extended scope beyond docker/ to also localize constants in adapters/oci_sandbox_runtime.py and application/start_session.py — required to make the constants.py removal safe.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/core/constants.py`
- `src/scc_cli/docker/core.py`
- `src/scc_cli/docker/credentials.py`
- `src/scc_cli/docker/launch.py`
- `src/scc_cli/adapters/oci_sandbox_runtime.py`
- `src/scc_cli/application/start_session.py`
