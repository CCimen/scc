---
id: T01
parent: S01
milestone: M006-d622bc
key_files:
  - src/scc_cli/core/provider_resolution.py
  - src/scc_cli/core/errors.py
  - src/scc_cli/ports/config_models.py
  - src/scc_cli/config.py
  - tests/test_provider_resolution.py
key_decisions:
  - Deferred import of ProviderNotAllowedError inside resolve_active_provider to keep the module import-free of adapters/bootstrap
duration: 
verification_result: passed
completed_at: 2026-04-04T22:51:36.764Z
blocker_discovered: false
---

# T01: Added pure provider resolver with CLI > config > default precedence, ProviderNotAllowedError, allowed_providers team config field, and selected_provider user config helpers

**Added pure provider resolver with CLI > config > default precedence, ProviderNotAllowedError, allowed_providers team config field, and selected_provider user config helpers**

## What Happened

Created provider_resolution.py in core with resolve_active_provider() implementing CLI flag > config > default ('claude') precedence. Validates against KNOWN_PROVIDERS (ValueError) and team allowed_providers policy (ProviderNotAllowedError). Added ProviderNotAllowedError to errors.py extending PolicyViolationError. Extended NormalizedTeamConfig with allowed_providers field. Added selected_provider to user config defaults with get/set helpers following the selected_profile pattern exactly.

## Verification

20/20 tests passed in test_provider_resolution.py. mypy clean on all 4 source files. ruff clean. Full suite 4509 passed, 23 skipped, 2 xfailed — no regressions.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_provider_resolution.py -v` | 0 | ✅ pass | 11300ms |
| 2 | `uv run mypy src/scc_cli/core/provider_resolution.py src/scc_cli/core/errors.py src/scc_cli/ports/config_models.py src/scc_cli/config.py` | 0 | ✅ pass | 7400ms |
| 3 | `uv run ruff check src/scc_cli/core/provider_resolution.py src/scc_cli/core/errors.py src/scc_cli/ports/config_models.py src/scc_cli/config.py` | 0 | ✅ pass | 3700ms |
| 4 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 70400ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/core/provider_resolution.py`
- `src/scc_cli/core/errors.py`
- `src/scc_cli/ports/config_models.py`
- `src/scc_cli/config.py`
- `tests/test_provider_resolution.py`
