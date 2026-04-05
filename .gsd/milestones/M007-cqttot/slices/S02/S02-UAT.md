# S02: Session, resume, and machine-readable output provider hardening — UAT

**Milestone:** M007-cqttot
**Written:** 2026-04-05T13:04:08.837Z

## UAT: S02 — Session, resume, and machine-readable output provider hardening

### Preconditions
- SCC installed with `uv sync` and full test suite passing (4675 tests)
- S01 ProviderRuntimeSpec registry available in `core/provider_registry.py`

---

### Test Case 1: Provider sessions directory resolution

**Steps:**
1. Import `get_provider_sessions_dir` from `scc_cli.sessions`
2. Call `get_provider_sessions_dir()` (no args)
3. Call `get_provider_sessions_dir('claude')`
4. Call `get_provider_sessions_dir('codex')`
5. Call `get_provider_sessions_dir('unknown-provider')`

**Expected:**
- Step 2 and 3 both return `Path.home() / '.claude'`
- Step 4 returns `Path.home() / '.codex'`
- Step 5 raises `InvalidProviderError`

---

### Test Case 2: Provider recent sessions helper

**Steps:**
1. Import `get_provider_recent_sessions` from `scc_cli.sessions`
2. Call `get_provider_recent_sessions('claude')` in an env with no sessions.json
3. Call `get_provider_recent_sessions('codex')` in an env with no sessions.json

**Expected:**
- Both return empty list without error
- Neither references hardcoded `AGENT_CONFIG_DIR`

---

### Test Case 3: Audit config dir resolution

**Steps:**
1. Import `get_provider_config_dir` from `scc_cli.commands.audit`
2. Call `get_provider_config_dir()` (no args)
3. Call `get_provider_config_dir('codex')`
4. Call `get_provider_config_dir('unknown')`

**Expected:**
- Step 2 returns `Path.home() / '.claude'`
- Step 3 returns `Path.home() / '.codex'`
- Step 4 raises `InvalidProviderError`

---

### Test Case 4: Sandbox provider_id recording

**Steps:**
1. Read `src/scc_cli/commands/launch/sandbox.py` line containing `provider_id=`
2. Verify it reads `provider_id='claude'` not `provider_id=None`

**Expected:**
- Legacy sandbox path explicitly records `provider_id='claude'`

---

### Test Case 5: WorkContext provider_id serialization

**Steps:**
1. Create a WorkContext with `provider_id='codex'`
2. Call `to_dict()` on it
3. Call `WorkContext.from_dict()` with the resulting dict
4. Verify `provider_id` round-trips to `'codex'`
5. Call `WorkContext.from_dict()` with a dict that has no `provider_id` key

**Expected:**
- Step 4: provider_id is `'codex'`
- Step 5: provider_id defaults to `None` (backward compat)

---

### Test Case 6: WorkContext display_label with provider

**Steps:**
1. Create WorkContext with `provider_id=None`, check `display_label`
2. Create WorkContext with `provider_id='claude'`, check `display_label`
3. Create WorkContext with `provider_id='codex'`, check `display_label`

**Expected:**
- Step 1: display_label contains no provider suffix
- Step 2: display_label contains no provider suffix (Claude is the default, not shown)
- Step 3: display_label ends with `(codex)` suffix

---

### Test Case 7: Session list CLI includes provider column

**Steps:**
1. Run `uv run pytest tests/test_s02_provider_sessions.py::TestSessionListProvider -v`

**Expected:**
- `test_session_dicts_includes_provider_id` passes — session dicts carry provider_id
- `test_session_dicts_defaults_none_to_claude` passes — None provider defaults to 'claude' in output

---

### Test Case 8: Old function names no longer exist

**Steps:**
1. `grep -r "get_claude_sessions_dir\|get_claude_recent_sessions\|get_claude_dir" src/scc_cli/`

**Expected:**
- Zero matches — all Claude-named helpers have been renamed

---

### Test Case 9: Full regression suite

**Steps:**
1. Run `uv run pytest -q`

**Expected:**
- 4675 passed, 23 skipped, 2 xfailed
- Zero failures, zero errors
