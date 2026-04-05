---
id: T01
parent: S04
milestone: M006-d622bc
key_files:
  - src/scc_cli/ports/session_models.py
  - src/scc_cli/application/sessions/use_cases.py
  - src/scc_cli/sessions.py
  - src/scc_cli/commands/launch/flow_session.py
  - src/scc_cli/commands/launch/flow.py
  - src/scc_cli/commands/launch/flow_interactive.py
  - src/scc_cli/commands/launch/sandbox.py
  - tests/test_session_provider_id.py
  - tests/test_sessions.py
key_decisions:
  - schema_version bumped from 1 to 2 for new records; from_dict still defaults to 1 for legacy data
  - record_session preserves schema_version from existing records on update
  - Legacy sandbox.py path passes provider_id=None since provider is not resolved there
duration: 
verification_result: passed
completed_at: 2026-04-05T01:00:40.377Z
blocker_discovered: false
---

# T01: Added provider_id field to SessionRecord, SessionSummary, SessionFilter and threaded it through all session recording and listing call sites in the launch flow

**Added provider_id field to SessionRecord, SessionSummary, SessionFilter and threaded it through all session recording and listing call sites in the launch flow**

## What Happened

Added `provider_id: str | None = None` to all three session dataclasses (SessionRecord, SessionSummary, SessionFilter). Updated from_dict() for backward compat, bumped schema_version default to 2. Threaded provider_id through SessionService.record_session(), the sessions.py facade, _record_session_and_context(), and all call sites in flow.py, flow_interactive.py, and sandbox.py. Added provider_id filtering to _filter_sessions(). Fixed a latent bug where record_session wasn't preserving schema_version from existing records on update. Created 13 new tests and updated 1 existing test.

## Verification

All four verification checks passed: 13/13 provider_id tests pass, ruff clean on target files, mypy clean on target files, full suite 4599 passed / 0 failed / 23 skipped / 2 xfailed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_session_provider_id.py -v --no-cov` | 0 | ✅ pass | 4100ms |
| 2 | `uv run ruff check src/scc_cli/ports/session_models.py src/scc_cli/sessions.py src/scc_cli/commands/launch/flow_session.py` | 0 | ✅ pass | 4100ms |
| 3 | `uv run mypy src/scc_cli/ports/session_models.py src/scc_cli/sessions.py src/scc_cli/commands/launch/flow_session.py` | 0 | ✅ pass | 4100ms |
| 4 | `uv run pytest --rootdir "$PWD" -q --no-cov` | 0 | ✅ pass | 62340ms |

## Deviations

Fixed latent schema_version preservation bug exposed by version bump. Updated existing test_sessions.py schema version test. Also updated update_session_container to preserve provider_id.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/ports/session_models.py`
- `src/scc_cli/application/sessions/use_cases.py`
- `src/scc_cli/sessions.py`
- `src/scc_cli/commands/launch/flow_session.py`
- `src/scc_cli/commands/launch/flow.py`
- `src/scc_cli/commands/launch/flow_interactive.py`
- `src/scc_cli/commands/launch/sandbox.py`
- `tests/test_session_provider_id.py`
- `tests/test_sessions.py`
