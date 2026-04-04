# S02: CodexAgentRunner, provider-aware image selection, and launch path wiring

**Goal:** scc start --provider codex builds a Codex-specific SandboxSpec with the right image, settings path, and agent command. The launch reaches Docker exec with codex argv.
**Demo:** After this: scc start --provider codex builds a Codex-specific SandboxSpec with the right image, settings path, and agent command. The launch reaches Docker exec with codex argv.

## Tasks
- [x] **T01: Created CodexAgentRunner adapter with codex argv and .codex settings path, added Codex image constants, Dockerfile, and 13 passing tests including parametric contract coverage** — ---
estimated_steps: 5
estimated_files: 6
skills_used: []
---

# T01: CodexAgentRunner adapter, Codex image contracts, and Dockerfile

**Slice:** S02 — CodexAgentRunner, provider-aware image selection, and launch path wiring
**Milestone:** M006-d622bc

## Description

Create the CodexAgentRunner adapter, add Codex image constants, create the Codex Dockerfile, and register the runner in bootstrap and fakes. This is the foundation — downstream tasks depend on this runner and image ref existing.

## Steps

1. Create `src/scc_cli/adapters/codex_agent_runner.py` mirroring `claude_agent_runner.py`. Key differences:
   - `DEFAULT_SETTINGS_PATH = Path("/home/agent/.codex/config.toml")` (Codex uses `.codex/` config dir)
   - `build_command` returns `argv=["codex"]` (no `--dangerously-skip-permissions` — that's Claude-specific)
   - `describe` returns `"Codex"`

2. Add Codex image constants to `src/scc_cli/core/image_contracts.py`:
   - `SCC_CODEX_IMAGE = ImageRef(repository="scc-agent-codex", tag="latest")`
   - `SCC_CODEX_IMAGE_REF = "scc-agent-codex:latest"`

3. Create `images/scc-agent-codex/Dockerfile` based on `images/scc-agent-claude/Dockerfile`. Install Node.js 20 LTS + `@openai/codex` via npm. Verify with `codex --version`. Same user/workdir pattern.

4. Add `codex_agent_runner: AgentRunner | None = None` field to `DefaultAdapters` in `src/scc_cli/bootstrap.py` (use `| None = None` default per KNOWLEDGE.md pattern). Instantiate `CodexAgentRunner()` in `get_default_adapters()`. Import `CodexAgentRunner` at the top.

5. Add `codex_agent_runner=FakeAgentRunner()` to `build_fake_adapters()` in `tests/fakes/__init__.py`. Also add `FakeAgentRunner()` to any inline `DefaultAdapters()` constructions in test files (grep for them).

6. Create `tests/test_codex_agent_runner.py` with the canonical 4-test shape per KNOWLEDGE.md:
   - `test_build_settings_returns_codex_path` — settings path is `/home/agent/.codex/config.toml`
   - `test_build_command_returns_codex_argv` — argv starts with `"codex"`, no `--dangerously-skip-permissions`
   - `test_describe_returns_codex` — returns `"Codex"`
   - `test_env_is_clean_str_to_str` — env dict is empty (D003 contract guard)
   Add Codex runner to `tests/contracts/test_agent_runner_contract.py` alongside Claude.

## Must-Haves

- [ ] CodexAgentRunner implements AgentRunner protocol with codex argv, .codex settings path, and "Codex" describe
- [ ] SCC_CODEX_IMAGE and SCC_CODEX_IMAGE_REF exist in image_contracts.py
- [ ] images/scc-agent-codex/Dockerfile installs Node.js 20 + @openai/codex
- [ ] codex_agent_runner field added to DefaultAdapters with None default
- [ ] FakeAgentRunner() wired into build_fake_adapters() for codex_agent_runner
- [ ] 4+ tests pass for CodexAgentRunner, contract test covers both runners

## Verification

- `uv run pytest tests/test_codex_agent_runner.py tests/contracts/test_agent_runner_contract.py -v` — all pass
- `uv run ruff check src/scc_cli/adapters/codex_agent_runner.py src/scc_cli/core/image_contracts.py src/scc_cli/bootstrap.py` — clean
- `uv run mypy src/scc_cli/adapters/codex_agent_runner.py src/scc_cli/core/image_contracts.py src/scc_cli/bootstrap.py` — no issues
- `uv run pytest --rootdir "$PWD" -q` — full suite, zero regressions

## Inputs

- `src/scc_cli/adapters/claude_agent_runner.py` — template for the new runner
- `src/scc_cli/core/image_contracts.py` — add Codex constants alongside Claude
- `images/scc-agent-claude/Dockerfile` — template for Codex Dockerfile
- `src/scc_cli/bootstrap.py` — add codex_agent_runner field and instantiation
- `tests/fakes/__init__.py` — add codex_agent_runner to build_fake_adapters
- `tests/contracts/test_agent_runner_contract.py` — extend with Codex runner

## Expected Output

- `src/scc_cli/adapters/codex_agent_runner.py` — new CodexAgentRunner adapter
- `src/scc_cli/core/image_contracts.py` — SCC_CODEX_IMAGE + SCC_CODEX_IMAGE_REF added
- `images/scc-agent-codex/Dockerfile` — new Codex container image definition
- `src/scc_cli/bootstrap.py` — codex_agent_runner field and wiring
- `tests/fakes/__init__.py` — codex_agent_runner in fake adapters
- `tests/test_codex_agent_runner.py` — new 4-test file
- `tests/contracts/test_agent_runner_contract.py` — Codex runner contract test added
  - Estimate: 30m
  - Files: src/scc_cli/adapters/codex_agent_runner.py, src/scc_cli/core/image_contracts.py, images/scc-agent-codex/Dockerfile, src/scc_cli/bootstrap.py, tests/fakes/__init__.py, tests/test_codex_agent_runner.py, tests/contracts/test_agent_runner_contract.py
  - Verify: uv run pytest tests/test_codex_agent_runner.py tests/contracts/test_agent_runner_contract.py -v && uv run ruff check src/scc_cli/adapters/codex_agent_runner.py src/scc_cli/core/image_contracts.py src/scc_cli/bootstrap.py && uv run mypy src/scc_cli/adapters/codex_agent_runner.py src/scc_cli/core/image_contracts.py src/scc_cli/bootstrap.py && uv run pytest --rootdir "$PWD" -q
- [x] **T02: Wired CodexAgentRunner into provider dispatch table, threaded runtime_info from probe, and made image selection and agent_argv provider-aware with 10 new tests** — ---
estimated_steps: 5
estimated_files: 7
skills_used: []
---

# T02: Provider-aware runner dispatch, runtime_info threading, and image selection

**Slice:** S02 — CodexAgentRunner, provider-aware image selection, and launch path wiring
**Milestone:** M006-d622bc

## Description

Wire the CodexAgentRunner (created in T01) into the provider dispatch table, thread runtime_info from the probe into StartSessionDependencies, and make _build_sandbox_spec select the image ref by provider_id instead of hardcoding SCC_CLAUDE_IMAGE_REF. This is the critical wiring task that connects provider selection (S01) to provider-specific runtime behavior.

## Steps

1. Add `agent_runner` to `_PROVIDER_DISPATCH` in `src/scc_cli/commands/launch/dependencies.py`:
   ```python
   _PROVIDER_DISPATCH = {
       "claude": {
           "agent_provider": "agent_provider",
           "safety_adapter": "claude_safety_adapter",
           "agent_runner": "agent_runner",
       },
       "codex": {
           "agent_provider": "codex_agent_provider",
           "safety_adapter": "codex_safety_adapter",
           "agent_runner": "codex_agent_runner",
       },
   }
   ```
   Update `build_start_session_dependencies` to dispatch `agent_runner` from the table (currently hardcodes `adapters.agent_runner`). Use the same `getattr` + require pattern as agent_provider. Thread `runtime_info` from `adapters.runtime_probe.probe()` if `adapters.runtime_probe` is not None — set it on `StartSessionDependencies`.

2. Add a provider_id → image_ref mapping in `src/scc_cli/application/start_session.py`:
   ```python
   from scc_cli.core.image_contracts import SCC_CLAUDE_IMAGE_REF, SCC_CODEX_IMAGE_REF

   _PROVIDER_IMAGE_REF: dict[str, str] = {
       "claude": SCC_CLAUDE_IMAGE_REF,
       "codex": SCC_CODEX_IMAGE_REF,
   }
   ```
   Update `_build_sandbox_spec` to look up `agent_provider.capability_profile().provider_id` in `_PROVIDER_IMAGE_REF` instead of hardcoding `SCC_CLAUDE_IMAGE_REF`. Fall back to `SCC_CLAUDE_IMAGE_REF` for unknown providers.

3. Thread `AgentLaunchSpec.argv` into `SandboxSpec` — add the `agent_argv` field to SandboxSpec in `src/scc_cli/ports/models.py` (see T03 for the field, but the population happens here). In `_build_sandbox_spec`, if `agent_provider` is not None, get the launch spec and populate `agent_argv` from it. Actually — `AgentLaunchSpec` is already built by `_build_agent_launch_spec` separately. The cleanest approach: build the `AgentLaunchSpec` first, then pass its argv into `_build_sandbox_spec`. Refactor `prepare_start_session` to build agent_launch_spec before sandbox_spec, then pass `agent_launch_spec.argv` into `_build_sandbox_spec` as `agent_argv`.

4. Add tests to `tests/test_provider_dispatch.py`:
   - `test_codex_dispatch_uses_codex_agent_runner` — verifies codex provider gets codex_agent_runner
   - `test_claude_dispatch_uses_claude_agent_runner` — verifies claude gets the default agent_runner
   - `test_runtime_info_threaded_from_probe` — verifies runtime_info is populated when probe exists

5. Add tests to `tests/test_application_start_session.py`:
   - `test_build_sandbox_spec_codex_image_for_oci` — when provider=codex and backend=oci, image is SCC_CODEX_IMAGE_REF
   - `test_build_sandbox_spec_claude_image_for_oci` — when provider=claude and backend=oci, image is SCC_CLAUDE_IMAGE_REF
   - `test_build_sandbox_spec_agent_argv_from_launch_spec` — agent_argv populated from provider's argv

## Negative Tests

- **Malformed inputs**: unknown provider_id falls back to claude runner/image (not crash)
- **Error paths**: missing codex_agent_runner on adapters (None) raises clear error via _require pattern
- **Boundary conditions**: runtime_probe=None means runtime_info stays None — backward compat

## Must-Haves

- [ ] agent_runner dispatched per-provider from _PROVIDER_DISPATCH table
- [ ] runtime_info threaded from runtime_probe.probe() into StartSessionDependencies
- [ ] _build_sandbox_spec selects image by provider_id, not hardcoded Claude
- [ ] agent_argv from AgentLaunchSpec flows into SandboxSpec
- [ ] Unknown provider_id falls back safely to claude defaults
- [ ] Tests cover runner dispatch, runtime_info threading, and image selection

## Verification

- `uv run pytest tests/test_provider_dispatch.py tests/test_application_start_session.py -v` — all pass
- `uv run ruff check src/scc_cli/commands/launch/dependencies.py src/scc_cli/application/start_session.py src/scc_cli/ports/models.py` — clean
- `uv run mypy src/scc_cli/commands/launch/dependencies.py src/scc_cli/application/start_session.py src/scc_cli/ports/models.py` — no issues
- `uv run pytest --rootdir "$PWD" -q` — full suite, zero regressions

## Observability Impact

- Signals added/changed: runtime_info now flows into StartSessionDependencies, making OCI backend detection work in the live launch path
- How a future agent inspects this: check dependencies.runtime_info in debug or dry-run; _PROVIDER_DISPATCH table is inspectable
- Failure state exposed: missing runner raises InvalidLaunchPlanError with clear message

## Inputs

- `src/scc_cli/adapters/codex_agent_runner.py` — created in T01
- `src/scc_cli/core/image_contracts.py` — SCC_CODEX_IMAGE_REF from T01
- `src/scc_cli/bootstrap.py` — codex_agent_runner field from T01
- `src/scc_cli/commands/launch/dependencies.py` — dispatch table to extend
- `src/scc_cli/application/start_session.py` — _build_sandbox_spec to make provider-aware
- `src/scc_cli/ports/models.py` — SandboxSpec to extend with agent_argv
- `tests/test_provider_dispatch.py` — existing dispatch tests to extend

## Expected Output

- `src/scc_cli/commands/launch/dependencies.py` — agent_runner dispatch + runtime_info threading
- `src/scc_cli/application/start_session.py` — provider-aware image selection + agent_argv propagation
- `src/scc_cli/ports/models.py` — agent_argv field on SandboxSpec
- `tests/test_provider_dispatch.py` — runner dispatch + runtime_info tests added
- `tests/test_application_start_session.py` — provider-aware image + argv tests added
  - Estimate: 45m
  - Files: src/scc_cli/commands/launch/dependencies.py, src/scc_cli/application/start_session.py, src/scc_cli/ports/models.py, tests/test_provider_dispatch.py, tests/test_application_start_session.py
  - Verify: uv run pytest tests/test_provider_dispatch.py tests/test_application_start_session.py -v && uv run ruff check src/scc_cli/commands/launch/dependencies.py src/scc_cli/application/start_session.py src/scc_cli/ports/models.py && uv run mypy src/scc_cli/commands/launch/dependencies.py src/scc_cli/application/start_session.py src/scc_cli/ports/models.py && uv run pytest --rootdir "$PWD" -q
- [ ] **T03: OCI runtime provider-aware exec command and credential volume mounting** — ---
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
  - Estimate: 45m
  - Files: src/scc_cli/ports/models.py, src/scc_cli/adapters/oci_sandbox_runtime.py, src/scc_cli/application/start_session.py, tests/test_oci_sandbox_runtime.py, tests/test_application_start_session.py
  - Verify: uv run pytest tests/test_oci_sandbox_runtime.py tests/test_application_start_session.py -v && uv run ruff check src/scc_cli/adapters/oci_sandbox_runtime.py src/scc_cli/ports/models.py src/scc_cli/application/start_session.py && uv run mypy src/scc_cli/adapters/oci_sandbox_runtime.py src/scc_cli/ports/models.py src/scc_cli/application/start_session.py && uv run pytest --rootdir "$PWD" -q
