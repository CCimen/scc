# S02 Research: CodexAgentRunner, provider-aware image selection, and launch path wiring

## Summary

This is targeted research. The pattern is fully established by ClaudeAgentRunner and ClaudeAgentProvider. S02 replicates it for Codex, adds a Codex image constant, a Codex Dockerfile, wires provider-aware runner dispatch through the dependency builder, and makes the OCI runtime consume provider-owned argv instead of hardcoded `AGENT_NAME`. The work is medium complexity — the runner itself is trivial, but threading provider identity through `SandboxSpec` → OCI exec touches a well-tested adapter and must not regress 4529+ existing tests.

## Recommendation

Three tasks:

1. **CodexAgentRunner + image contracts + Dockerfile** — Create the runner adapter, add `SCC_CODEX_IMAGE` / `SCC_CODEX_IMAGE_REF` to `image_contracts.py`, create `images/scc-agent-codex/Dockerfile`. Tests: canonical 4-test runner shape + image contract tests.

2. **Provider-aware runner dispatch + image selection in start_session** — Add `codex_agent_runner` to `DefaultAdapters` + bootstrap. Extend `_PROVIDER_DISPATCH` in `dependencies.py` with `agent_runner` field. Make `build_start_session_dependencies` dispatch `agent_runner` per-provider. Make `_build_sandbox_spec` select image ref from provider instead of the hardcoded `SCC_CLAUDE_IMAGE_REF`. Thread `runtime_info` into `build_start_session_dependencies` so OCI backend detection works.

3. **OCI runtime provider-aware exec** — Add `agent_argv: tuple[str, ...] | None` field to `SandboxSpec`. Propagate from `AgentLaunchSpec.argv` in `_build_sandbox_spec`. Update `_build_exec_cmd` to use `spec.agent_argv` when present, falling back to `AGENT_NAME` for backward compat. This is the riskiest change — 483-line test file covers the OCI runtime.

## Implementation Landscape

### What exists

| Component | File | Status |
|-----------|------|--------|
| `AgentRunner` protocol | `ports/agent_runner.py` | 3 methods: `build_settings`, `build_command`, `describe` |
| `ClaudeAgentRunner` | `adapters/claude_agent_runner.py` | Complete — template for Codex |
| `CodexAgentProvider` | `adapters/codex_agent_provider.py` | Complete — already has `argv=("codex",)` in `prepare_launch` |
| `DefaultAdapters` | `bootstrap.py` | Has `agent_runner: AgentRunner` (always `ClaudeAgentRunner()`), no `codex_agent_runner` field |
| `_PROVIDER_DISPATCH` | `commands/launch/dependencies.py` | Maps `agent_provider` and `safety_adapter` per provider, but NOT `agent_runner` |
| `build_start_session_dependencies` | `commands/launch/dependencies.py` | Dispatches `agent_provider` per provider, but hardcodes `adapters.agent_runner` |
| `_build_sandbox_spec` | `application/start_session.py` | Hardcodes `SCC_CLAUDE_IMAGE_REF` for OCI, `SANDBOX_IMAGE` for Desktop |
| `OciSandboxRuntime._build_exec_cmd` | `adapters/oci_sandbox_runtime.py` | Hardcodes `AGENT_NAME` ("claude") + `--dangerously-skip-permissions` |
| `OciSandboxRuntime._build_create_cmd` | `adapters/oci_sandbox_runtime.py` | Hardcodes `SANDBOX_DATA_VOLUME` ("docker-claude-sandbox-data") → `{_AGENT_HOME}/.claude` |
| `SandboxSpec` | `ports/models.py` | No `agent_argv` or `provider_id` field |
| `image_contracts.py` | `core/image_contracts.py` | Has `SCC_CLAUDE_IMAGE` and `SCC_CLAUDE_IMAGE_REF`, no Codex equivalents |
| `images/scc-agent-codex/` | Does not exist | Needs Dockerfile modeled on `images/scc-agent-claude/Dockerfile` |
| Fake runner | `tests/fakes/fake_agent_runner.py` | Single fake, used for both providers |

### What needs building

1. **`adapters/codex_agent_runner.py`** — New file. Mirror `ClaudeAgentRunner`:
   - `build_settings`: identical pattern, path default `/home/agent/.codex/config.toml` (Codex uses `.codex/` config dir)
   - `build_command`: `argv=["codex"]` (no `--dangerously-skip-permissions` — Claude-specific)
   - `describe`: `"Codex"`

2. **`core/image_contracts.py`** — Add `SCC_CODEX_IMAGE = ImageRef(repository="scc-agent-codex", tag="latest")` and `SCC_CODEX_IMAGE_REF = "scc-agent-codex:latest"`

3. **`images/scc-agent-codex/Dockerfile`** — Based on scc-base, install Node.js 20 LTS + `@openai/codex` via npm. Verify with `codex --version`. Same user/workdir pattern as Claude image.

4. **`bootstrap.py`** — Add `codex_agent_runner: AgentRunner | None = None` field to `DefaultAdapters` (with `| None = None` default per KNOWLEDGE.md pattern). Instantiate `CodexAgentRunner()` in `get_default_adapters()`.

5. **`commands/launch/dependencies.py`** — Add `agent_runner` to `_PROVIDER_DISPATCH` entries (`{"agent_runner": "agent_runner"}` for claude, `{"agent_runner": "codex_agent_runner"}` for codex). Update `build_start_session_dependencies` to dispatch `agent_runner` from the table. Thread `runtime_info` from `adapters.runtime_probe` into `StartSessionDependencies`.

6. **`application/start_session.py`** — Make `_build_sandbox_spec` provider-aware for image selection. Instead of hardcoded `SCC_CLAUDE_IMAGE_REF`, resolve image from `agent_provider.capability_profile().provider_id` → image ref lookup. Propagate `AgentLaunchSpec.argv` into `SandboxSpec` for the OCI runtime.

7. **`ports/models.py`** — Add `agent_argv: tuple[str, ...] = ()` to `SandboxSpec` for the OCI exec path.

8. **`adapters/oci_sandbox_runtime.py`** — Update `_build_exec_cmd` to use `spec.agent_argv` when present (non-empty tuple), falling back to current `[AGENT_NAME, "--dangerously-skip-permissions"]` for backward compat. Consider making credential volume provider-aware (derive from provider_id rather than hardcoded `SANDBOX_DATA_VOLUME`).

### Key constraints

- **Per KNOWLEDGE.md**: When adding a new field to `DefaultAdapters`, use `| None = None` default and grep all construction sites: `build_fake_adapters()`, inline `DefaultAdapters()` in tests.
- **Per KNOWLEDGE.md**: The canonical 4-test shape for a new adapter applies to `CodexAgentRunner`: (1) settings build, (2) command build, (3) describe, (4) env contract (D003).
- **Per D027**: `ProviderRuntimeSpec` was planned as a separate model from `CapabilityProfile`. However, for S02's scope, we don't need the full model yet — image ref and agent argv can be derived from existing `AgentLaunchSpec` and a simple provider_id → image_ref mapping. The full `ProviderRuntimeSpec` can be introduced later if needed.
- **Per D028 constraint 4**: For missing images, `docker build -t scc-agent-{provider}:latest images/scc-agent-{provider}/` is the standardized command. The Dockerfile must live at the expected path.
- **Per D028 constraint 5**: Container names, volume names, and session identity must include provider to support coexistence. However, container naming and session identity are S04's coexistence test scope. S02's scope is image selection and exec command.
- **OCI exec risk**: The `_build_exec_cmd` method is tested by 483 lines of tests. Changes must preserve backward compat for Claude and add Codex's behavior.
- **`runtime_info` gap**: `build_start_session_dependencies` doesn't currently set `runtime_info`, so `_build_sandbox_spec` always falls back to `SANDBOX_IMAGE` (Docker Desktop template). For OCI backend support, `runtime_info` must be threaded from `adapters.runtime_probe` through to `StartSessionDependencies`. However, the probe needs the actual runtime probe call — in `build_start_session_dependencies`, `adapters.runtime_probe` is available.

### Credential volume naming

Currently hardcoded: `SANDBOX_DATA_VOLUME` = `"docker-claude-sandbox-data"` → mounted at `/home/agent/.claude`. For Codex, the config dir is `.codex/`. The volume name and mount target need to be provider-aware for coexistence. Options:
- Add `data_volume` and `config_mount_path` to `SandboxSpec`
- Derive from a provider_id → constants mapping in the OCI runtime

The cleanest approach: add `data_volume: str = ""` and `config_dir: str = ""` fields to `SandboxSpec`, populated from the provider_id in `_build_sandbox_spec`. The OCI runtime reads these instead of hardcoded constants. Fallback to current values when empty (backward compat).

### Image selection approach

Rather than introducing `ProviderRuntimeSpec` now, use a simple mapping:

```python
_PROVIDER_IMAGE_REF: dict[str, str] = {
    "claude": SCC_CLAUDE_IMAGE_REF,
    "codex": SCC_CODEX_IMAGE_REF,
}
```

In `_build_sandbox_spec`, look up `request.provider_id` (or `agent_provider.capability_profile().provider_id`) in this dict. This keeps the change minimal and avoids a new model that would need to be threaded through the entire launch flow.

### Files likely touched

| File | Change |
|------|--------|
| `adapters/codex_agent_runner.py` | New — CodexAgentRunner class |
| `core/image_contracts.py` | Add SCC_CODEX_IMAGE, SCC_CODEX_IMAGE_REF |
| `images/scc-agent-codex/Dockerfile` | New — Codex container image |
| `bootstrap.py` | Add codex_agent_runner field + instantiation |
| `commands/launch/dependencies.py` | Add agent_runner to dispatch, thread runtime_info |
| `application/start_session.py` | Provider-aware image selection, propagate agent_argv into SandboxSpec |
| `ports/models.py` | Add agent_argv + data_volume + config_dir to SandboxSpec |
| `adapters/oci_sandbox_runtime.py` | Use spec.agent_argv in exec, spec.data_volume in create |
| `tests/fakes/__init__.py` | Add codex_agent_runner to build_fake_adapters |
| `tests/test_codex_agent_runner.py` | New — 4-test canonical shape |
| `tests/test_oci_sandbox_runtime.py` | Add Codex exec tests, data_volume tests |
| `tests/contracts/test_agent_runner_contract.py` | Add Codex runner contract test |
| `tests/test_application_start_session.py` | Provider-aware image selection tests |
| `tests/test_provider_dispatch.py` | Runner dispatch tests |

### Verification

- `uv run pytest tests/test_codex_agent_runner.py -v` — 4+ tests pass
- `uv run pytest tests/test_oci_sandbox_runtime.py -v` — all existing + new Codex tests pass
- `uv run pytest tests/test_provider_dispatch.py -v` — runner dispatch tests pass
- `uv run ruff check` — clean
- `uv run mypy src/scc_cli/adapters/codex_agent_runner.py src/scc_cli/core/image_contracts.py src/scc_cli/ports/models.py src/scc_cli/adapters/oci_sandbox_runtime.py src/scc_cli/application/start_session.py src/scc_cli/commands/launch/dependencies.py src/scc_cli/bootstrap.py` — no issues
- `uv run pytest --rootdir "$PWD" -q` — full suite, zero regressions
