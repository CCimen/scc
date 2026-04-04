---
id: T02
parent: S04
milestone: M001
key_files:
  - src/scc_cli/core/enums.py
  - src/scc_cli/core/errors.py
  - src/scc_cli/core/error_mapping.py
  - src/scc_cli/json_command.py
  - tests/test_error_mapping.py
  - tests/test_json_command.py
key_decisions:
  - Make `SCCError` subclasses the canonical source of exit-code truth instead of relying on special cases in the mapper to correct stale defaults.
  - Add a stable error category model and expose it through JSON payloads so human and machine output share the same classification semantics.
  - Introduce a `to_audit_event()` helper as the first shared audit-event direction rather than wiring an audit sink in M001.
duration: 
verification_result: passed
completed_at: 2026-04-03T15:43:13.985Z
blocker_discovered: false
---

# T02: Aligned SCCError categories and exit codes with JSON payload metadata, and added a shared audit-event mapping helper.

**Aligned SCCError categories and exit codes with JSON payload metadata, and added a shared audit-event mapping helper.**

## What Happened

I aligned the current error and output seam around one typed category model and the existing exit-code contract. The key underlying bug was that several `SCCError` subclasses carried stale exit-code defaults that disagreed with `core.exit_codes`, and the application only worked because the mapper corrected them later. I fixed that drift by importing the shared exit-code constants into `core.errors`, adding a stable `ErrorCategory` enum, setting category and aligned exit-code defaults on the exception hierarchy, and making `PolicyViolationError` explicitly governance-scoped. Then I simplified `core.error_mapping` to trust `SCCError` directly, extended JSON payloads with `error_category` and `exit_code`, added a shared `to_audit_event()` helper that emits the new `AuditEvent` contract, and updated `json_command` so error metadata is preserved in the envelope data instead of being discarded.

## Verification

Ran LSP diagnostics on the touched modules and then executed the focused error/json test suite covering the exception hierarchy, mapper behavior, JSON command envelopes, and JSON output infrastructure. All checks passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_error_mapping.py tests/test_json_command.py tests/test_json_output.py` | 0 | ✅ pass | 1248ms |

## Deviations

I kept the output contract change focused on shared metadata rather than introducing a brand-new top-level error envelope shape for decorated commands. The command kind remains stable; the new category and exit-code data now live inside the existing `data` payload.

## Known Issues

This slice aligns error categories, exit codes, and JSON payload metadata, but it does not yet route audit events to any persistent sink. The `to_audit_event()` helper defines the shared shape for later network/safety work.

## Files Created/Modified

- `src/scc_cli/core/enums.py`
- `src/scc_cli/core/errors.py`
- `src/scc_cli/core/error_mapping.py`
- `src/scc_cli/json_command.py`
- `tests/test_error_mapping.py`
- `tests/test_json_command.py`
