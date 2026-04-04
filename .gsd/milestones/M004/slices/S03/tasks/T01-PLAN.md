---
estimated_steps: 33
estimated_files: 6
skills_used: []
---

# T01: SafetyCheckResult contract, SafetyAdapter protocol, and Claude/Codex adapter implementations with unit tests

## Description

Create the SafetyCheckResult dataclass, the SafetyAdapter protocol port, and both provider-specific adapter implementations (ClaudeSafetyAdapter, CodexSafetyAdapter). Each adapter takes a SafetyEngine and AuditEventSink at construction, delegates to engine.evaluate(), emits a structured AuditEvent with provider-specific metadata, and returns a SafetyCheckResult with the verdict plus a provider-formatted user message. Write unit tests for both adapters.

## Steps

1. Add `SafetyCheckResult` frozen dataclass to `src/scc_cli/core/contracts.py` with fields: `verdict: SafetyVerdict`, `user_message: str`, `audit_emitted: bool`.

2. Create `src/scc_cli/ports/safety_adapter.py` with a `SafetyAdapter` Protocol defining `check_command(command: str, policy: SafetyPolicy) -> SafetyCheckResult`.

3. Implement `src/scc_cli/adapters/claude_safety_adapter.py`:
   - Class `ClaudeSafetyAdapter` with `__init__(self, engine: SafetyEngine, audit_sink: AuditEventSink)`.
   - `check_command()` calls `self.engine.evaluate(command, policy)` to get a `SafetyVerdict`.
   - Emits an `AuditEvent` via `self.audit_sink.append()` with: `event_type='safety.check'`, `severity=SeverityLevel.WARNING` if blocked else `SeverityLevel.INFO`, `subject='claude'`, `metadata={'provider_id': 'claude', 'command': command, 'verdict_allowed': str(verdict.allowed).lower(), 'matched_rule': verdict.matched_rule or '', 'command_family': verdict.command_family or ''}`.
   - Returns `SafetyCheckResult(verdict=verdict, user_message=<claude-formatted>, audit_emitted=True)`.
   - Claude user message format: blocked → `'[Claude] Command blocked: {verdict.reason}'`, allowed → `'[Claude] Command allowed'`.

4. Implement `src/scc_cli/adapters/codex_safety_adapter.py` — same pattern as Claude but with `provider_id='codex'`, `subject='codex'`, and message prefix `'[Codex]'`.

5. Write `tests/test_claude_safety_adapter.py` with tests:
   - `test_check_command_delegates_to_engine` — verify engine.evaluate() called with correct args
   - `test_blocked_command_emits_warning_audit_event` — verify AuditEvent with WARNING severity and correct metadata
   - `test_allowed_command_emits_info_audit_event` — verify AuditEvent with INFO severity
   - `test_blocked_user_message_format` — verify '[Claude] Command blocked: ...' format
   - `test_allowed_user_message_format` — verify '[Claude] Command allowed'
   - `test_audit_emitted_flag_is_true` — verify SafetyCheckResult.audit_emitted is True
   - Use `FakeSafetyEngine` from `tests/fakes/fake_safety_engine.py` and `FakeAuditEventSink` from `tests/fakes/__init__.py`.

6. Write `tests/test_codex_safety_adapter.py` — mirror of Claude tests with Codex-specific assertions (provider_id='codex', '[Codex]' prefix).

## Must-Haves

- [ ] `SafetyCheckResult` is a frozen dataclass with `verdict`, `user_message`, `audit_emitted` fields
- [ ] `SafetyAdapter` protocol defines `check_command(command, policy) -> SafetyCheckResult`
- [ ] Both adapters delegate to `SafetyEngine.evaluate()` — no duplicated verdict logic
- [ ] Both adapters emit `AuditEvent` with stringified metadata values (dict[str, str])
- [ ] All unit tests pass
- [ ] `uv run ruff check` clean, `uv run mypy src/scc_cli` clean

## Verification

- `uv run pytest tests/test_claude_safety_adapter.py tests/test_codex_safety_adapter.py -v` — all pass
- `uv run ruff check` — clean
- `uv run mypy src/scc_cli` — clean
- `uv run pytest --rootdir "$PWD" -q` — full regression passes (baseline: 3726)

## Inputs

- ``src/scc_cli/core/contracts.py` — existing SafetyVerdict, SafetyPolicy, AuditEvent dataclasses to extend with SafetyCheckResult`
- ``src/scc_cli/ports/safety_engine.py` — SafetyEngine protocol that adapters consume`
- ``src/scc_cli/ports/audit_event_sink.py` — AuditEventSink protocol that adapters emit through`
- ``src/scc_cli/core/enums.py` — SeverityLevel enum for AuditEvent severity`
- ``tests/fakes/fake_safety_engine.py` — FakeSafetyEngine for unit test injection`
- ``tests/fakes/__init__.py` — FakeAuditEventSink for unit test injection`

## Expected Output

- ``src/scc_cli/core/contracts.py` — SafetyCheckResult dataclass added`
- ``src/scc_cli/ports/safety_adapter.py` — new SafetyAdapter protocol`
- ``src/scc_cli/adapters/claude_safety_adapter.py` — new ClaudeSafetyAdapter implementation`
- ``src/scc_cli/adapters/codex_safety_adapter.py` — new CodexSafetyAdapter implementation`
- ``tests/test_claude_safety_adapter.py` — Claude adapter unit tests`
- ``tests/test_codex_safety_adapter.py` — Codex adapter unit tests`

## Verification

uv run pytest tests/test_claude_safety_adapter.py tests/test_codex_safety_adapter.py -v && uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q
