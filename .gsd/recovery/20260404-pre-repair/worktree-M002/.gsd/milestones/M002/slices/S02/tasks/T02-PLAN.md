---
estimated_steps: 4
estimated_files: 5
skills_used:
  - karpathy-guidelines
---

# T02: Add ClaudeAgentProvider characterization tests with typed contract assertions

**Slice:** S02 — Claude adapter extraction and cleanup
**Milestone:** M002

## Description

Add focused TDD-style characterization tests for `src/scc_cli/adapters/claude_agent_provider.py` so Claude becomes the first fully pinned provider on the `AgentProvider` seam. Follow the canonical four-test provider-adapter pattern already established in project knowledge: capability metadata, clean launch spec without settings, settings artifact handling, and the env str-to-str guard. Keep the assertions at the provider-neutral contract edge so later providers can copy the test shape without inheriting Claude-specific leakage. This task must also keep the provider file and new test pyright-clean under scoped checking.

## Negative Tests

- **Malformed inputs**: passing nested config like `{"mcpServers": {}}` must not leak non-string values into `spec.env`.
- **Error paths**: `settings_path=None` must produce empty `artifact_paths`; adding a settings path must add only that artifact reference and keep `env` empty.
- **Boundary conditions**: the test module must pin the exact Claude metadata and `AgentLaunchSpec` shape so future drift fails loudly.

## Steps

1. Create `tests/test_claude_agent_provider.py` and wire it to `ClaudeAgentProvider` using the same style as other contract tests in the repo.
2. Add the canonical four tests covering `capability_profile()`, clean `prepare_launch()` behavior without settings, artifact-path behavior with settings, and the env str-to-str rule.
3. Keep assertions provider-neutral at the contract boundary: validate `provider_id`, `display_name`, `required_destination_set`, `argv`, `required_destination_sets`, `artifact_paths`, and `workdir` without asserting on raw Claude settings payload internals.
4. Run focused provider tests, scoped pyright, and the repo-wide lint/type/test gate.

## Must-Haves

- [ ] `tests/test_claude_agent_provider.py` exists and follows the canonical four-test provider-adapter shape.
- [ ] Claude's `AgentLaunchSpec` contract is pinned explicitly: canonical argv, empty env, correct artifact handling, correct destination set, correct workdir.
- [ ] The new provider test and touched provider file stay scoped-pyright-clean.

## Verification

- `uv run pytest tests/test_claude_agent_provider.py -q`
- `uv run pyright src/scc_cli/adapters/claude_agent_provider.py tests/test_claude_agent_provider.py`
- `uv run ruff check && uv run mypy src/scc_cli && uv run pytest --tb=short -q`

## Observability Impact

- Signals added/changed: `tests/test_claude_agent_provider.py` becomes the first-stop contract diagnostic for Claude seam drift.
- How a future agent inspects this: run the focused pytest command above, then inspect scoped `uv run pyright ...` output for type drift.
- Failure state exposed: wrong provider metadata, wrong `AgentLaunchSpec` shape, missing artifact paths, or env leakage into non-string values.

## Inputs

- `src/scc_cli/adapters/claude_agent_provider.py` — provider implementation under test.
- `src/scc_cli/core/contracts.py` — defines `AgentLaunchSpec` and `ProviderCapabilityProfile` expectations.
- `tests/test_core_contracts.py` — existing contract boundary assertions that establish the provider-neutral seam vocabulary.
- `tests/fakes/fake_agent_provider.py` — reference shape for provider seam tests already used elsewhere.

## Expected Output

- `tests/test_claude_agent_provider.py` — dedicated Claude provider characterization coverage pinning the seam contract.
