---
id: T11
parent: S05
milestone: M007-cqttot
key_files:
  - tests/test_oci_sandbox_runtime.py
key_decisions:
  - (none)
duration: 
verification_result: passed
completed_at: 2026-04-05T15:49:57.468Z
blocker_discovered: false
---

# T11: Added 7 OCI runtime-layer tests proving config persistence is deterministic across governed→standalone, teamA→teamB, settings→no-settings, cross-provider, and idempotent transitions

**Added 7 OCI runtime-layer tests proving config persistence is deterministic across governed→standalone, teamA→teamB, settings→no-settings, cross-provider, and idempotent transitions**

## What Happened

Added TestConfigPersistenceTransitions class to test_oci_sandbox_runtime.py with 7 tests exercising the OCI runtime's _inject_settings path across session transitions. Each test simulates two sequential launches with mock resets between and asserts the second launch writes the correct config content regardless of the first launch's config. Tests cover governed→standalone, teamA→teamB, resume skip, settings→no-settings, Codex workspace-scoped team transition, Claude→Codex cross-provider switch, and idempotent same-config writes.

## Verification

uv run pytest tests/test_oci_sandbox_runtime.py::TestConfigPersistenceTransitions -v: 7/7 passed. uv run ruff check: zero errors. uv run pytest tests/test_oci_sandbox_runtime.py tests/test_application_start_session.py -v: 110 passed. uv run pytest -q: 4811 passed, 0 failed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_oci_sandbox_runtime.py::TestConfigPersistenceTransitions -v` | 0 | ✅ pass | 4600ms |
| 2 | `uv run ruff check` | 0 | ✅ pass | 5500ms |
| 3 | `uv run pytest tests/test_oci_sandbox_runtime.py tests/test_application_start_session.py -v` | 0 | ✅ pass | 5500ms |
| 4 | `uv run pytest -q` | 0 | ✅ pass | 56500ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `tests/test_oci_sandbox_runtime.py`
