# S03: Claude and Codex UX/audit adapters over the shared engine

**Goal:** Claude and Codex safety adapters wrap the shared SafetyEngine with provider-specific UX formatting and AuditEvent emission, wired through bootstrap with full test coverage.
**Demo:** After this: TBD

## Tasks
- [x] **T01: Added SafetyCheckResult dataclass, SafetyAdapter protocol, and Claude/Codex adapter implementations with 12 unit tests — all checks clean** — ## Description

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
  - Estimate: 45m
  - Files: src/scc_cli/core/contracts.py, src/scc_cli/ports/safety_adapter.py, src/scc_cli/adapters/claude_safety_adapter.py, src/scc_cli/adapters/codex_safety_adapter.py, tests/test_claude_safety_adapter.py, tests/test_codex_safety_adapter.py
  - Verify: uv run pytest tests/test_claude_safety_adapter.py tests/test_codex_safety_adapter.py -v && uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q
- [x] **T02: Wired ClaudeSafetyAdapter and CodexSafetyAdapter into DefaultAdapters, created FakeSafetyAdapter, and added 8 integration tests covering engine → adapter → audit event chain** — ## Description

Wire both safety adapters into DefaultAdapters via bootstrap.py, create a FakeSafetyAdapter for downstream tests, update build_fake_adapters(), and write integration tests that exercise the full chain: engine → adapter → audit event across both providers.

## Steps

1. Create `tests/fakes/fake_safety_adapter.py`:
   - `FakeSafetyAdapter` dataclass with configurable `result: SafetyCheckResult` (default: allowed, empty message, audit_emitted=False) and `calls: list[tuple[str, SafetyPolicy]]` for recording.
   - `check_command()` records the call and returns the configured result.

2. Update `src/scc_cli/bootstrap.py`:
   - Import `ClaudeSafetyAdapter` and `CodexSafetyAdapter` from adapters.
   - Import `SafetyAdapter` from ports (for type annotation).
   - Add two new fields to `DefaultAdapters`: `claude_safety_adapter: SafetyAdapter | None = None` and `codex_safety_adapter: SafetyAdapter | None = None`.
   - In `get_default_adapters()`, after the existing `safety_engine=DefaultSafetyEngine()` line, instantiate both adapters: `claude_safety_adapter=ClaudeSafetyAdapter(engine=DefaultSafetyEngine(), audit_sink=LocalAuditEventSink())` and `codex_safety_adapter=CodexSafetyAdapter(engine=DefaultSafetyEngine(), audit_sink=LocalAuditEventSink())`. NOTE: reuse the same engine/sink instances already created for other fields — assign `engine = DefaultSafetyEngine()` and `sink = LocalAuditEventSink()` as local variables and pass to both the `safety_engine` field and both adapter constructors.

3. Update `tests/fakes/__init__.py`:
   - Import `FakeSafetyAdapter`.
   - Add `claude_safety_adapter=FakeSafetyAdapter()` and `codex_safety_adapter=FakeSafetyAdapter()` to `build_fake_adapters()`.

4. Write `tests/test_safety_adapter_audit.py` with integration tests:
   - `test_claude_adapter_full_chain_blocked` — construct ClaudeSafetyAdapter with real DefaultSafetyEngine and FakeAuditEventSink, evaluate `git push --force`, verify: verdict.allowed is False, audit event emitted with provider_id='claude' and severity WARNING, user_message contains '[Claude] Command blocked'.
   - `test_codex_adapter_full_chain_blocked` — same with CodexSafetyAdapter and '[Codex]' prefix.
   - `test_claude_adapter_full_chain_allowed` — evaluate a safe command like `git status`, verify: verdict.allowed is True, audit event with INFO severity, user_message is '[Claude] Command allowed'.
   - `test_codex_adapter_full_chain_allowed` — same with CodexSafetyAdapter.
   - `test_both_adapters_share_engine_verdicts` — feed same command to both adapters with same policy, verify both produce same verdict.allowed and same matched_rule.
   - `test_audit_metadata_keys_are_all_strings` — verify all values in emitted AuditEvent.metadata are str type (prevents serialization issues in LocalAuditEventSink).
   - `test_bootstrap_wiring_has_safety_adapter_fields` — import `get_default_adapters` or `DefaultAdapters`, verify the fields exist as attributes (don't call get_default_adapters() which probes Docker — just verify the dataclass accepts the fields).

## Must-Haves

- [ ] `FakeSafetyAdapter` exists in `tests/fakes/` with configurable result and call recording
- [ ] `DefaultAdapters` has `claude_safety_adapter` and `codex_safety_adapter` fields with `| None = None` defaults
- [ ] `build_fake_adapters()` includes both fake safety adapters
- [ ] Integration tests pass exercising engine → adapter → audit event chain
- [ ] All metadata values in emitted AuditEvents are strings
- [ ] `uv run ruff check` clean, `uv run mypy src/scc_cli` clean, full regression passes

## Verification

- `uv run pytest tests/test_safety_adapter_audit.py -v` — all pass
- `uv run ruff check` — clean
- `uv run mypy src/scc_cli` — clean
- `uv run pytest --rootdir "$PWD" -q` — full regression passes (baseline: 3726 + T01 additions)
  - Estimate: 35m
  - Files: tests/fakes/fake_safety_adapter.py, src/scc_cli/bootstrap.py, tests/fakes/__init__.py, tests/test_safety_adapter_audit.py
  - Verify: uv run pytest tests/test_safety_adapter_audit.py -v && uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q
