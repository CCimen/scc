---
estimated_steps: 79
estimated_files: 5
skills_used: []
---

# T02: Provider-aware runner dispatch, runtime_info threading, and image selection

---
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

## Inputs

- `src/scc_cli/adapters/codex_agent_runner.py`
- `src/scc_cli/core/image_contracts.py`
- `src/scc_cli/bootstrap.py`
- `src/scc_cli/commands/launch/dependencies.py`
- `src/scc_cli/application/start_session.py`
- `src/scc_cli/ports/models.py`
- `tests/test_provider_dispatch.py`

## Expected Output

- `src/scc_cli/commands/launch/dependencies.py`
- `src/scc_cli/application/start_session.py`
- `src/scc_cli/ports/models.py`
- `tests/test_provider_dispatch.py`
- `tests/test_application_start_session.py`

## Verification

uv run pytest tests/test_provider_dispatch.py tests/test_application_start_session.py -v && uv run ruff check src/scc_cli/commands/launch/dependencies.py src/scc_cli/application/start_session.py src/scc_cli/ports/models.py && uv run mypy src/scc_cli/commands/launch/dependencies.py src/scc_cli/application/start_session.py src/scc_cli/ports/models.py && uv run pytest --rootdir "$PWD" -q
