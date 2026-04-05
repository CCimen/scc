---
id: T08
parent: S05
milestone: M007-cqttot
key_files:
  - src/scc_cli/application/start_session.py
  - tests/test_application_start_session.py
key_decisions:
  - D038/D042 implemented via early-return in _build_agent_settings for resume, and empty-dict fallback for fresh launch
duration: 
verification_result: passed
completed_at: 2026-04-05T15:31:17.866Z
blocker_discovered: false
---

# T08: Fresh launch now deterministically writes SCC-managed config layer (even when empty); resume skips injection to preserve session context

**Fresh launch now deterministically writes SCC-managed config layer (even when empty); resume skips injection to preserve session context**

## What Happened

Implemented D038/D042 config freshness guarantee in _build_agent_settings. Added is_resume parameter: resume returns None (OCI runtime skips injection), fresh launch always produces AgentSettings (empty dict fallback overwrites stale volume config). Codex fresh launch with empty config still gets SCC-managed defaults (cli_auth_credentials_store='file') via runner merge. Updated one existing test assertion invalidated by the new semantics. Added 7 new tests covering fresh/resume paths and transition scenarios (governed→standalone, teamA→teamB, settings→no-settings).

## Verification

ruff check: zero errors. mypy: zero issues. 92 targeted tests passed (start_session + OCI runtime). 41 truthfulness/branding tests passed. Full suite: 4768 passed, 0 failed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 2000ms |
| 2 | `uv run mypy src/scc_cli/application/start_session.py` | 0 | ✅ pass | 2000ms |
| 3 | `uv run pytest tests/test_application_start_session.py tests/test_oci_sandbox_runtime.py -v` | 0 | ✅ pass | 5000ms |
| 4 | `uv run pytest tests/test_docs_truthfulness.py tests/test_provider_branding.py -v` | 0 | ✅ pass | 6000ms |
| 5 | `uv run pytest -q` | 0 | ✅ pass | 50000ms |

## Deviations

Updated test_prepare_start_session_captures_sync_error assertion from agent_settings is None to agent_settings is not None with empty content — existing assertion was invalidated by D038 fresh-launch-always-writes semantics.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/application/start_session.py`
- `tests/test_application_start_session.py`
