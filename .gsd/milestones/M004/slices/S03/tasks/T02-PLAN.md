---
estimated_steps: 34
estimated_files: 4
skills_used: []
---

# T02: Bootstrap wiring, FakeSafetyAdapter, and cross-adapter audit integration tests

## Description

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

## Inputs

- ``src/scc_cli/adapters/claude_safety_adapter.py` — ClaudeSafetyAdapter from T01`
- ``src/scc_cli/adapters/codex_safety_adapter.py` — CodexSafetyAdapter from T01`
- ``src/scc_cli/ports/safety_adapter.py` — SafetyAdapter protocol from T01`
- ``src/scc_cli/core/contracts.py` — SafetyCheckResult from T01`
- ``src/scc_cli/bootstrap.py` — existing DefaultAdapters to extend`
- ``tests/fakes/__init__.py` — existing build_fake_adapters() to extend`
- ``tests/fakes/fake_safety_engine.py` — FakeSafetyEngine for integration tests`
- ``src/scc_cli/core/safety_engine.py` — DefaultSafetyEngine for integration tests`

## Expected Output

- ``tests/fakes/fake_safety_adapter.py` — new FakeSafetyAdapter`
- ``src/scc_cli/bootstrap.py` — DefaultAdapters extended with safety adapter fields`
- ``tests/fakes/__init__.py` — build_fake_adapters() updated with fake safety adapters`
- ``tests/test_safety_adapter_audit.py` — cross-adapter audit integration tests`

## Verification

uv run pytest tests/test_safety_adapter_audit.py -v && uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q
