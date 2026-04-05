---
id: T02
parent: S04
milestone: M007-cqttot
key_files:
  - src/scc_cli/adapters/oci_sandbox_runtime.py
  - src/scc_cli/application/start_session.py
  - src/scc_cli/commands/profile.py
  - tests/test_oci_sandbox_runtime.py
  - tests/test_application_start_session.py
  - tests/test_start_session_image_routing.py
key_decisions:
  - Renamed T01's localized constants to more descriptive _CLAUDE_* prefixed names for self-documentation
duration: 
verification_result: passed
completed_at: 2026-04-05T13:56:11.512Z
blocker_discovered: false
---

# T02: Renamed localized Claude constants to _CLAUDE_AGENT_NAME, _CLAUDE_DATA_VOLUME, _DOCKER_DESKTOP_CLAUDE_IMAGE and documented profile.py as Claude provider only

**Renamed localized Claude constants to _CLAUDE_AGENT_NAME, _CLAUDE_DATA_VOLUME, _DOCKER_DESKTOP_CLAUDE_IMAGE and documented profile.py as Claude provider only**

## What Happened

T01 had already localized all Claude-specific constants from core/constants.py into consumer modules. T02 renamed these to explicitly Claude-prefixed names (_CLAUDE_AGENT_NAME, _CLAUDE_DATA_VOLUME in oci_sandbox_runtime.py, _DOCKER_DESKTOP_CLAUDE_IMAGE in start_session.py) for self-documentation. Updated three test files with aliased imports. Documented profile.py module docstring as Claude provider only.

## Verification

86 targeted tests pass. ruff check clean on all 3 source files. mypy clean on all 3 source files. No remaining core.constants imports for Claude-specific values in the codebase.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_oci_sandbox_runtime.py tests/test_application_start_session.py tests/test_start_session_image_routing.py -v` | 0 | ✅ pass | 4500ms |
| 2 | `uv run ruff check src/scc_cli/adapters/oci_sandbox_runtime.py src/scc_cli/application/start_session.py src/scc_cli/commands/profile.py` | 0 | ✅ pass | 4500ms |
| 3 | `uv run mypy src/scc_cli/adapters/oci_sandbox_runtime.py src/scc_cli/application/start_session.py src/scc_cli/commands/profile.py` | 0 | ✅ pass | 4500ms |

## Deviations

T01 already did the constant localization, so T02 reduced to renaming for clarity and documenting profile.py.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/adapters/oci_sandbox_runtime.py`
- `src/scc_cli/application/start_session.py`
- `src/scc_cli/commands/profile.py`
- `tests/test_oci_sandbox_runtime.py`
- `tests/test_application_start_session.py`
- `tests/test_start_session_image_routing.py`
