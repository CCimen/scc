---
id: S01
parent: M007-cqttot
milestone: M007-cqttot
provides:
  - ProviderRuntimeSpec frozen dataclass in core/contracts.py
  - PROVIDER_REGISTRY dict in core/provider_registry.py
  - get_runtime_spec() fail-closed lookup function
  - InvalidProviderError in core/errors.py
requires:
  []
affects:
  - S02
  - S03
  - S04
key_files:
  - src/scc_cli/core/contracts.py
  - src/scc_cli/core/errors.py
  - src/scc_cli/core/provider_registry.py
  - src/scc_cli/application/start_session.py
  - src/scc_cli/commands/launch/dependencies.py
  - src/scc_cli/doctor/checks/environment.py
  - tests/test_provider_registry.py
key_decisions:
  - D043: provider_registry.py moved to core/ (from planned package root) to satisfy test_no_root_sprawl guardrail
  - Settings path resolution uses request.provider_id rather than adapter self-reported ID
  - Doctor check_provider_image gracefully falls back to claude image for unknown providers (diagnostic path per D032)
patterns_established:
  - ProviderRuntimeSpec as the single source of truth for provider runtime details — replaces 5 scattered dicts
  - get_runtime_spec() fail-closed lookup with InvalidProviderError — the pattern for all future provider runtime data access
  - Registry guardrail test: test_registry_keys_match_known_providers ensures PROVIDER_REGISTRY stays in sync with KNOWN_PROVIDERS
observability_surfaces:
  - InvalidProviderError carries provider_id and known_providers tuple for actionable error messages
  - get_runtime_spec() raises with full context (unknown ID + list of valid providers) — no silent fallback
drill_down_paths:
  - .gsd/milestones/M007-cqttot/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M007-cqttot/slices/S01/tasks/T02-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-05T12:40:15.897Z
blocker_discovered: false
---

# S01: ProviderRuntimeSpec model, fail-closed dispatch, and settings-path fix

**Replaced 5 scattered provider dicts with a single ProviderRuntimeSpec registry, fixed the hardcoded Claude settings path bug, and made unknown providers fail closed with InvalidProviderError.**

## What Happened

This slice consolidated scattered provider runtime data into a single typed registry and fixed a correctness bug where Codex would receive Claude's settings path.

**T01 — Foundation types and registry module.** Added `ProviderRuntimeSpec` frozen dataclass to `core/contracts.py` with six typed fields (provider_id, display_name, image_ref, config_dir, settings_path, data_volume). Added `InvalidProviderError(SCCError)` to `core/errors.py` with exit_code=2 and auto-populated user_message/suggested_action. Created `core/provider_registry.py` with `PROVIDER_REGISTRY` dict (claude and codex entries) and `get_runtime_spec()` fail-closed lookup. Wrote 11 tests covering field correctness, error messages, registry integrity, coexistence uniqueness, and immutability. The module was initially planned for package root but was placed in `core/` to satisfy the existing `test_no_root_sprawl` guardrail (recorded as D043).

**T02 — Consumer migration and bug fix.** Removed `_PROVIDER_IMAGE_REF`, `_PROVIDER_DATA_VOLUME`, `_PROVIDER_CONFIG_DIR` dicts from `start_session.py`. Wired `_build_sandbox_spec` to use `get_runtime_spec()` for image, volume, and config dir lookups. Fixed the settings path bug: `_build_agent_settings` now uses `spec.settings_path` from the registry instead of the hardcoded `.claude/settings.json`, so Codex correctly gets `.codex/config.toml`. Made `dependencies.py` fail closed — unknown `provider_id` raises `InvalidProviderError` instead of silently falling back to Claude. Updated doctor's `check_provider_image` to use the registry with diagnostic-safe fallback (per D032). Flipped 4 tests from asserting Claude fallback to asserting `InvalidProviderError`. Updated coexistence tests to import from `PROVIDER_REGISTRY`. Full suite passes with zero regressions (4654 passed).

## Verification

All slice-level verification gates pass:

1. **Targeted tests** (86 passed): `uv run pytest tests/test_provider_registry.py tests/test_provider_dispatch.py tests/test_provider_coexistence.py tests/test_application_start_session.py tests/test_doctor_image_check.py -v` — all pass
2. **Type checking**: `uv run mypy src/scc_cli/core/contracts.py src/scc_cli/core/errors.py src/scc_cli/core/provider_registry.py src/scc_cli/application/start_session.py src/scc_cli/commands/launch/dependencies.py src/scc_cli/doctor/checks/environment.py` — Success: no issues found in 6 source files
3. **Lint**: `uv run ruff check` on all touched files — All checks passed
4. **Full suite**: `uv run pytest -q` — 4654 passed, 23 skipped, 2 xfailed (zero regressions vs M006 baseline of 4643, +11 new registry tests)

## Requirements Advanced

- R001 — Replaced 5 scattered dicts with a single typed registry, improving cohesion and reducing drift risk when adding providers. 11 new tests cover the registry contract.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

1. `provider_registry.py` placed in `core/` instead of package root as D034 specified — the `test_no_root_sprawl` guardrail rejects new top-level modules. Recorded as D043.
2. Settings path resolution uses `request.provider_id` rather than adapter self-reported ID to avoid breaking tests that use FakeAgentProvider.
3. T01 added 3 extra tests beyond the 8 specified (test_spec_is_frozen, test_invalid_provider_error_suggested_action, test_empty_string_provider_raises) for stronger contract coverage.

## Known Limitations

None.

## Follow-ups

None.

## Files Created/Modified

- `src/scc_cli/core/contracts.py` — Added ProviderRuntimeSpec frozen dataclass with 6 typed fields
- `src/scc_cli/core/errors.py` — Added InvalidProviderError(SCCError) with exit_code=2 and auto-populated messages
- `src/scc_cli/core/provider_registry.py` — New module: PROVIDER_REGISTRY dict + get_runtime_spec() fail-closed lookup
- `src/scc_cli/application/start_session.py` — Removed 3 scattered dicts, wired to registry lookups, fixed settings path bug
- `src/scc_cli/commands/launch/dependencies.py` — Made unknown provider_id fail closed with InvalidProviderError
- `src/scc_cli/doctor/checks/environment.py` — Updated check_provider_image to use registry with diagnostic-safe fallback
- `tests/test_provider_registry.py` — 11 tests covering registry fields, errors, integrity, coexistence, and immutability
- `tests/test_provider_dispatch.py` — Flipped 2 fallback tests to assert InvalidProviderError
- `tests/test_provider_coexistence.py` — Updated imports from scattered dicts to PROVIDER_REGISTRY
- `tests/test_application_start_session.py` — Flipped 1 fallback test to assert InvalidProviderError
- `tests/test_doctor_image_check.py` — Updated for registry-based image lookup
