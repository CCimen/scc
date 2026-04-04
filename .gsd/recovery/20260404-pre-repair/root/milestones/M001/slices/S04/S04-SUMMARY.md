---
id: S04
parent: M001
milestone: M001
provides:
  - Explicit typed seams for M002 provider/runtime work.
  - Aligned error-category and exit-code behavior across exceptions and JSON output.
  - A shared typed audit-event direction for later network and safety adoption.
requires:
  - slice: S03
    provides: Characterized launch/config/safety behavior under the truthful network vocabulary.
affects:
  []
key_files:
  - src/scc_cli/core/contracts.py
  - src/scc_cli/ports/agent_provider.py
  - src/scc_cli/core/errors.py
  - src/scc_cli/core/error_mapping.py
  - src/scc_cli/json_command.py
  - tests/test_core_contracts.py
  - tests/test_error_mapping.py
  - tests/test_json_command.py
  - .gsd/DECISIONS.md
key_decisions:
  - Introduce the M001 typed seams as a thin standalone layer rather than forcing immediate adoption into the existing Claude-shaped launch flow.
  - Make the SCCError hierarchy the canonical source of exit-code and category truth.
  - Expose `error_category` and `exit_code` in JSON error payloads while keeping the existing envelope shape stable.
  - Provide `to_audit_event()` as the first shared audit-event direction for later network and safety work.
patterns_established:
  - Introduce future architecture seams as thin typed layers first, then adopt them incrementally.
  - Keep exception classes, exit-code mapping, and JSON metadata aligned from one source of truth.
  - When adding new typed contracts, add direct contract tests rather than relying only on indirect integration coverage.
observability_surfaces:
  - New AuditEvent typed contract and `to_audit_event()` helper for later network/safety reuse.
  - JSON error payloads now include stable `error_category` and `exit_code` metadata.
  - Contract tests that lock the new typed seam and error/output behavior.
drill_down_paths:
  - .gsd/milestones/M001/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M001/slices/S04/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-03T15:47:50.871Z
blocker_discovered: false
---

# S04: Typed control-plane contracts and shared error-audit seams

**Added the typed M001 control-plane contracts and aligned the shared error/output/audit seam, then closed the slice on a clean passing gate.**

## What Happened

This slice delivered the typed foundation M001 set out to create. I added a new core contract module for RuntimeInfo, NetworkPolicyPlan, DestinationSet, EgressRule, SafetyPolicy, SafetyVerdict, AuditEvent, ProviderCapabilityProfile, and AgentLaunchSpec, plus a provider-neutral AgentProvider protocol. I also aligned the existing error/output seam by adding a stable ErrorCategory enum, fixing stale exception exit-code defaults so they match the shared exit-code contract directly, extending JSON payloads with `error_category` and `exit_code`, and adding a shared `to_audit_event()` helper. Finally, I recorded the architectural decisions in GSD, updated the active milestone context wording, and reran the full verification gate to a clean pass after fixing two small slice-local issues.

## Verification

Verified the new typed seams and aligned error/output behavior with focused contract and error/json test runs during execution, then ran the full fixed gate successfully: `uv run ruff check && uv run mypy src/scc_cli && uv run pytest`.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

The full-gate verification for T03 needed two small cleanup reruns after slice-local issues in new code: a ruff import fix in `ports/agent_provider.py` and a mypy-friendly switch from `datetime.UTC` to `timezone.utc` in the audit-event contract. Both were corrected before slice completion.

## Known Limitations

The current application flow still uses the older AgentRunner/SandboxSpec path; the new provider-neutral seam is present and tested but not adopted yet. Audit events now have a shared typed shape, but there is no persistent audit sink wired in M001.

## Follow-ups

M002 should begin adopting the new AgentProvider and AgentLaunchSpec seam in the actual launch flow. Future network and safety work can also route the new AuditEvent shape to a persistent sink once those subsystems are ready.

## Files Created/Modified

- `src/scc_cli/core/contracts.py` — Added the thin M001 typed contract layer for launch, runtime, network, safety, and audit planning.
- `src/scc_cli/ports/agent_provider.py` — Added the provider-neutral AgentProvider protocol for future launch preparation work.
- `src/scc_cli/core/__init__.py` — Exported the new core contracts from the core package.
- `src/scc_cli/core/enums.py` — Added the stable ErrorCategory enum used by errors and JSON metadata.
- `src/scc_cli/core/errors.py` — Aligned typed exception defaults with the shared exit-code contract and stable error categories.
- `src/scc_cli/core/error_mapping.py` — Aligned shared error mapping, JSON metadata, and audit-event conversion around the new category model.
- `src/scc_cli/json_command.py` — Preserved error metadata in json_command envelopes instead of discarding it.
- `tests/test_core_contracts.py` — Added focused tests for the new typed contracts and provider protocol.
- `tests/test_error_mapping.py` — Added focused tests for error-category, exit-code, JSON payload, and audit-event mapping behavior.
- `tests/test_json_command.py` — Updated JSON command tests to assert stable error metadata in the envelope data.
- `.gsd/milestones/M001-CONTEXT.md` — Updated the active milestone context wording away from the old isolated-language phrasing.
