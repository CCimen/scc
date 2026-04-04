---
estimated_steps: 46
estimated_files: 6
skills_used: []
---

# T02: Safety audit reader, CLI command, support-bundle integration, and tests

Create `application/safety_audit.py` with a bounded reader over the canonical JSONL sink filtered to `safety.check` events. Add `scc support safety-audit` CLI command under the existing `support_app` with human and `--json` modes. Add `SAFETY_AUDIT` kind to the enum. Create the JSON presenter. Add a `safety` section to the support bundle manifest with effective policy summary and recent safety events. Write comprehensive tests.

## Steps

1. Add `SAFETY_AUDIT = "SafetyAudit"` to `Kind` enum in `src/scc_cli/kinds.py`.

2. Create `src/scc_cli/application/safety_audit.py`:
   - Define `SafetyAuditEventRecord` frozen dataclass: `line_number: int`, `event_type: str`, `message: str`, `severity: str`, `occurred_at: str`, `command: str | None`, `verdict_allowed: str | None`, `matched_rule: str | None`, `provider_id: str | None`, `metadata: dict[str, Any]`
   - Define `SafetyAuditDiagnostics` frozen dataclass: `sink_path: str`, `state: str`, `requested_limit: int`, `scanned_line_count: int`, `malformed_line_count: int`, `last_malformed_line: int | None`, `recent_events: tuple[SafetyAuditEventRecord, ...]`, `last_blocked: SafetyAuditEventRecord | None`, `blocked_count: int`, `allowed_count: int`, `error: str | None = None`
   - Add `to_dict()` method on `SafetyAuditDiagnostics` using `dataclasses.asdict`
   - Implement `read_safety_audit_diagnostics(*, audit_path: Path | None = None, limit: int = 10, redact_paths: bool = True) -> SafetyAuditDiagnostics`
   - Reuse `_tail_lines` from `application/launch/audit_log.py` (import it) for bounded tail-read
   - Filter parsed records to `event_type == "safety.check"` only
   - Extract `command`, `verdict_allowed`, `matched_rule`, `provider_id` from record metadata
   - Track `blocked_count` / `allowed_count` and `last_blocked`
   - Reuse the `_redact_string` pattern for path redaction

3. Create `src/scc_cli/presentation/json/safety_audit_json.py`:
   - Implement `build_safety_audit_envelope(diagnostics: SafetyAuditDiagnostics) -> dict[str, object]`
   - Use `build_envelope(Kind.SAFETY_AUDIT, data=diagnostics.to_dict())`

4. Add `scc support safety-audit` command in `src/scc_cli/commands/support.py`:
   - Follow the exact pattern of `support_launch_audit_cmd`
   - Options: `--limit` (default 10), `--json`, `--pretty`
   - Human mode: render sink state, blocked/allowed counts, last blocked command, recent events
   - JSON mode: use `build_safety_audit_envelope`
   - Import from `application.safety_audit` and `presentation.json.safety_audit_json`

5. Add `safety` section to `build_support_bundle_manifest()` in `src/scc_cli/application/support_bundle.py`:
   - Wrap in try/except (partial results pattern per KNOWLEDGE.md)
   - Include effective policy summary via `load_safety_policy()` from `core/safety_policy_loader.py`
   - Include recent safety audit events via `read_safety_audit_diagnostics(limit=5)`
   - Structure: `{"effective_policy": {"action": ..., "source": ...}, "recent_audit": diagnostics.to_dict()}`

6. Create `tests/test_safety_audit.py` with tests:
   - `test_empty_sink_returns_empty_state` — no file exists → state "unavailable"
   - `test_filters_to_safety_check_events` — mixed JSONL with launch and safety.check events → only safety.check returned
   - `test_blocked_allowed_counts` — verify blocked_count and allowed_count
   - `test_last_blocked_populated` — verify last_blocked is the most recent blocked event
   - `test_bounded_scan` — verify limit parameter works
   - `test_malformed_lines_skipped` — malformed JSON lines don't crash, increment malformed count
   - `test_redact_paths` — home dir replaced with ~
   - `test_support_bundle_has_safety_section` — mock dependencies, verify manifest["safety"] key exists

## Must-Haves

- [ ] Safety audit reader filters to `event_type == "safety.check"` only
- [ ] Reader uses bounded tail-read (reuses `_tail_lines`), not full-file scan
- [ ] `scc support safety-audit` works in both human and `--json` modes
- [ ] Support bundle manifest includes `safety` section with effective policy and recent audit
- [ ] `SAFETY_AUDIT` kind registered in `kinds.py`
- [ ] All tests in `test_safety_audit.py` pass
- [ ] `uv run ruff check` clean
- [ ] `uv run mypy src/scc_cli` clean
- [ ] Full regression ≥3746 passed

## Inputs

- ``src/scc_cli/core/safety_policy_loader.py` — load_safety_policy() from T01`
- ``src/scc_cli/application/launch/audit_log.py` — _tail_lines reuse, LaunchAuditDiagnostics pattern`
- ``src/scc_cli/commands/support.py` — existing support_app and launch-audit command pattern`
- ``src/scc_cli/application/support_bundle.py` — existing build_support_bundle_manifest()`
- ``src/scc_cli/kinds.py` — existing Kind enum`
- ``src/scc_cli/json_output.py` — build_envelope()`
- ``src/scc_cli/presentation/json/launch_audit_json.py` — JSON presenter pattern`
- ``src/scc_cli/adapters/local_audit_event_sink.py` — JSONL format reference`

## Expected Output

- ``src/scc_cli/kinds.py` — updated with SAFETY_AUDIT kind`
- ``src/scc_cli/application/safety_audit.py` — safety audit reader module`
- ``src/scc_cli/presentation/json/safety_audit_json.py` — JSON envelope builder`
- ``src/scc_cli/commands/support.py` — updated with safety-audit command`
- ``src/scc_cli/application/support_bundle.py` — updated with safety section`
- ``tests/test_safety_audit.py` — safety audit reader and integration tests`

## Verification

uv run pytest tests/test_safety_audit.py -v && uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q
