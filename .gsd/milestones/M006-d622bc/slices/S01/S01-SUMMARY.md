---
id: S01
parent: M006-d622bc
milestone: M006-d622bc
provides:
  - resolve_active_provider() for downstream launch path consumers
  - provider_id field on StartSessionRequest for S02/S03/S04
  - _PROVIDER_DISPATCH table for S02 to add CodexAgentRunner mapping
  - allowed_providers field on NormalizedTeamConfig for policy enforcement
  - scc provider show/set commands for user configuration
requires:
  []
affects:
  - S02
  - S03
  - S04
key_files:
  - src/scc_cli/core/provider_resolution.py
  - src/scc_cli/core/errors.py
  - src/scc_cli/ports/config_models.py
  - src/scc_cli/config.py
  - src/scc_cli/commands/provider.py
  - src/scc_cli/cli.py
  - src/scc_cli/application/start_session.py
  - src/scc_cli/commands/launch/dependencies.py
  - src/scc_cli/commands/launch/flow.py
  - tests/test_provider_resolution.py
  - tests/test_provider_commands.py
  - tests/test_provider_dispatch.py
key_decisions:
  - D026: Provider selection flows CLI flag > config > default, with policy validation against team allowed_providers
  - D028 constraint 2 enforced: provider dispatch is request-scoped in build_start_session_dependencies(), not baked into lru_cached DefaultAdapters
  - Dict-based _PROVIDER_DISPATCH table for O(1) provider→adapter field mapping — avoids if/else chains as providers grow
patterns_established:
  - resolve_active_provider() is a pure function in core — no imports from adapters or bootstrap
  - Provider config helpers follow the exact selected_profile pattern: get_selected_provider()/set_selected_provider()
  - Provider CLI commands follow the profile_app pattern with handle_errors decorator
  - _PROVIDER_DISPATCH dict maps provider_id to DefaultAdapters field names for O(1) lookup
  - _resolve_provider() helper keeps start() under the 300-line guardrail while handling OptionInfo normalization
observability_surfaces:
  - scc provider show prints the active provider
  - ProviderNotAllowedError includes user_message with the blocked provider and suggested_action listing allowed providers
drill_down_paths:
  - .gsd/milestones/M006-d622bc/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M006-d622bc/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M006-d622bc/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-04T23:17:37.002Z
blocker_discovered: false
---

# S01: Provider selection config, CLI flag, and bootstrap dispatch

**Provider selection flows from user intent (CLI flag, config, default) through policy validation to request-scoped adapter dispatch in the launch path.**

## What Happened

S01 established the complete provider selection pipeline across three tasks.

**T01 — Pure provider resolver.** Created `core/provider_resolution.py` with `resolve_active_provider()` implementing CLI flag > config > default ('claude') precedence. Added `ProviderNotAllowedError` to `core/errors.py` extending `PolicyViolationError`, with auto-generated user_message and suggested_action. Extended `NormalizedTeamConfig` with `allowed_providers: tuple[str, ...]` field (empty = all allowed, matching the `blocked_plugins` pattern). Added `selected_provider` to user config defaults with `get_selected_provider()`/`set_selected_provider()` helpers following the exact `selected_profile` pattern. 20 tests.

**T02 — CLI surface.** Created `commands/provider.py` with `scc provider show` and `scc provider set` commands following the `profile_app` pattern. Registered in `cli.py` under the Configuration panel. Added `provider_id: str | None = None` to `StartSessionRequest`. Added `--provider` option to `start()` in `flow.py`, threading it into the request. 9 tests. Fixed two pre-existing ruff I001 import-sorting violations.

**T03 — Launch path wiring.** Updated `build_start_session_dependencies()` to accept `provider_id` and dispatch the correct `agent_provider` from `DefaultAdapters` using a `_PROVIDER_DISPATCH` dict-based lookup table. Wired `resolve_active_provider()` into `flow.py`'s `start()` before request building, extracting `allowed_providers` from team config. Extracted `_resolve_provider()` helper to keep `start()` under the 300-line function size guardrail. Added `isinstance(provider, str)` guard to normalize typer `OptionInfo` objects that appear when testing commands via direct function calls. 11 tests.

All work stays within D028 constraints: shared infra (probe, engine, sink) remains in the lru_cached `DefaultAdapters` singleton; provider-specific adapters are selected per invocation in `build_start_session_dependencies()`. Safety adapter dispatch is recorded in the dispatch table but not yet threaded into `StartSessionDependencies` — deferred to S04.

## Verification

All verification gates pass:
- `uv run pytest tests/test_provider_resolution.py tests/test_provider_commands.py tests/test_provider_dispatch.py -v`: 40/40 passed
- `uv run ruff check`: clean (0 errors)
- `uv run mypy src/scc_cli/core/provider_resolution.py src/scc_cli/core/errors.py src/scc_cli/ports/config_models.py src/scc_cli/config.py src/scc_cli/commands/provider.py src/scc_cli/application/start_session.py src/scc_cli/commands/launch/dependencies.py src/scc_cli/commands/launch/flow.py`: Success, no issues found in 8 source files
- `uv run pytest --rootdir "$PWD" -q`: 4529 passed, 23 skipped, 2 xfailed — zero regressions
- 100% coverage on new modules: provider_resolution.py, provider.py, dependencies.py

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

T03 extracted `_resolve_provider()` helper from `start()` (not in plan) to satisfy the 300-line function size guardrail. T03 added `isinstance(provider, str)` guard to normalize typer OptionInfo defaults for direct-call test compatibility. Safety adapter dispatch recorded in dispatch table but not threaded into StartSessionDependencies — deferred to S04 per plan constraints.

## Known Limitations

Safety adapter dispatch is in the _PROVIDER_DISPATCH table but not yet consumed by StartSessionDependencies — S04 will complete that wiring. CodexAgentRunner does not exist yet — S02's scope. The `--provider` flag is not yet surfaced in dry-run JSON, support bundle, audit events, or session list output — D028 constraint 3, deferred to S04.

## Follow-ups

S02: Build CodexAgentRunner and provider-aware image selection. S03: Adapt all user-facing strings to the active provider. S04: Thread safety adapter dispatch, add provider_id to machine-readable outputs, coexistence testing.

## Files Created/Modified

- `src/scc_cli/core/provider_resolution.py` — New module: resolve_active_provider() with CLI > config > default precedence, KNOWN_PROVIDERS constant
- `src/scc_cli/core/errors.py` — Added ProviderNotAllowedError extending PolicyViolationError with auto-generated user_message/suggested_action
- `src/scc_cli/ports/config_models.py` — Added allowed_providers: tuple[str, ...] = () to NormalizedTeamConfig
- `src/scc_cli/config.py` — Added selected_provider to USER_CONFIG_DEFAULTS, get_selected_provider(), set_selected_provider()
- `src/scc_cli/commands/provider.py` — New module: provider_app with show and set commands
- `src/scc_cli/cli.py` — Registered provider_app under Configuration panel
- `src/scc_cli/application/start_session.py` — Added provider_id: str | None = None to StartSessionRequest
- `src/scc_cli/commands/launch/dependencies.py` — Added provider_id parameter to build_start_session_dependencies() with _PROVIDER_DISPATCH dict-based adapter dispatch
- `src/scc_cli/commands/launch/flow.py` — Added --provider option to start(), extracted _resolve_provider() helper, wired resolve_active_provider() into launch path
- `tests/test_provider_resolution.py` — 20 tests covering resolver, error, config helpers, and team config field
- `tests/test_provider_commands.py` — 9 tests covering show/set commands, start request field, help display
- `tests/test_provider_dispatch.py` — 11 tests covering dispatch table, policy validation, and provider resolution in flow
