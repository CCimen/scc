# S04: Fail-closed policy loading, audit surfaces, and operator diagnostics

**Goal:** Fail-closed typed policy loading from org config, doctor safety-policy check, safety audit reader over the canonical JSONL sink, `scc support safety-audit` CLI command, and safety section in the support bundle — all following established patterns.
**Demo:** After this: TBD

## Tasks
- [x] **T01: Added fail-closed typed SafetyPolicy loader in core, doctor safety-policy check, and 31 tests with import guardrail** — Create `core/safety_policy_loader.py` with `load_safety_policy(org_config: dict[str, Any] | None) -> SafetyPolicy` that extracts safety policy from org config dicts and returns a typed `SafetyPolicy`. Fail-closed: any parse error → default `SafetyPolicy(action="block")`. Create `doctor/checks/safety.py` with `check_safety_policy() -> CheckResult` that probes org config availability and policy validity through `bootstrap.get_default_adapters()`. Register the new check in `doctor/checks/__init__.py` and `doctor/core.py`. Write comprehensive tests and a guardrail preventing core→docker imports.

## Steps

1. Create `src/scc_cli/core/safety_policy_loader.py`:
   - Define `VALID_SAFETY_NET_ACTIONS = frozenset({"block", "warn", "allow"})`
   - Implement `load_safety_policy(org_config: dict[str, Any] | None) -> SafetyPolicy`
   - Extract `security.safety_net` from org config dict
   - Validate `action` field: if missing or not in valid set → `"block"` (fail-closed)
   - Pass remaining keys as `rules` dict
   - Return `SafetyPolicy(action=action, rules=rules, source="org.security.safety_net")`
   - On any exception or if org_config is None → return default `SafetyPolicy(action="block")`
   - Do NOT import from `scc_cli.docker.launch` — duplicate the ~10 lines of validation logic

2. Create `src/scc_cli/doctor/checks/safety.py`:
   - Implement `check_safety_policy() -> CheckResult`
   - Try loading org config via `bootstrap.get_default_adapters()` → `adapters.config_store`
   - If no org config: return WARNING CheckResult ("No org config found, using default block policy")
   - If org config lacks `security.safety_net`: return WARNING ("No safety_net section in org config")
   - If action is invalid: return ERROR with fix hint
   - If valid: return PASS with the effective action
   - Wrap the whole check in try/except → return ERROR on any unexpected failure

3. Register the check in `doctor/checks/__init__.py`:
   - Import `check_safety_policy` from `.safety`
   - Add to `run_all_checks()` after the cache checks section
   - Add to `__all__`

4. Register the check in `doctor/core.py`:
   - Import `check_safety_policy` from `.checks`
   - Call it in `run_doctor()` and append to `result.checks`

5. Create `tests/test_safety_policy_loader.py` with tests:
   - `test_none_org_config_returns_default_block` — None → SafetyPolicy(action="block")
   - `test_empty_dict_returns_default_block` — {} → block
   - `test_missing_security_key_returns_default_block`
   - `test_missing_safety_net_key_returns_default_block`
   - `test_valid_block_action_passthrough`
   - `test_valid_warn_action_passthrough`
   - `test_valid_allow_action_passthrough`
   - `test_invalid_action_falls_back_to_block`
   - `test_rules_extracted_from_policy`
   - `test_non_dict_org_config_returns_default_block` — e.g. string or list input
   - `test_no_import_from_docker_launch` — guardrail: tokenize `safety_policy_loader.py`, assert no NAME token `docker` in import statements

6. Create `tests/test_safety_doctor_check.py` with tests:
   - `test_check_passes_with_valid_org_config` — mock config_store to return org config with valid safety_net
   - `test_check_warns_when_no_org_config` — mock config_store returning None
   - `test_check_warns_when_no_safety_net_section`
   - `test_check_errors_on_malformed_org_config` — mock config_store raising exception

## Must-Haves

- [ ] `load_safety_policy()` returns `SafetyPolicy` (never raw dict, never None)
- [ ] Fail-closed: any parse failure → default block policy
- [ ] No imports from `scc_cli.docker.launch` in `safety_policy_loader.py`
- [ ] Doctor check goes through `bootstrap.get_default_adapters()` per KNOWLEDGE.md rule
- [ ] All tests in `test_safety_policy_loader.py` and `test_safety_doctor_check.py` pass
- [ ] `uv run ruff check` clean
- [ ] `uv run mypy src/scc_cli` clean
  - Estimate: 45m
  - Files: src/scc_cli/core/safety_policy_loader.py, src/scc_cli/doctor/checks/safety.py, src/scc_cli/doctor/checks/__init__.py, src/scc_cli/doctor/core.py, tests/test_safety_policy_loader.py, tests/test_safety_doctor_check.py
  - Verify: uv run pytest tests/test_safety_policy_loader.py tests/test_safety_doctor_check.py -v && uv run ruff check && uv run mypy src/scc_cli && grep -r 'from scc_cli.docker' src/scc_cli/core/safety_policy_loader.py; test $? -eq 1
- [ ] **T02: Safety audit reader, CLI command, support-bundle integration, and tests** — Create `application/safety_audit.py` with a bounded reader over the canonical JSONL sink filtered to `safety.check` events. Add `scc support safety-audit` CLI command under the existing `support_app` with human and `--json` modes. Add `SAFETY_AUDIT` kind to the enum. Create the JSON presenter. Add a `safety` section to the support bundle manifest with effective policy summary and recent safety events. Write comprehensive tests.

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
  - Estimate: 60m
  - Files: src/scc_cli/kinds.py, src/scc_cli/application/safety_audit.py, src/scc_cli/presentation/json/safety_audit_json.py, src/scc_cli/commands/support.py, src/scc_cli/application/support_bundle.py, tests/test_safety_audit.py
  - Verify: uv run pytest tests/test_safety_audit.py -v && uv run ruff check && uv run mypy src/scc_cli && uv run pytest --rootdir "$PWD" -q
