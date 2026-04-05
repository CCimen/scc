---
id: S02
parent: M007-cqttot
milestone: M007-cqttot
provides:
  - Provider-parameterized session/audit helpers using registry
  - WorkContext with provider_id field and backward-compat serialization
  - Session list CLI with Provider column
  - Explicit provider_id='claude' recording in legacy sandbox path
requires:
  - slice: S01
    provides: ProviderRuntimeSpec registry with get_runtime_spec() fail-closed lookup and InvalidProviderError
affects:
  - S04
  - S05
key_files:
  - src/scc_cli/sessions.py
  - src/scc_cli/commands/audit.py
  - src/scc_cli/commands/launch/sandbox.py
  - src/scc_cli/contexts.py
  - src/scc_cli/commands/worktree/session_commands.py
  - tests/test_s02_provider_sessions.py
key_decisions:
  - Default parameter value 'claude' on renamed helpers preserves backward compatibility without requiring call-site migration
  - WorkContext.display_label appends provider info only for non-default providers to avoid visual noise on existing Claude sessions
patterns_established:
  - Registry-based helper pattern: shared helpers that previously hardcoded Claude paths now take provider_id and resolve via get_runtime_spec(). This pattern should be applied to any remaining Claude-named helpers in S04.
  - WorkContext provider_id threading: provider identity is now part of session context — downstream features (Quick Resume, session picker) can filter and display by provider.
observability_surfaces:
  - Session list CLI Provider column surfaces provider_id for operator visibility
  - WorkContext.display_label shows non-default provider in parentheses for Quick Resume
drill_down_paths:
  - .gsd/milestones/M007-cqttot/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M007-cqttot/slices/S02/tasks/T02-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-05T13:04:08.836Z
blocker_discovered: false
---

# S02: Session, resume, and machine-readable output provider hardening

**Provider-parameterized session, audit, and context surfaces — three Claude-named helpers renamed to registry-based lookups, sandbox records explicit provider_id, WorkContext carries and surfaces provider identity, session list CLI shows provider column.**

## What Happened

S02 eliminated three Claude-hardcoded helper functions from shared code and replaced them with provider-parameterized versions backed by the ProviderRuntimeSpec registry from S01.

**T01 — Production changes (6 files):**
- `sessions.py`: Renamed `get_claude_sessions_dir()` → `get_provider_sessions_dir(provider_id='claude')` and `get_claude_recent_sessions()` → `get_provider_recent_sessions(provider_id='claude')`. Both now resolve the sessions directory via `get_runtime_spec(provider_id).config_dir` instead of the hardcoded `AGENT_CONFIG_DIR` constant.
- `commands/audit.py`: Renamed `get_claude_dir()` → `get_provider_config_dir(provider_id='claude')` with the same registry-based resolution.
- `commands/launch/sandbox.py`: Changed `provider_id=None` to `provider_id='claude'` — the legacy sandbox path is always Claude, now explicitly recorded per D032.
- `contexts.py`: Added `provider_id: str | None = None` field to WorkContext with full backward-compatible `to_dict()`/`from_dict()` serialization. Updated `display_label` to append `(codex)` suffix for non-default providers — default Claude sessions show no extra noise.
- `session_commands.py`: Added `provider_id` to session dict output and Provider column to the responsive session list table.
- `tests/test_sessions.py`: Updated one existing test for the new column shape.

**T02 — Test coverage (21 new tests):**
Created `tests/test_s02_provider_sessions.py` with four test classes covering: provider registry lookups for session and audit config dirs (including unknown-provider error), WorkContext provider_id serialization round-trip and backward compatibility, display_label behavior with default and non-default providers, and session list CLI provider_id dict-building logic.

All three renamed helpers use `provider_id='claude'` as the default parameter, so every existing call site continues to work without modification. This is backward-compatible by design — no migration needed.

## Verification

Slice-level verification ran all three gates:

1. **ruff check** on all 7 touched files (6 production + 1 test): zero errors
2. **mypy** on all 6 production files: zero errors (Success: no issues found in 6 source files)
3. **Full pytest suite**: 4675 passed, 23 skipped, 2 xfailed — zero failures, +21 net new tests from T02

Test count progression: S01 baseline 4654 → T01 4654 (no new tests, one updated) → T02 4675 (+21 new tests).

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None. Both tasks completed exactly as planned with zero deviations.

## Known Limitations

- The renamed helpers default to `provider_id='claude'` — callers that should be explicitly provider-aware (e.g. a future Codex session list) must pass the provider_id explicitly. The defaults are a migration convenience, not a permanent architecture.
- Session list Provider column is in `wide_columns` only — narrow terminal renderings may not show it.

## Follow-ups

None.

## Files Created/Modified

- `src/scc_cli/sessions.py` — Renamed get_claude_sessions_dir → get_provider_sessions_dir and get_claude_recent_sessions → get_provider_recent_sessions, both using registry-based config_dir lookup
- `src/scc_cli/commands/audit.py` — Renamed get_claude_dir → get_provider_config_dir with registry-based config_dir lookup
- `src/scc_cli/commands/launch/sandbox.py` — Changed provider_id=None to provider_id='claude' for explicit recording
- `src/scc_cli/contexts.py` — Added provider_id field to WorkContext with backward-compat serialization and provider-aware display_label
- `src/scc_cli/commands/worktree/session_commands.py` — Added provider_id to session dicts and Provider column to session list table
- `tests/test_sessions.py` — Updated one existing test for new column shape
- `tests/test_s02_provider_sessions.py` — New: 21 tests covering all S02 production changes
