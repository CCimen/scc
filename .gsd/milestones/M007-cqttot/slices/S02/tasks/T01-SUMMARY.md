---
id: T01
parent: S02
milestone: M007-cqttot
key_files:
  - src/scc_cli/sessions.py
  - src/scc_cli/commands/audit.py
  - src/scc_cli/commands/launch/sandbox.py
  - src/scc_cli/contexts.py
  - src/scc_cli/commands/worktree/session_commands.py
  - tests/test_sessions.py
key_decisions:
  - Default parameter value 'claude' on renamed helpers preserves backward compatibility without migration
  - WorkContext.display_label appends provider info only for non-default providers to avoid visual noise
duration: 
verification_result: passed
completed_at: 2026-04-05T12:56:35.556Z
blocker_discovered: false
---

# T01: Renamed three Claude-hardcoded helpers to provider-parameterized versions using registry, fixed sandbox provider_id, added provider_id to WorkContext, and surfaced provider in session list CLI and Quick Resume display

**Renamed three Claude-hardcoded helpers to provider-parameterized versions using registry, fixed sandbox provider_id, added provider_id to WorkContext, and surfaced provider in session list CLI and Quick Resume display**

## What Happened

Executed all six task plan steps: renamed get_claude_sessions_dir → get_provider_sessions_dir and get_claude_recent_sessions → get_provider_recent_sessions in sessions.py, renamed get_claude_dir → get_provider_config_dir in audit.py (all using get_runtime_spec from provider_registry instead of hardcoded AGENT_CONFIG_DIR), fixed sandbox.py to record provider_id='claude' explicitly instead of None, added provider_id field to WorkContext with full backward-compat serialization and merge support, updated display_label to surface non-default providers, and added Provider column to session list CLI table. Updated one test for the new column shape.

## Verification

ruff check on all 6 source files — zero errors. mypy on all 6 source files — zero errors. Full pytest suite: 4654 passed, 23 skipped, 2 xfailed, 0 failures.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check src/scc_cli/sessions.py src/scc_cli/commands/audit.py src/scc_cli/commands/launch/sandbox.py src/scc_cli/commands/worktree/session_commands.py src/scc_cli/contexts.py src/scc_cli/application/launch/start_wizard.py` | 0 | ✅ pass | 3000ms |
| 2 | `uv run mypy src/scc_cli/sessions.py src/scc_cli/commands/audit.py src/scc_cli/commands/launch/sandbox.py src/scc_cli/commands/worktree/session_commands.py src/scc_cli/contexts.py src/scc_cli/application/launch/start_wizard.py` | 0 | ✅ pass | 3000ms |
| 3 | `uv run pytest -q` | 0 | ✅ pass | 48200ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/sessions.py`
- `src/scc_cli/commands/audit.py`
- `src/scc_cli/commands/launch/sandbox.py`
- `src/scc_cli/contexts.py`
- `src/scc_cli/commands/worktree/session_commands.py`
- `tests/test_sessions.py`
