---
id: T01
parent: S01
milestone: M007-cqttot
key_files:
  - src/scc_cli/core/contracts.py
  - src/scc_cli/core/errors.py
  - src/scc_cli/provider_registry.py
  - tests/test_provider_registry.py
key_decisions:
  - ProviderRuntimeSpec placed in core/contracts.py next to ProviderCapabilityProfile
  - InvalidProviderError inherits from SCCError directly with exit_code=2
  - provider_registry.py at composition layer — imports only from core
  - settings_path uses relative paths; container-absolute prefix applied at call site
duration: 
verification_result: passed
completed_at: 2026-04-05T12:25:38.612Z
blocker_discovered: false
---

# T01: Added ProviderRuntimeSpec frozen dataclass, InvalidProviderError, and provider_registry module with fail-closed lookup and 11-test suite

**Added ProviderRuntimeSpec frozen dataclass, InvalidProviderError, and provider_registry module with fail-closed lookup and 11-test suite**

## What Happened

Added ProviderRuntimeSpec frozen dataclass to core/contracts.py with six typed fields (provider_id, display_name, image_ref, config_dir, settings_path, data_volume). Added InvalidProviderError(SCCError) to core/errors.py with exit_code=2 and auto-populated user_message/suggested_action. Created provider_registry.py at the composition layer with PROVIDER_REGISTRY dict (claude and codex entries matching current scattered dicts) and get_runtime_spec() fail-closed lookup. Wrote 11 tests covering field correctness, error raising, message content, registry integrity, coexistence uniqueness, and immutability.

## Verification

All three verification commands pass cleanly: pytest 11/11 passed, mypy clean on all 3 source files, ruff clean on provider_registry.py.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_provider_registry.py -v` | 0 | ✅ pass | 11200ms |
| 2 | `uv run mypy src/scc_cli/provider_registry.py src/scc_cli/core/contracts.py src/scc_cli/core/errors.py` | 0 | ✅ pass | 5100ms |
| 3 | `uv run ruff check src/scc_cli/provider_registry.py` | 0 | ✅ pass | 2400ms |

## Deviations

Added 3 extra tests beyond the 8 specified (test_spec_is_frozen, test_invalid_provider_error_suggested_action, test_empty_string_provider_raises) for stronger contract coverage. settings_path uses relative path — container-absolute prefix applied at call site per existing pattern.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/core/contracts.py`
- `src/scc_cli/core/errors.py`
- `src/scc_cli/provider_registry.py`
- `tests/test_provider_registry.py`
