# S03 — Research: Claude and Codex UX/audit adapters over the shared engine

**Date:** 2026-04-04

## Summary

S03 bridges the shared safety engine (S01) and the runtime wrapper baseline (S02) to the two provider adapters (Claude, Codex). The work is **straightforward** — it follows established patterns (provider adapter shape, audit event sink, bootstrap wiring) and requires no new technology or risky integration.

The two provider adapters (`ClaudeAgentProvider`, `CodexAgentProvider`) already exist with their 4-test characterization shape. Neither currently touches safety evaluation. The slice needs to add a thin UX/audit adapter layer that:

1. **Calls `SafetyEngine.evaluate()`** for provider-initiated commands, producing typed `SafetyVerdict` results.
2. **Emits `AuditEvent` records** through the existing `AuditEventSink` port when safety evaluation triggers (block, warn, allow with rule match).
3. **Formats provider-specific UX feedback** — Claude and Codex may present safety verdicts differently to the user, but both consume the same engine.

The key architectural constraint is that the adapters must **not** duplicate safety logic. They are UX/audit shells around `SafetyEngine.evaluate()`. The hard enforcement lives in the runtime wrappers (S02). The adapters improve the user experience (richer error messages, provider-native formatting) and create an audit trail.

## Recommendation

Build a single `SafetyAdapter` protocol in `ports/` with `check_command(command, policy) -> SafetyCheckResult` that wraps `SafetyEngine.evaluate()` + audit event emission. Then implement `ClaudeSafetyAdapter` and `CodexSafetyAdapter` in `adapters/`. Each adapter:
- Takes a `SafetyEngine` and `AuditEventSink` at construction
- Calls `engine.evaluate(command, policy)` for the verdict
- Emits a structured `AuditEvent` with provider-specific metadata (`provider_id`, verdict details)
- Returns a `SafetyCheckResult` carrying the verdict plus a provider-formatted user message

Wire both adapters into `DefaultAdapters` via `bootstrap.py` following the established `| None = None` optional-field pattern. Expose a `FakeSafetyAdapter` in `tests/fakes/` for downstream testing.

This keeps the adapters thin (< 60 lines each), maximizes reuse of the shared engine, and produces auditable safety events matching the existing `AuditEvent` contract.

## Implementation Landscape

### Key Files

- `src/scc_cli/ports/safety_engine.py` — Existing `SafetyEngine` protocol. The adapters consume this, not duplicate it.
- `src/scc_cli/core/safety_engine.py` — `DefaultSafetyEngine` implementation from S01. Not modified.
- `src/scc_cli/core/contracts.py` — Existing `SafetyVerdict`, `SafetyPolicy`, `AuditEvent` dataclasses. May add a small `SafetyCheckResult` here or in a new file.
- `src/scc_cli/ports/audit_event_sink.py` — Existing `AuditEventSink` protocol. Adapters emit events through this.
- `src/scc_cli/adapters/claude_agent_provider.py` — Existing Claude provider adapter. Not modified (separation of concerns: launch prep vs safety check are separate responsibilities).
- `src/scc_cli/adapters/codex_agent_provider.py` — Existing Codex provider adapter. Not modified.
- `src/scc_cli/bootstrap.py` — Composition root. Needs new adapter fields and wiring.
- `tests/fakes/__init__.py` — Test factory. Needs fake safety adapter.
- `tests/fakes/fake_safety_engine.py` — Existing fake. Not modified (used by the adapters' tests).

### New Files

- `src/scc_cli/ports/safety_adapter.py` — New `SafetyAdapter` protocol: `check_command(command, policy) -> SafetyCheckResult`.
- `src/scc_cli/core/contracts.py` — Add `SafetyCheckResult` dataclass (verdict + user_message + audit_emitted flag).
- `src/scc_cli/adapters/claude_safety_adapter.py` — Claude-specific adapter: wraps engine + emits audit events with `provider_id="claude"`.
- `src/scc_cli/adapters/codex_safety_adapter.py` — Codex-specific adapter: wraps engine + emits audit events with `provider_id="codex"`.
- `tests/fakes/fake_safety_adapter.py` — Configurable fake for downstream tests.
- `tests/test_claude_safety_adapter.py` — Adapter unit tests.
- `tests/test_codex_safety_adapter.py` — Adapter unit tests.
- `tests/test_safety_adapter_audit.py` — Cross-adapter audit integration tests.

### Build Order

1. **T01 — SafetyCheckResult contract + SafetyAdapter protocol.** Add `SafetyCheckResult` to `core/contracts.py`. Create `ports/safety_adapter.py` with the protocol. This is pure types — no logic, no risk. Unblocks both adapter implementations.

2. **T02 — Claude and Codex safety adapters.** Implement `ClaudeSafetyAdapter` and `CodexSafetyAdapter` in `adapters/`. Both follow the same pattern: construct with `SafetyEngine` + `AuditEventSink`, delegate `evaluate()`, emit audit event, format user message. Tests follow the existing 4-test adapter characterization shape adapted for safety (verdict passthrough, audit emission, provider metadata, blocked/allowed UX formatting).

3. **T03 — Bootstrap wiring + fake + integration tests.** Wire adapters into `DefaultAdapters` with `| None = None` defaults. Create `FakeSafetyAdapter`. Update `build_fake_adapters()`. Write integration tests confirming the full chain: engine → adapter → audit event.

### Verification Approach

- `uv run pytest tests/test_claude_safety_adapter.py tests/test_codex_safety_adapter.py tests/test_safety_adapter_audit.py -v` — all new adapter tests pass
- `uv run pytest tests/test_safety_engine.py tests/test_safety_engine_boundary.py -v` — existing engine tests unbroken
- `uv run ruff check` — clean
- `uv run mypy src/scc_cli` — clean
- `uv run pytest --rootdir "$PWD" -q` — full regression passes (baseline: 3726 passed)

## Constraints

- **Import boundary:** `test_only_bootstrap_imports_adapters` is not enforced as a test file but `test_safety_engine_boundary.py` AST-scans core safety modules for provider imports. Adapters must import from `ports/` and `core/`, never the reverse.
- **Adapter isolation:** Per spec-03 and KNOWLEDGE.md: "provider-native features are not hard enforcement." The adapters are UX/audit only. They must not alter verdict logic beyond formatting.
- **DefaultAdapters pattern:** New fields must use `| None = None` defaults per KNOWLEDGE.md to avoid breaking existing construction sites (`build_fake_adapters()`, inline `DefaultAdapters(...)` calls in tests).
- **AuditEvent shape:** Must use the existing `AuditEvent` dataclass from `core/contracts.py`. Metadata is `dict[str, str]` — no nested objects. Provider-specific context goes in metadata keys like `provider_id`, `matched_rule`, `verdict_allowed`.

## Common Pitfalls

- **Breaking `build_fake_adapters()`** — Every new `DefaultAdapters` field must be mirrored in `tests/fakes/__init__.py`. The `| None = None` default is the safety net, but tests that construct `DefaultAdapters` inline will break without it.
- **Duplicating verdict logic in adapters** — The adapters must delegate to `SafetyEngine.evaluate()` and only add UX formatting. If an adapter re-evaluates or reinterprets the verdict, it diverges from the runtime wrappers (S02) and creates a consistency gap.
- **Audit event metadata types** — `AuditEvent.metadata` is `dict[str, str]`. Passing non-string values (e.g. `bool` for `verdict.allowed`) will cause serialization issues in `LocalAuditEventSink`. Always stringify.
