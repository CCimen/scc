# S04: Fail-closed policy loading, audit surfaces, and operator diagnostics — UAT

**Milestone:** M004
**Written:** 2026-04-04T13:20:54.513Z

## UAT: S04 — Fail-closed policy loading, audit surfaces, and operator diagnostics

### Preconditions
- SCC installed with `uv sync` from `scc-sync-1.7.3`
- No special environment or Docker required — all tests are unit/integration level

---

### TC-01: Fail-closed policy loader — None input
**Steps:**
1. Call `load_safety_policy(None)`
**Expected:** Returns `SafetyPolicy(action="block")` — the default fail-closed policy.

### TC-02: Fail-closed policy loader — empty dict
**Steps:**
1. Call `load_safety_policy({})`
**Expected:** Returns `SafetyPolicy(action="block")`.

### TC-03: Fail-closed policy loader — valid org config with warn action
**Steps:**
1. Call `load_safety_policy({"security": {"safety_net": {"action": "warn", "git_force_push": False}}})`
**Expected:** Returns `SafetyPolicy(action="warn", rules={"git_force_push": False}, source="org.security.safety_net")`.

### TC-04: Fail-closed policy loader — invalid action falls back to block
**Steps:**
1. Call `load_safety_policy({"security": {"safety_net": {"action": "yolo"}}})`
**Expected:** Returns `SafetyPolicy(action="block")` — invalid actions are rejected fail-closed.

### TC-05: Fail-closed policy loader — non-dict input
**Steps:**
1. Call `load_safety_policy("not a dict")`
**Expected:** Returns `SafetyPolicy(action="block")` — graceful fallback on type error.

### TC-06: Import boundary guardrail
**Steps:**
1. Run `grep -r 'from scc_cli.docker' src/scc_cli/core/safety_policy_loader.py`
**Expected:** Exit code 1 (no matches). The core safety policy loader has no docker imports.

### TC-07: Doctor check — valid org config
**Steps:**
1. Mock `bootstrap.get_default_adapters()` to return adapters with a config_store containing valid org config with `security.safety_net.action = "warn"`
2. Call `check_safety_policy()`
**Expected:** Returns `CheckResult` with status PASS and message indicating effective action is "warn".

### TC-08: Doctor check — no org config available
**Steps:**
1. Mock `bootstrap.get_default_adapters()` to return adapters with config_store returning None
2. Call `check_safety_policy()`
**Expected:** Returns `CheckResult` with status WARNING and message about using default block policy.

### TC-09: Doctor check — malformed org config (exception)
**Steps:**
1. Mock `bootstrap.get_default_adapters()` to raise an exception
2. Call `check_safety_policy()`
**Expected:** Returns `CheckResult` with status ERROR — does not crash.

### TC-10: Safety audit reader — empty/missing sink
**Steps:**
1. Call `read_safety_audit_diagnostics(audit_path=Path("/nonexistent"))` 
**Expected:** Returns `SafetyAuditDiagnostics` with `state="unavailable"`, zero counts, empty events.

### TC-11: Safety audit reader — filters to safety.check events
**Steps:**
1. Create a JSONL file with mixed events: `launch.started`, `safety.check` (blocked), `safety.check` (allowed), `launch.completed`
2. Call `read_safety_audit_diagnostics(audit_path=..., limit=10)`
**Expected:** `recent_events` contains only the 2 safety.check events. Launch events are silently skipped (not malformed).

### TC-12: Safety audit reader — blocked/allowed counts
**Steps:**
1. Create JSONL with 3 safety.check events: 2 with `verdict_allowed: false`, 1 with `verdict_allowed: true`
2. Call `read_safety_audit_diagnostics(audit_path=...)`
**Expected:** `blocked_count=2`, `allowed_count=1`, `last_blocked` is the most recent blocked event.

### TC-13: Safety audit reader — malformed lines skipped
**Steps:**
1. Create JSONL with valid safety.check events interleaved with `{invalid json` lines
2. Call `read_safety_audit_diagnostics(audit_path=...)`
**Expected:** `malformed_line_count > 0`, valid safety events still returned, no crash.

### TC-14: Safety audit reader — path redaction
**Steps:**
1. Create JSONL with a safety.check event containing the user's home directory path in metadata
2. Call `read_safety_audit_diagnostics(audit_path=..., redact_paths=True)`
**Expected:** Home directory replaced with `~` in returned event records and sink_path.

### TC-15: CLI command — `scc support safety-audit` human mode
**Steps:**
1. Mock audit sink with safety events
2. Invoke `scc support safety-audit --limit 5`
**Expected:** Human-readable output showing sink state, blocked/allowed summary, and recent events.

### TC-16: CLI command — `scc support safety-audit --json` mode
**Steps:**
1. Mock audit sink with safety events
2. Invoke `scc support safety-audit --json`
**Expected:** Valid JSON envelope with `kind: "SafetyAudit"` and `data` containing diagnostics.

### TC-17: Support bundle safety section
**Steps:**
1. Mock org config and audit sink
2. Call `build_support_bundle_manifest()`
**Expected:** Manifest contains `safety` key with `effective_policy` (action, source) and `recent_audit` (diagnostics dict).

### TC-18: Support bundle safety section — partial failure resilience
**Steps:**
1. Mock org config to raise an exception but audit sink to work normally
2. Call `build_support_bundle_manifest()`
**Expected:** Bundle still generates successfully with partial safety data — does not crash.

### TC-19: Full verification gate
**Steps:**
1. `uv run pytest tests/test_safety_policy_loader.py tests/test_safety_doctor_check.py tests/test_safety_audit.py -v`
2. `uv run ruff check`
3. `uv run mypy src/scc_cli`
4. `uv run pytest --rootdir "$PWD" -q`
**Expected:** All pass. ≥3790 tests in full suite. Zero regressions.
