# S05: Product naming, documentation truthfulness, and milestone validation — UAT

**Milestone:** M007-cqttot
**Written:** 2026-04-05T16:03:05.145Z

## UAT: S05 — Product Naming, Documentation Truthfulness, and Architecture Reconciliation

### Preconditions
- Working directory: `scc-sync-1.7.3`
- Python 3.10+, uv installed
- `uv sync` completed

---

### Test 1: Product naming consistency
**Steps:**
1. `head -1 README.md`
2. `grep '^description' pyproject.toml`
3. `grep -r 'Sandboxed Code CLI' src/scc_cli/ui/branding.py`

**Expected:**
- README line 1 contains 'SCC - Sandboxed Code CLI' (not 'Claude' or 'Coding')
- pyproject.toml description says 'Run AI coding agents' (not 'Run Claude Code')
- branding.py references 'Sandboxed Code CLI'

---

### Test 2: Truthfulness guardrail tests pass
**Steps:**
1. `uv run pytest tests/test_docs_truthfulness.py -v`

**Expected:**
- 32 tests pass including:
  - test_readme_title_says_sandboxed_code_cli
  - test_provider_runtime_spec_exists_in_core
  - test_fail_closed_dispatch_error_exists
  - test_d033_codex_bypass_flag_in_runner
  - test_d035_agent_settings_rendered_bytes
  - test_d037_agent_provider_has_auth_check
  - test_d040_codex_runner_forces_file_auth_store
  - test_d041_codex_settings_scope_is_workspace
  - test_d001_product_identity_consistent

---

### Test 3: Settings serialization is format-agnostic
**Steps:**
1. `uv run pytest tests/test_claude_agent_runner.py tests/test_codex_agent_runner.py -v -k settings`

**Expected:**
- Claude runner produces JSON bytes (parseable with json.loads)
- Codex runner produces TOML bytes (contains `[section]` syntax)
- Both return AgentSettings with rendered_bytes, not dict

---

### Test 4: Codex launch argv includes bypass flag
**Steps:**
1. `uv run pytest tests/test_codex_agent_runner.py -v -k bypass`

**Expected:**
- `--dangerously-bypass-approvals-and-sandbox` present in build_command() output

---

### Test 5: Codex config includes file-based auth
**Steps:**
1. `uv run pytest tests/test_codex_agent_runner.py -v -k D040`

**Expected:**
- Tests prove `cli_auth_credentials_store = "file"` always appears in Codex rendered settings
- Caller config can add keys but SCC defaults are always present

---

### Test 6: Auth readiness is adapter-owned
**Steps:**
1. `uv run pytest tests/test_claude_agent_provider.py tests/test_codex_agent_provider.py -v -k auth`

**Expected:**
- Both providers implement auth_check() returning AuthReadiness
- Tests cover: volume missing, file missing, empty file, corrupt JSON, valid JSON
- Wording is truthful ('auth cache present' not 'logged in')

---

### Test 7: Fail-closed dispatch — no silent Claude fallback
**Steps:**
1. `uv run pytest tests/test_application_start_session.py tests/test_provider_dispatch.py tests/test_bootstrap.py -v -k 'fail_closed or invalid_provider or missing_provider'`

**Expected:**
- Missing provider_id raises InvalidProviderError or ProviderNotReadyError
- No test shows a silent fallback to Claude in active launch paths

---

### Test 8: Config persistence transitions
**Steps:**
1. `uv run pytest tests/test_oci_sandbox_runtime.py::TestConfigPersistenceTransitions -v`

**Expected:**
- 7 tests pass covering governed→standalone, teamA→teamB, resume skip, settings→no-settings, cross-provider, and idempotent transitions

---

### Test 9: Image Dockerfile structure
**Steps:**
1. `uv run pytest tests/test_image_structure.py -v`

**Expected:**
- 25 tests pass
- scc-base creates both .claude and .codex dirs
- scc-agent-codex has ARG CODEX_VERSION

---

### Test 10: Full regression suite
**Steps:**
1. `uv run pytest -q`

**Expected:**
- ≥4750 passed (actual: 4820), 0 failed
- 23 skipped and 2 xfailed are pre-existing

---

### Edge Cases
- **Resume after governed team switch:** Resume returns None for settings, OCI runtime skips injection — agent keeps original session config
- **Empty config on fresh launch:** SCC writes empty/default config file (never skips write) — clears stale team config from volume
- **Corrupt auth file:** auth_check() returns AuthReadiness(ready=False) with guidance, not a crash
- **Unknown provider_id in launch path:** InvalidProviderError raised, never silent fallback to Claude
