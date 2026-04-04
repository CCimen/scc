---
id: T03
parent: S06
milestone: M005
key_files:
  - tests/test_function_sizes.py
  - src/scc_cli/commands/launch/flow_interactive.py
  - src/scc_cli/application/compute_effective_config.py
  - src/scc_cli/commands/reset.py
  - src/scc_cli/commands/org/update_cmd.py
key_decisions:
  - Extracted wizard step handlers as standalone functions returning union types (_PickerContinue | _PickerExit)
  - All ruff per-file-ignores confirmed permanent — no transitional ignores to remove
duration: 
verification_result: passed
completed_at: 2026-04-04T21:04:07.574Z
blocker_discovered: false
---

# T03: Removed xfail from function-size guardrail, extracted 4 oversized functions below 300-line limit, confirmed all ruff ignores are permanent

**Removed xfail from function-size guardrail, extracted 4 oversized functions below 300-line limit, confirmed all ruff ignores are permanent**

## What Happened

Four functions exceeded the 300-line function-size guardrail: interactive_start (524), compute_effective_config (424), org_update_cmd (309), and reset_cmd (308). Each was refactored by extracting cohesive helper functions: _handle_workspace_picker/_handle_workspace_source for the wizard, _merge_team_mcp_servers/_merge_project_config for config computation, _update_single_team/_update_all_teams for org update, and _execute_factory_reset for reset. The xfail marker was removed. All ruff per-file-ignores were confirmed permanent (T201 for CLI stdout, UP037 for defensive annotation).

## Verification

uv run ruff check: all checks passed. uv run mypy src/scc_cli: 0 errors in 289 files. uv run pytest tests/test_file_sizes.py tests/test_function_sizes.py -v: both pass, no xfail. uv run pytest --rootdir "$PWD" -q: 4463 passed, 23 skipped, 2 xfailed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 10400ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 5500ms |
| 3 | `uv run pytest tests/test_file_sizes.py tests/test_function_sizes.py -v` | 0 | ✅ pass | 1800ms |
| 4 | `uv run pytest --rootdir . -q` | 0 | ✅ pass | 74200ms |

## Deviations

Used NormalizedTeamConfig instead of TeamProfile for _merge_team_mcp_servers type annotation (mypy caught the mismatch). Introduced _PickerContinue/_PickerExit type aliases for wizard step handler union returns.

## Known Issues

None.

## Files Created/Modified

- `tests/test_function_sizes.py`
- `src/scc_cli/commands/launch/flow_interactive.py`
- `src/scc_cli/application/compute_effective_config.py`
- `src/scc_cli/commands/reset.py`
- `src/scc_cli/commands/org/update_cmd.py`
