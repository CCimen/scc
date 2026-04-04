---
id: S03
parent: M004
milestone: M004
provides:
  - SafetyCheckResult dataclass for downstream diagnostic and UI consumption
  - SafetyAdapter protocol for provider-specific safety check abstraction
  - ClaudeSafetyAdapter and CodexSafetyAdapter wired in bootstrap
  - FakeSafetyAdapter for downstream test code
requires:
  - slice: S01
    provides: SafetyEngine protocol, DefaultSafetyEngine, SafetyVerdict, SafetyPolicy, FakeSafetyEngine
  - slice: S02
    provides: Runtime wrapper baseline establishing the 7-tool scope and defense-in-depth pattern
affects:
  - S04
  - S05
key_files:
  - src/scc_cli/core/contracts.py
  - src/scc_cli/ports/safety_adapter.py
  - src/scc_cli/adapters/claude_safety_adapter.py
  - src/scc_cli/adapters/codex_safety_adapter.py
  - src/scc_cli/bootstrap.py
  - tests/fakes/fake_safety_adapter.py
  - tests/fakes/__init__.py
  - tests/test_claude_safety_adapter.py
  - tests/test_codex_safety_adapter.py
  - tests/test_safety_adapter_audit.py
key_decisions:
  - SafetyCheckResult placed in contracts.py alongside SafetyVerdict to keep safety-domain types co-located
  - Adapter metadata values are all stringified (dict[str, str]) for safe AuditEvent serialization
  - Shared engine/sink local variables in get_default_adapters() to avoid duplicate instances across safety_engine and both adapter constructors
  - FakeSafetyAdapter defaults to allowed/no-audit matching the FakeSafetyEngine allow-all convention
patterns_established:
  - SafetyAdapter protocol follows the same 4-touch-point wiring pattern as AgentProvider: adapter file → bootstrap import+field+instantiation → fakes factory → inline test constructions
  - Provider safety adapters are pure UX/audit wrappers with zero verdict logic — engine is the single source of safety truth
  - Blocked commands → WARNING audit severity, allowed commands → INFO audit severity as the standard adapter audit pattern
observability_surfaces:
  - AuditEvent emission with provider-specific metadata (provider_id, command, verdict_allowed, matched_rule, command_family) on every safety check
drill_down_paths:
  - .gsd/milestones/M004/slices/S03/tasks/T01-SUMMARY.md
  - .gsd/milestones/M004/slices/S03/tasks/T02-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-04T12:51:24.616Z
blocker_discovered: false
---

# S03: Claude and Codex UX/audit adapters over the shared engine

**Delivered provider-specific Claude and Codex safety adapters that wrap the shared SafetyEngine with UX-formatted user messages and structured AuditEvent emission, wired through bootstrap with 20 new tests (12 unit + 8 integration).**

## What Happened

S03 built the provider-specific UX and audit layer on top of the shared SafetyEngine delivered in S01. The slice introduced three new architectural elements:

**1. SafetyCheckResult contract (contracts.py).** A frozen dataclass with `verdict: SafetyVerdict`, `user_message: str`, and `audit_emitted: bool`. Placed alongside SafetyVerdict to keep safety-domain types co-located. This is the return type for all adapter-level safety checks — downstream consumers (S04 diagnostics, future UI surfaces) work with this instead of raw verdicts.

**2. SafetyAdapter protocol and two implementations.** The SafetyAdapter protocol in `ports/safety_adapter.py` defines `check_command(command, policy) -> SafetyCheckResult`. ClaudeSafetyAdapter and CodexSafetyAdapter each take a SafetyEngine and AuditEventSink at construction, delegate verdict logic entirely to engine.evaluate(), emit a structured AuditEvent with provider-specific metadata (all values stringified as `dict[str, str]` for safe serialization), and return a SafetyCheckResult with provider-prefixed user messages (`[Claude] Command blocked: ...` / `[Codex] Command allowed`).

Key design: adapters contain zero verdict logic — they are pure UX/audit wrappers. The engine is the single source of safety truth. Blocked commands emit WARNING-severity audit events; allowed commands emit INFO. Metadata includes provider_id, command, verdict_allowed, matched_rule, and command_family.

**3. Bootstrap wiring and test infrastructure.** DefaultAdapters gained `claude_safety_adapter` and `codex_safety_adapter` fields (both `SafetyAdapter | None = None` for backward compatibility). `get_default_adapters()` was refactored to share engine and sink local variables across safety_engine and both adapter constructors — no duplicate instances. FakeSafetyAdapter was added to `tests/fakes/` with configurable result and call recording, and wired into `build_fake_adapters()`.

**Test coverage.** 12 unit tests (6 per adapter) cover engine delegation, audit event severity, user message formatting, and the audit_emitted flag. 8 integration tests exercise the full engine → adapter → audit event chain for both providers, including shared-engine verdict consistency, metadata string-type enforcement, and bootstrap field verification. All 20 tests pass alongside the full 3746 regression suite.

## Verification

All four verification gates passed:
1. `uv run pytest tests/test_claude_safety_adapter.py tests/test_codex_safety_adapter.py tests/test_safety_adapter_audit.py -v` — 20/20 passed
2. `uv run ruff check` — clean
3. `uv run mypy src/scc_cli` — clean (257 source files, 0 issues)
4. `uv run pytest --rootdir "$PWD" -q` — 3746 passed, 23 skipped, 4 xfailed (above 3726 baseline, +20 net new tests)

## Requirements Advanced

- R001 — Safety adapter layer decomposed into focused protocol + two small adapters (47 lines each) with dedicated test files; bootstrap wiring uses shared instances; zero verdict logic duplication between adapters.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

Minor: ruff import-sort auto-fix needed on bootstrap.py after inserting new adapter imports. No plan-level deviation.

## Known Limitations

None. Both adapters are fully functional and tested. The `| None = None` defaults on DefaultAdapters fields mean existing construction sites that don't know about safety adapters continue to work without breakage.

## Follow-ups

S04 will wire fail-closed policy loading and expose audit surfaces/diagnostics that consume SafetyCheckResult from these adapters.

## Files Created/Modified

- `src/scc_cli/core/contracts.py` — Added SafetyCheckResult frozen dataclass with verdict, user_message, audit_emitted fields
- `src/scc_cli/ports/safety_adapter.py` — New file: SafetyAdapter protocol defining check_command(command, policy) -> SafetyCheckResult
- `src/scc_cli/adapters/claude_safety_adapter.py` — New file: ClaudeSafetyAdapter wrapping SafetyEngine with Claude-specific UX formatting and audit emission
- `src/scc_cli/adapters/codex_safety_adapter.py` — New file: CodexSafetyAdapter wrapping SafetyEngine with Codex-specific UX formatting and audit emission
- `src/scc_cli/bootstrap.py` — Added claude_safety_adapter and codex_safety_adapter fields to DefaultAdapters; refactored get_default_adapters() to share engine/sink instances
- `tests/fakes/fake_safety_adapter.py` — New file: FakeSafetyAdapter with configurable result and call recording for downstream tests
- `tests/fakes/__init__.py` — Added FakeSafetyAdapter import and wired into build_fake_adapters()
- `tests/test_claude_safety_adapter.py` — New file: 6 unit tests covering engine delegation, audit events, user messages, audit_emitted flag
- `tests/test_codex_safety_adapter.py` — New file: 6 unit tests mirroring Claude adapter tests with Codex-specific assertions
- `tests/test_safety_adapter_audit.py` — New file: 8 integration tests exercising full engine → adapter → audit event chain for both providers
