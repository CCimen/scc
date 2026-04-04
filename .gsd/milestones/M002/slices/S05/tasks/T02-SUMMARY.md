---
id: T02
parent: S05
milestone: M002
key_files:
  - src/scc_cli/application/support_bundle.py
  - src/scc_cli/application/settings/use_cases.py
  - src/scc_cli/commands/support.py
  - src/scc_cli/ui/settings.py
  - src/scc_cli/support_bundle.py
  - tests/test_support_bundle.py
  - tests/test_application_settings.py
  - tests/test_no_root_sprawl.py
key_decisions:
  - Keep default support-bundle path calculation and default dependency wiring in `src/scc_cli/application/support_bundle.py` so callers share one real implementation.
  - Remove `src/scc_cli/support_bundle.py` outright instead of leaving a compatibility shim or root-level duplicate.
duration: 
verification_result: mixed
completed_at: 2026-04-03T21:14:34.141Z
blocker_discovered: false
---

# T02: Unified CLI and settings support-bundle generation on the application support-bundle use case.

**Unified CLI and settings support-bundle generation on the application support-bundle use case.**

## What Happened

Moved the remaining support-bundle ownership into `src/scc_cli/application/support_bundle.py` by adding the shared default-path helper and a composition-root-backed dependency builder there. Updated `src/scc_cli/commands/support.py` and `src/scc_cli/application/settings/use_cases.py` to call that application path, and updated `src/scc_cli/ui/settings.py` to use the same default-path helper the CLI uses. Deleted `src/scc_cli/support_bundle.py` instead of leaving a wrapper. Rewrote the focused tests to target the application module directly, added settings-action coverage that proves the settings screen routes through `create_support_bundle(...)`, and tightened guardrails with root-sprawl coverage plus a source-scan test that fails if production code imports the removed module again. The T01 launch-audit manifest section stays on the shared path because both callers now converge on the same application-owned manifest builder and archive writer flow.

## Verification

Ran `uv run pytest --rootdir "$PWD" ./tests/test_application_settings.py ./tests/test_support_bundle.py ./tests/test_no_root_sprawl.py -q` and all 32 focused tests passed. Ran targeted `ruff check` on the changed files; it passed. Ran `uv run mypy src/scc_cli`; it passed. Ran `uv run pytest`; the full suite passed (`3249 passed, 23 skipped, 4 xfailed`). Ran repo-wide `uv run ruff check`; it still fails, but only in unrelated pre-existing test files outside this task.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest --rootdir "$PWD" ./tests/test_application_settings.py ./tests/test_support_bundle.py ./tests/test_no_root_sprawl.py -q` | 0 | ✅ pass | 13700ms |
| 2 | `uv run ruff check src/scc_cli/application/support_bundle.py src/scc_cli/application/settings/use_cases.py src/scc_cli/commands/support.py src/scc_cli/ui/settings.py tests/test_support_bundle.py tests/test_application_settings.py tests/test_no_root_sprawl.py` | 0 | ✅ pass | 4900ms |
| 3 | `uv run ruff check` | 1 | ❌ fail | 41400ms |
| 4 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 41400ms |
| 5 | `uv run pytest` | 0 | ✅ pass | 41400ms |

## Deviations

None.

## Known Issues

`uv run ruff check` is still red at the repo level because of unrelated pre-existing violations in other test files. The files touched by this task pass targeted ruff.

## Files Created/Modified

- `src/scc_cli/application/support_bundle.py`
- `src/scc_cli/application/settings/use_cases.py`
- `src/scc_cli/commands/support.py`
- `src/scc_cli/ui/settings.py`
- `src/scc_cli/support_bundle.py`
- `tests/test_support_bundle.py`
- `tests/test_application_settings.py`
- `tests/test_no_root_sprawl.py`
