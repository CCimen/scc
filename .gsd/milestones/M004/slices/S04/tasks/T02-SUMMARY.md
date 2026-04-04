---
id: T02
parent: S04
milestone: M004
key_files:
  - src/scc_cli/application/safety_audit.py
  - src/scc_cli/presentation/json/safety_audit_json.py
  - src/scc_cli/commands/support.py
  - src/scc_cli/application/support_bundle.py
  - src/scc_cli/kinds.py
  - tests/test_safety_audit.py
key_decisions:
  - Reused _tail_lines from launch audit_log for bounded reading (no full-file scan)
  - Non-safety events parsed as valid JSON are silently skipped (not counted as malformed)
  - Safety section uses _load_raw_org_config_for_bundle() indirection matching T01 doctor pattern
duration: 
verification_result: passed
completed_at: 2026-04-04T13:16:12.051Z
blocker_discovered: false
---

# T02: Added safety audit reader filtering safety.check events from JSONL sink, scc support safety-audit CLI command, support bundle safety section, and 13 tests

**Added safety audit reader filtering safety.check events from JSONL sink, scc support safety-audit CLI command, support bundle safety section, and 13 tests**

## What Happened

Created application/safety_audit.py with SafetyAuditEventRecord and SafetyAuditDiagnostics frozen dataclasses and read_safety_audit_diagnostics() that uses bounded tail-read (reuses _tail_lines from launch audit) filtering to event_type == "safety.check". Tracks blocked/allowed counts and last blocked event. Created presentation/json/safety_audit_json.py with envelope builder using Kind.SAFETY_AUDIT. Added SAFETY_AUDIT to the Kind enum. Added scc support safety-audit command in commands/support.py following the exact launch-audit pattern with --limit, --json, --pretty options. Added safety section to build_support_bundle_manifest() with effective policy (from load_safety_policy) and recent audit events, wrapped in try/except for partial results. Wrote 13 tests covering empty sink, event filtering, blocked/allowed counts, last blocked, bounded scan, malformed lines, path redaction, JSON serializable output, CLI human mode, CLI JSON mode, unavailable sink, and support bundle integration.

## Verification

All 13 targeted tests pass. ruff check clean. mypy clean (261 files). Full regression: 3790 passed, 23 skipped, 4 xfailed — zero regressions.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_safety_audit.py -v` | 0 | ✅ pass | 4700ms |
| 2 | `uv run ruff check` | 0 | ✅ pass | 5000ms |
| 3 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4400ms |
| 4 | `uv run pytest --tb=short -q` | 0 | ✅ pass | 46600ms |

## Deviations

Added extra tests beyond plan (test_redact_paths_disabled, test_to_dict_returns_serializable). Non-safety JSONL events parsed as valid JSON are silently skipped rather than counted as malformed.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/application/safety_audit.py`
- `src/scc_cli/presentation/json/safety_audit_json.py`
- `src/scc_cli/commands/support.py`
- `src/scc_cli/application/support_bundle.py`
- `src/scc_cli/kinds.py`
- `tests/test_safety_audit.py`
