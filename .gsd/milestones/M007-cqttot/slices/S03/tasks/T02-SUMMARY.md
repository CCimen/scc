---
id: T02
parent: S03
milestone: M007-cqttot
key_files:
  - src/scc_cli/doctor/core.py
  - src/scc_cli/doctor/render.py
  - src/scc_cli/doctor/serialization.py
  - src/scc_cli/commands/admin.py
  - src/scc_cli/doctor/checks/environment.py
  - src/scc_cli/doctor/__init__.py
  - tests/test_doctor_provider_wiring.py
key_decisions:
  - Category assignment uses a name→category map in core.py with _assign_category() applied post-collection, preserving categories already set by check functions
  - Render grouping uses fixed category order (backend→provider→config→worktree→general) with bold cyan section headers
duration: 
verification_result: passed
completed_at: 2026-04-05T13:27:15.273Z
blocker_discovered: false
---

# T02: Wired --provider flag, category assignment, and grouped doctor output with 20 new tests

**Wired --provider flag, category assignment, and grouped doctor output with 20 new tests**

## What Happened

Updated six source files to wire provider-awareness through the doctor pipeline. run_doctor() now accepts provider_id and threads it to check_provider_image() and check_provider_auth(). Added _CATEGORY_MAP and _assign_category() to automatically classify checks into backend/provider/config/worktree/general categories. doctor_cmd gained a --provider flag that validates against KNOWN_PROVIDERS (exit code 2 for unknown). render_doctor_results() sorts checks by category order and inserts bold cyan section headers. build_doctor_json_data() includes category in each check dict. check_provider_auth is now re-exported from doctor/__init__.py.

## Verification

All three verification gates pass: ruff check clean, mypy 293 files no issues, pytest 4718 passed. Task-specific tests (20 in test_doctor_provider_wiring.py) all pass covering category assignment, provider threading, CLI flag validation, JSON serialization, and render grouping.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 10000ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 48000ms |
| 3 | `uv run pytest -q` | 0 | ✅ pass | 50000ms |
| 4 | `uv run pytest tests/test_doctor_provider_wiring.py -v` | 0 | ✅ pass | 1000ms |

## Deviations

Fixed pre-existing ruff import sort issue in test_doctor_provider_errors.py. CLI tests required explicit parameter passing for typer commands and click.exceptions.Exit with .exit_code attribute.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/doctor/core.py`
- `src/scc_cli/doctor/render.py`
- `src/scc_cli/doctor/serialization.py`
- `src/scc_cli/commands/admin.py`
- `src/scc_cli/doctor/checks/environment.py`
- `src/scc_cli/doctor/__init__.py`
- `tests/test_doctor_provider_wiring.py`
