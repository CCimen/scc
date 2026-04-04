---
id: S04
parent: M004
milestone: M004
provides:
  - Fail-closed SafetyPolicy loader (core/safety_policy_loader.py) usable by any module needing effective policy
  - Doctor safety-policy check for operator health diagnostics
  - Bounded safety audit reader for JSONL sink inspection
  - scc support safety-audit CLI command for operator troubleshooting
  - Support bundle safety section for comprehensive diagnostics
requires:
  - slice: S02
    provides: Runtime wrapper baseline in scc-base and canonical JSONL audit sink
  - slice: S03
    provides: Provider safety adapters emitting safety.check AuditEvents to the JSONL sink
affects:
  - S05
key_files:
  - src/scc_cli/core/safety_policy_loader.py
  - src/scc_cli/doctor/checks/safety.py
  - src/scc_cli/doctor/checks/__init__.py
  - src/scc_cli/doctor/core.py
  - src/scc_cli/application/safety_audit.py
  - src/scc_cli/presentation/json/safety_audit_json.py
  - src/scc_cli/commands/support.py
  - src/scc_cli/application/support_bundle.py
  - src/scc_cli/kinds.py
  - tests/test_safety_policy_loader.py
  - tests/test_safety_doctor_check.py
  - tests/test_safety_audit.py
key_decisions:
  - Used raw config.load_cached_org_config() for doctor check — NormalizedOrgConfig strips safety_net
  - Duplicated validation logic from docker.launch to preserve core→docker import boundary
  - Reused _tail_lines from launch audit_log for bounded reading (no full-file scan)
  - Non-safety JSONL events parsed as valid JSON are silently skipped (not counted as malformed)
  - Safety bundle section uses _load_raw_org_config_for_bundle() indirection matching T01 doctor pattern
patterns_established:
  - Fail-closed typed policy loader pattern: extract from raw config, validate strictly, return default on any failure
  - Doctor check pattern for safety subsystems: probe via bootstrap → report PASS/WARNING/ERROR with fix hints
  - Safety audit reader pattern: bounded tail-read from canonical JSONL sink filtered by event_type, with redaction and serialization
  - CLI diagnostic command pattern: follow launch-audit command's --limit/--json/--pretty shape for all new audit surfaces
  - Support bundle safety section: effective policy + recent audit events, wrapped in try/except for partial results
observability_surfaces:
  - scc doctor safety-policy check (PASS/WARNING/ERROR for org config and safety policy validity)
  - scc support safety-audit CLI command (human and JSON modes with --limit, --json, --pretty)
  - Support bundle manifest safety section (effective policy summary + recent safety audit events)
drill_down_paths:
  - .gsd/milestones/M004/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M004/slices/S04/tasks/T02-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-04T13:20:54.513Z
blocker_discovered: false
---

# S04: Fail-closed policy loading, audit surfaces, and operator diagnostics

**Delivered fail-closed typed SafetyPolicy loader, doctor safety-policy check, bounded safety audit reader over the canonical JSONL sink, `scc support safety-audit` CLI command, support bundle safety section, and 57 new tests.**

## What Happened

S04 closes the operator-facing diagnostic gap for the M004 safety engine by adding three surfaces: typed policy loading, health checking, and audit inspection.

**T01 — Fail-closed SafetyPolicy loader and doctor check (31 tests)**

Created `core/safety_policy_loader.py` with `load_safety_policy(org_config: dict | None) -> SafetyPolicy` that extracts `security.safety_net` from raw org config dicts and returns a typed SafetyPolicy. Fail-closed: any parse error, missing key, or invalid action value falls back to default `SafetyPolicy(action="block")`. The module intentionally duplicates ~10 lines of validation from `docker.launch` to preserve the core→docker import boundary, enforced by a tokenize-based guardrail test.

Created `doctor/checks/safety.py` with `check_safety_policy() -> CheckResult` that probes org config via `bootstrap.get_default_adapters()` (per KNOWLEDGE.md rule) and reports PASS/WARNING/ERROR. Uses raw `config.load_cached_org_config()` because NormalizedOrgConfig strips the safety_net section. The `_load_raw_org_config()` indirection enables clean mock patching.

Registered the check in `doctor/checks/__init__.py` and `doctor/core.py`. Wrote 24 loader tests and 7 doctor tests covering all branches: None config, empty dict, missing keys, valid actions, invalid actions, rules extraction, non-dict input, and the import guardrail.

**T02 — Safety audit reader, CLI command, and support bundle section (13 tests)**

Created `application/safety_audit.py` with frozen dataclasses `SafetyAuditEventRecord` and `SafetyAuditDiagnostics`, plus `read_safety_audit_diagnostics()` that uses bounded tail-read (reuses `_tail_lines` from launch audit) filtering to `event_type == "safety.check"` only. Tracks blocked/allowed counts and last blocked event. Path redaction replaces home directory with `~`.

Added `SAFETY_AUDIT` kind to the enum. Created `presentation/json/safety_audit_json.py` with envelope builder. Added `scc support safety-audit` CLI command following the exact `launch-audit` pattern with `--limit`, `--json`, `--pretty` options and human/JSON modes.

Added `safety` section to `build_support_bundle_manifest()` with effective policy summary (via `load_safety_policy()`) and recent safety audit events (via `read_safety_audit_diagnostics(limit=5)`), wrapped in try/except for partial results.

Wrote 13 tests covering empty sink, event filtering, blocked/allowed counts, bounded scan, malformed lines, path redaction, JSON serialization, CLI human/JSON modes, unavailable sink, and support bundle integration.

## Verification

All verification gates passed:

1. **Slice-specific tests (44 tests):** `uv run pytest tests/test_safety_policy_loader.py tests/test_safety_doctor_check.py tests/test_safety_audit.py -v` — 44 passed
2. **Ruff check:** `uv run ruff check` — All checks passed
3. **Mypy check:** `uv run mypy src/scc_cli` — Success: no issues found in 261 source files
4. **Docker import guardrail:** `grep -r 'from scc_cli.docker' src/scc_cli/core/safety_policy_loader.py` — exit 1 (no matches, as expected)
5. **Full regression:** `uv run pytest --rootdir "$PWD" --tb=short -q` — 3790 passed, 23 skipped, 4 xfailed (+44 net new tests from S03's 3746 baseline)

## Requirements Advanced

- R001 — S04 decomposed safety policy loading into a focused core module, added doctor check through bootstrap boundary, and built audit reader reusing existing bounded-read infrastructure — all following established clean architecture patterns in touched files

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Minor deviations from plan, all additive:
- T01 added extra tests beyond plan: non-dict fallbacks, missing-action fallback, source field, parametrized return-type invariant (24 vs planned 11)
- T01 used `_load_raw_org_config()` indirection instead of function-body import for doctor check testability
- T02 added extra tests (test_redact_paths_disabled, test_to_dict_returns_serializable) — 13 vs planned 8
- T02 treats non-safety JSONL events as valid JSON silently skipped (not counted as malformed)

## Known Limitations

None. All planned capabilities delivered and verified.

## Follow-ups

None.

## Files Created/Modified

- `src/scc_cli/core/safety_policy_loader.py` — New: fail-closed typed SafetyPolicy loader from raw org config dicts
- `src/scc_cli/doctor/checks/safety.py` — New: doctor check_safety_policy() probing org config via bootstrap
- `src/scc_cli/doctor/checks/__init__.py` — Modified: registered check_safety_policy in run_all_checks() and __all__
- `src/scc_cli/doctor/core.py` — Modified: call check_safety_policy() in run_doctor()
- `src/scc_cli/application/safety_audit.py` — New: bounded safety audit reader with SafetyAuditDiagnostics and event filtering
- `src/scc_cli/presentation/json/safety_audit_json.py` — New: JSON envelope builder for safety audit diagnostics
- `src/scc_cli/commands/support.py` — Modified: added scc support safety-audit CLI command
- `src/scc_cli/application/support_bundle.py` — Modified: added safety section to build_support_bundle_manifest()
- `src/scc_cli/kinds.py` — Modified: added SAFETY_AUDIT kind to enum
- `tests/test_safety_policy_loader.py` — New: 24 tests for fail-closed policy loader
- `tests/test_safety_doctor_check.py` — New: 7 tests for doctor safety-policy check
- `tests/test_safety_audit.py` — New: 13 tests for safety audit reader, CLI command, and support bundle integration
