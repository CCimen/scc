---
estimated_steps: 76
estimated_files: 5
skills_used: []
---

# T03: OCI runtime provider-aware exec command and credential volume mounting

---
estimated_steps: 5
estimated_files: 5
skills_used: []
---

# T03: OCI runtime provider-aware exec command and credential volume mounting

**Slice:** S02 — CodexAgentRunner, provider-aware image selection, and launch path wiring
**Milestone:** M006-d622bc

## Description

This is the highest-risk task in S02. The OCI sandbox runtime has 483 lines of tests and hardcodes `AGENT_NAME` ("claude") and `SANDBOX_DATA_VOLUME` ("docker-claude-sandbox-data") with a `.claude` mount path. This task makes `_build_exec_cmd` use `spec.agent_argv` when present and `_build_create_cmd` use `spec.data_volume` and `spec.config_dir` when present, with backward-compat fallbacks.

## Steps

1. Add `data_volume: str = ""` and `config_dir: str = ""` fields to `SandboxSpec` in `src/scc_cli/ports/models.py`. These are populated by `_build_sandbox_spec` in T02's changes — but T02 only added `agent_argv`. Extend `_build_sandbox_spec` in `src/scc_cli/application/start_session.py` to also populate `data_volume` and `config_dir` based on provider_id:
   ```python
   _PROVIDER_DATA_VOLUME: dict[str, str] = {
       "claude": "docker-claude-sandbox-data",
       "codex": "docker-codex-sandbox-data",
   }
   _PROVIDER_CONFIG_DIR: dict[str, str] = {
       "claude": ".claude",
       "codex": ".codex",
   }
   ```
   Look up using `provider_id` from the capability profile. Fall back to existing constants for unknown providers.

2. Update `_build_exec_cmd` in `src/scc_cli/adapters/oci_sandbox_runtime.py`:
   - When `spec.agent_argv` is non-empty, use `list(spec.agent_argv)` as the command instead of `[AGENT_NAME, "--dangerously-skip-permissions"]`
   - When `spec.agent_argv` is empty (default), fall back to existing `[AGENT_NAME, "--dangerously-skip-permissions"]` for backward compat
   - Append `-c` for continue_session regardless of path
   - Note: `--dangerously-skip-permissions` is Claude-specific. Codex's argv will be just `("codex",)` from CodexAgentProvider.prepare_launch. The exec command must not add Claude-specific flags when using provider argv.

3. Update `_build_create_cmd` in `src/scc_cli/adapters/oci_sandbox_runtime.py`:
   - When `spec.data_volume` is non-empty, use it instead of `SANDBOX_DATA_VOLUME`
   - When `spec.config_dir` is non-empty, mount at `{_AGENT_HOME}/{spec.config_dir}` instead of `{_AGENT_HOME}/.claude`
   - When both are empty, fall back to existing `SANDBOX_DATA_VOLUME` and `.claude` path

4. Add tests to `tests/test_oci_sandbox_runtime.py`:
   - `test_build_exec_cmd_uses_agent_argv_when_present` — with `agent_argv=("codex",)`, exec cmd uses `codex` not `claude --dangerously-skip-permissions`
   - `test_build_exec_cmd_falls_back_to_agent_name` — empty agent_argv uses existing AGENT_NAME behavior
   - `test_build_exec_cmd_continue_session_with_codex_argv` — `-c` appended after codex argv
   - `test_build_create_cmd_uses_data_volume_when_present` — with data_volume="docker-codex-sandbox-data", volume mount uses it
   - `test_build_create_cmd_uses_config_dir_when_present` — with config_dir=".codex", mount target is `/home/agent/.codex`
   - `test_build_create_cmd_falls_back_to_defaults` — empty data_volume/config_dir uses existing constants

5. Add image selection tests for data_volume/config_dir in `tests/test_application_start_session.py`:
   - `test_build_sandbox_spec_codex_data_volume` — codex provider gets codex data volume name
   - `test_build_sandbox_spec_codex_config_dir` — codex provider gets .codex config dir

## Negative Tests

- **Boundary conditions**: empty agent_argv tuple → falls back to AGENT_NAME + --dangerously-skip-permissions (existing behavior preserved)
- **Boundary conditions**: empty data_volume string → falls back to SANDBOX_DATA_VOLUME constant
- **Boundary conditions**: empty config_dir string → falls back to .claude mount path
- **Error paths**: continue_session flag works correctly with both provider argv and default argv

## Must-Haves

- [ ] _build_exec_cmd uses spec.agent_argv when non-empty, falls back to AGENT_NAME for empty
- [ ] _build_create_cmd uses spec.data_volume and spec.config_dir when non-empty, falls back to constants
- [ ] data_volume and config_dir fields on SandboxSpec
- [ ] _build_sandbox_spec populates data_volume and config_dir by provider_id
- [ ] All existing OCI runtime tests still pass (backward compat)
- [ ] 6+ new tests cover codex exec/volume/config_dir paths plus fallbacks

## Verification

- `uv run pytest tests/test_oci_sandbox_runtime.py -v` — all existing + new tests pass
- `uv run pytest tests/test_application_start_session.py -v` — volume/config_dir tests pass
- `uv run ruff check src/scc_cli/adapters/oci_sandbox_runtime.py src/scc_cli/ports/models.py src/scc_cli/application/start_session.py` — clean
- `uv run mypy src/scc_cli/adapters/oci_sandbox_runtime.py src/scc_cli/ports/models.py src/scc_cli/application/start_session.py` — no issues
- `uv run pytest --rootdir "$PWD" -q` — full suite, zero regressions

## Observability Impact

- Signals added/changed: SandboxSpec now carries data_volume and config_dir, visible in any diagnostic dump of the spec
- How a future agent inspects this: inspect SandboxSpec fields in test fixtures or dry-run debug output
- Failure state exposed: no new error types — existing SandboxLaunchError wrapping covers all subprocess failures

## Inputs

- `src/scc_cli/ports/models.py` — SandboxSpec with agent_argv from T02
- `src/scc_cli/adapters/oci_sandbox_runtime.py` — _build_exec_cmd and _build_create_cmd to modify
- `src/scc_cli/application/start_session.py` — _build_sandbox_spec from T02 to extend with volume/config_dir
- `tests/test_oci_sandbox_runtime.py` — existing 483-line test file to extend
- `tests/test_application_start_session.py` — existing test file to extend

## Expected Output

- `src/scc_cli/ports/models.py` — data_volume and config_dir fields added to SandboxSpec
- `src/scc_cli/adapters/oci_sandbox_runtime.py` — provider-aware _build_exec_cmd and _build_create_cmd
- `src/scc_cli/application/start_session.py` — data_volume and config_dir population in _build_sandbox_spec
- `tests/test_oci_sandbox_runtime.py` — 6+ new tests for codex exec/volume/fallback
- `tests/test_application_start_session.py` — volume/config_dir tests added

## Inputs

- `src/scc_cli/ports/models.py`
- `src/scc_cli/adapters/oci_sandbox_runtime.py`
- `src/scc_cli/application/start_session.py`
- `tests/test_oci_sandbox_runtime.py`
- `tests/test_application_start_session.py`

## Expected Output

- `src/scc_cli/ports/models.py`
- `src/scc_cli/adapters/oci_sandbox_runtime.py`
- `src/scc_cli/application/start_session.py`
- `tests/test_oci_sandbox_runtime.py`
- `tests/test_application_start_session.py`

## Verification

uv run pytest tests/test_oci_sandbox_runtime.py tests/test_application_start_session.py -v && uv run ruff check src/scc_cli/adapters/oci_sandbox_runtime.py src/scc_cli/ports/models.py src/scc_cli/application/start_session.py && uv run mypy src/scc_cli/adapters/oci_sandbox_runtime.py src/scc_cli/ports/models.py src/scc_cli/application/start_session.py && uv run pytest --rootdir "$PWD" -q
