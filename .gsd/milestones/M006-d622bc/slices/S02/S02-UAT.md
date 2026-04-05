# S02: CodexAgentRunner, provider-aware image selection, and launch path wiring — UAT

**Milestone:** M006-d622bc
**Written:** 2026-04-04T23:55:56.053Z

## UAT: S02 — CodexAgentRunner, provider-aware image selection, and launch path wiring

### Preconditions
- SCC repo at `scc-sync-1.7.3` with M006 S01 and S02 changes applied
- Python 3.10+, uv available
- No Docker required (all tests use mocks)

### Test Case 1: CodexAgentRunner contract compliance
**Steps:**
1. Run `uv run pytest tests/test_codex_agent_runner.py tests/contracts/test_agent_runner_contract.py -v`

**Expected:**
- `test_build_settings_returns_codex_path` passes — settings path is `/home/agent/.codex/config.toml`
- `test_build_command_returns_codex_argv` passes — argv is `["codex"]`, no `--dangerously-skip-permissions`
- `test_describe_returns_codex` passes — returns `"Codex"`
- `test_env_is_clean_str_to_str` passes — env dict is empty (D003 contract)
- Parametric contract tests cover both Claude and Codex runners across all 4 contract properties

### Test Case 2: Provider dispatch routes correctly
**Steps:**
1. Run `uv run pytest tests/test_provider_dispatch.py -v -k "agent_runner or runtime_info"`

**Expected:**
- Codex provider dispatches to `codex_agent_runner` (not the default `agent_runner`)
- Claude provider dispatches to default `agent_runner`
- `runtime_info` is populated from `runtime_probe.probe()` when probe exists
- `runtime_info` is None when runtime_probe is None

### Test Case 3: Provider-aware SandboxSpec population
**Steps:**
1. Run `uv run pytest tests/test_application_start_session.py -v -k "codex"`

**Expected:**
- Codex provider gets `scc-agent-codex:latest` image ref
- Codex provider gets `docker-codex-sandbox-data` volume name
- Codex provider gets `.codex` config dir
- Codex provider gets `["codex"]` agent_argv
- Claude provider still gets `scc-agent-claude:latest`, `docker-claude-sandbox-data`, `.claude`

### Test Case 4: OCI runtime exec command with Codex argv
**Steps:**
1. Run `uv run pytest tests/test_oci_sandbox_runtime.py -v -k "agent_argv or codex"`

**Expected:**
- With `agent_argv=["codex"]`, exec command is `docker exec ... codex` — no `--dangerously-skip-permissions`
- With empty `agent_argv`, exec command falls back to `claude --dangerously-skip-permissions`
- Continue-session with codex argv appends `-c` correctly
- With `data_volume="docker-codex-sandbox-data"`, volume mount uses the codex volume name
- With `config_dir=".codex"`, mount target is `/home/agent/.codex`
- With empty data_volume/config_dir, falls back to existing Claude defaults

### Test Case 5: Backward compatibility — existing Claude path unchanged
**Steps:**
1. Run `uv run pytest tests/test_oci_sandbox_runtime.py -v -k "not codex and not agent_argv"`

**Expected:**
- All pre-existing OCI runtime tests still pass without modification
- Default SandboxSpec (empty agent_argv, empty data_volume, empty config_dir) produces identical Docker commands to pre-S02 behavior

### Test Case 6: Full regression check
**Steps:**
1. Run `uv run pytest --rootdir "$PWD" -q`

**Expected:**
- 4568+ tests pass
- 0 failures
- 23 skipped, 2 xfailed (unchanged from baseline)

### Test Case 7: Codex Dockerfile structure
**Steps:**
1. Verify `images/scc-agent-codex/Dockerfile` exists
2. Check it installs Node.js 20 and `@openai/codex`
3. Check it uses the same user/workdir pattern as `images/scc-agent-claude/Dockerfile`

**Expected:**
- Dockerfile present with Node.js 20 LTS installation
- `@openai/codex` installed globally via npm
- Non-root agent user with `/home/agent` workdir

### Edge Cases
- Unknown provider_id falls back to Claude defaults for image, volume, config_dir, and argv — silent fallback, no crash
- Missing `codex_agent_runner` on adapters (None) raises `InvalidLaunchPlanError` with clear message
- `runtime_probe=None` leaves `runtime_info=None` — no crash, backward compat preserved
