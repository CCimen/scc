---
id: T02
parent: S01
milestone: M007-cqttot
key_files:
  - src/scc_cli/core/provider_registry.py
  - src/scc_cli/application/start_session.py
  - src/scc_cli/commands/launch/dependencies.py
  - src/scc_cli/doctor/checks/environment.py
  - tests/test_provider_dispatch.py
  - tests/test_provider_coexistence.py
  - tests/test_application_start_session.py
  - tests/test_provider_registry.py
  - tests/test_provider_branding.py
key_decisions:
  - provider_registry.py moved to core/ to satisfy no-root-sprawl guardrail
  - Settings path resolution uses request.provider_id rather than adapter self-reported ID
  - Doctor check_provider_image gracefully falls back to claude image for unknown providers (diagnostic path per D032)
duration: 
verification_result: passed
completed_at: 2026-04-05T12:35:40.217Z
blocker_discovered: false
---

# T02: Replaced all 5 scattered provider dicts with PROVIDER_REGISTRY lookups, fixed hardcoded Claude settings path, made unknown providers fail-closed, and flipped 4 fallback tests

**Replaced all 5 scattered provider dicts with PROVIDER_REGISTRY lookups, fixed hardcoded Claude settings path, made unknown providers fail-closed, and flipped 4 fallback tests**

## What Happened

Removed _PROVIDER_IMAGE_REF, _PROVIDER_DATA_VOLUME, and _PROVIDER_CONFIG_DIR dicts from start_session.py and replaced all usages with get_runtime_spec() lookups from the canonical registry in core/provider_registry.py. Fixed the hardcoded settings path bug: _build_agent_settings now uses spec.settings_path from the registry. Made dependencies.py fail-closed with InvalidProviderError. Updated doctor's check_provider_image to use registry with diagnostic-safe fallback. Flipped 4 tests from asserting Claude fallback to asserting InvalidProviderError. Updated coexistence tests to import from PROVIDER_REGISTRY. Moved provider_registry.py to core/ to satisfy the no-root-sprawl guardrail.

## Verification

All three verification gates pass: uv run ruff check (clean), uv run mypy on 6 source files (clean), uv run pytest -q (4654 passed, 23 skipped, 2 xfailed). Targeted test run of 107 tests across 7 test files all pass.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 2400ms |
| 2 | `uv run mypy (6 source files)` | 0 | ✅ pass | 2400ms |
| 3 | `uv run pytest tests/test_provider_dispatch.py tests/test_provider_coexistence.py tests/test_application_start_session.py tests/test_doctor_image_check.py tests/test_provider_registry.py tests/test_no_root_sprawl.py tests/test_provider_branding.py -v` | 0 | ✅ pass | 1130ms |
| 4 | `uv run pytest -q` | 0 | ✅ pass | 47400ms |

## Deviations

Moved provider_registry.py from root to core/ to satisfy test_no_root_sprawl guardrail. Settings path resolution uses request.provider_id (defaulting to "claude") instead of adapter self-reported ID to avoid breaking tests with FakeAgentProvider. Added missing import pytest to test_application_start_session.py.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/core/provider_registry.py`
- `src/scc_cli/application/start_session.py`
- `src/scc_cli/commands/launch/dependencies.py`
- `src/scc_cli/doctor/checks/environment.py`
- `tests/test_provider_dispatch.py`
- `tests/test_provider_coexistence.py`
- `tests/test_application_start_session.py`
- `tests/test_provider_registry.py`
- `tests/test_provider_branding.py`
