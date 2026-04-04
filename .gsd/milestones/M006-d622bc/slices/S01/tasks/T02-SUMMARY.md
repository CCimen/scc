---
id: T02
parent: S01
milestone: M006-d622bc
key_files:
  - src/scc_cli/commands/provider.py
  - src/scc_cli/cli.py
  - src/scc_cli/application/start_session.py
  - src/scc_cli/commands/launch/flow.py
  - tests/test_provider_commands.py
key_decisions:
  - Used no_args_is_help=True on provider_app so bare 'scc provider' shows usage
  - provider_id on StartSessionRequest defaults to None; resolution happens downstream
duration: 
verification_result: passed
completed_at: 2026-04-04T23:01:26.829Z
blocker_discovered: false
---

# T02: Added scc provider show/set commands, --provider flag on scc start, and provider_id field on StartSessionRequest

**Added scc provider show/set commands, --provider flag on scc start, and provider_id field on StartSessionRequest**

## What Happened

Created src/scc_cli/commands/provider.py with a provider_app Typer sub-app containing show and set commands. show prints the configured provider (defaults to 'claude'), set validates against KNOWN_PROVIDERS and persists. Registered provider_app in cli.py under the Configuration panel. Added provider_id: str | None = None to StartSessionRequest. Added --provider option to start() in flow.py and threaded it into the request. Wrote 9 tests covering default/configured show, valid/invalid set, help display, and request model field. Also fixed two pre-existing ruff I001 import-sorting violations blocking the verification gate.

## Verification

All three verification gates pass: uv run ruff check (clean), uv run mypy src/scc_cli (291 files, no issues), uv run pytest (4518 passed, 23 skipped, 2 xfailed). Focused test run: uv run pytest tests/test_provider_commands.py -v (9/9 passed).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 3000ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 80000ms |
| 3 | `uv run pytest` | 0 | ✅ pass | 71000ms |
| 4 | `uv run pytest tests/test_provider_commands.py -v` | 0 | ✅ pass | 2000ms |

## Deviations

Fixed two pre-existing ruff I001 import-sorting violations in environment.py and test_provider_resolution.py. Test for no-args help checks output content rather than exit code since typer uses exit 2 for help display.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/commands/provider.py`
- `src/scc_cli/cli.py`
- `src/scc_cli/application/start_session.py`
- `src/scc_cli/commands/launch/flow.py`
- `tests/test_provider_commands.py`
