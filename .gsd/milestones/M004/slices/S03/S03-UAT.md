# S03: Claude and Codex UX/audit adapters over the shared engine — UAT

**Milestone:** M004
**Written:** 2026-04-04T12:51:24.616Z

## UAT: S03 — Claude and Codex UX/audit adapters over the shared engine

### Preconditions
- Working directory: `scc-sync-1.7.3`
- Python environment active via `uv sync`
- S01 (shared safety engine) and S02 (runtime wrappers) already delivered

---

### Test 1: SafetyCheckResult contract integrity
**Steps:**
1. Run `uv run python -c "from scc_cli.core.contracts import SafetyCheckResult; r = SafetyCheckResult(verdict=None, user_message='test', audit_emitted=True); print(r.audit_emitted)"`
2. Verify output is `True`
3. Attempt mutation: `uv run python -c "from scc_cli.core.contracts import SafetyCheckResult; r = SafetyCheckResult(verdict=None, user_message='test', audit_emitted=True); r.user_message = 'x'"`
4. Verify FrozenInstanceError is raised (dataclass is immutable)

**Expected:** SafetyCheckResult is a frozen dataclass with three typed fields.

---

### Test 2: Claude adapter blocks dangerous command with correct UX format
**Steps:**
1. Run `uv run pytest tests/test_claude_safety_adapter.py::TestBlockedUserMessageFormat -v`
2. Verify test passes — blocked commands produce `[Claude] Command blocked: <reason>` user message

**Expected:** Claude adapter prefixes blocked messages with `[Claude]` and includes the engine's reason string.

---

### Test 3: Codex adapter blocks dangerous command with correct UX format
**Steps:**
1. Run `uv run pytest tests/test_codex_safety_adapter.py::TestBlockedUserMessageFormat -v`
2. Verify test passes — blocked commands produce `[Codex] Command blocked: <reason>` user message

**Expected:** Codex adapter prefixes blocked messages with `[Codex]` and includes the engine's reason string.

---

### Test 4: Audit events emitted with correct severity levels
**Steps:**
1. Run `uv run pytest tests/test_safety_adapter_audit.py::TestClaudeAdapterFullChainBlocked tests/test_safety_adapter_audit.py::TestClaudeAdapterFullChainAllowed -v`
2. Verify blocked → WARNING severity, allowed → INFO severity

**Expected:** Audit event severity correctly reflects the safety verdict for each check.

---

### Test 5: Both adapters produce identical verdicts for the same command
**Steps:**
1. Run `uv run pytest tests/test_safety_adapter_audit.py::TestBothAdaptersShareEngineVerdicts -v`
2. Verify test passes — same command + same policy → same `verdict.allowed` and `matched_rule` from both adapters

**Expected:** Adapters delegate to the same engine; verdict logic is not duplicated.

---

### Test 6: All audit metadata values are strings
**Steps:**
1. Run `uv run pytest tests/test_safety_adapter_audit.py::TestAuditMetadataKeysAreAllStrings -v`
2. Verify every value in the emitted AuditEvent.metadata dict is of type `str`

**Expected:** No non-string values in metadata — prevents serialization issues in LocalAuditEventSink.

---

### Test 7: Bootstrap wiring accepts safety adapter fields
**Steps:**
1. Run `uv run pytest tests/test_safety_adapter_audit.py::TestBootstrapWiringHasSafetyAdapterFields -v`
2. Verify DefaultAdapters accepts `claude_safety_adapter` and `codex_safety_adapter` fields
3. Verify both default to `None` when not explicitly provided

**Expected:** DefaultAdapters is backward-compatible — existing construction sites don't break.

---

### Test 8: Full regression passes with no new failures
**Steps:**
1. Run `uv run pytest --rootdir "$PWD" -q`
2. Verify total ≥ 3746 passed, 0 failures
3. Verify `uv run ruff check` is clean
4. Verify `uv run mypy src/scc_cli` reports 0 issues

**Expected:** No regressions from S03 changes. Test count grew by +20 (from 3726 baseline).

---

### Edge Cases
- **Missing policy key:** Adapters delegate to SafetyEngine which uses fail-closed semantics (`policy.rules.get(key, True)`) — the adapter never overrides this.
- **None matched_rule:** When engine returns `matched_rule=None`, adapter stringifies to empty string `''` in metadata — no KeyError or None serialization.
- **Adapter constructed without real engine/sink:** FakeSafetyAdapter exists for test code that doesn't need real engine evaluation.
