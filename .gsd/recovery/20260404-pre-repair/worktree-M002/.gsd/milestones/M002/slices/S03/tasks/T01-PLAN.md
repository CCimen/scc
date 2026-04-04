---
estimated_steps: 16
estimated_files: 6
skills_used: []
---

# T01: Implement CodexAgentProvider and pin the adapter contract

Create the second concrete `AgentProvider` implementation in its own adapter module so the provider seam is exercised by two real providers, not just Claude. Mirror the Claude provider's shape at the contract edge, but keep Codex-specific facts honest: `openai-core` destinations, minimal `argv`, no resume support yet, and file-based settings ownership via `artifact_paths`.

## Steps

1. Add `src/scc_cli/adapters/codex_agent_provider.py` implementing `capability_profile()` and `prepare_launch(...)` with signatures that match `src/scc_cli/ports/agent_provider.py` exactly.
2. Use `src/scc_cli/adapters/claude_agent_provider.py` and `tests/test_claude_agent_provider.py` as structure references only; do not copy Claude-only defaults or leak provider-native fields into `AgentLaunchSpec`.
3. Add `tests/test_codex_agent_provider.py` in the canonical four-test provider-adapter shape: metadata, clean launch without settings, settings artifact-path handling, and env str-to-str safety.
4. Keep the adapter file-based: `settings_path` becomes `artifact_paths`, `env` stays empty, and no shell-expanded provider config is introduced.
5. Run the focused adapter suite plus scoped type/lint checks and fix any local regressions before handoff.

## Must-Haves

- [ ] `CodexAgentProvider` conforms to `AgentProvider` without adding Codex-specific fields to shared core contracts.
- [ ] `tests/test_codex_agent_provider.py` mirrors the canonical four-test provider characterization pattern used for Claude.
- [ ] The adapter reports honest Codex capability metadata (`openai-core`; no resume, skills, or native integrations yet).
- [ ] The touched area stays maintainable under R001 by adding a small standalone adapter module instead of widening core launch orchestration.

## Negative Tests

- **Malformed inputs**: `config={}` and `settings_path=None` still produce a clean spec.
- **Error paths**: the env-contract test fails if nested or non-string env data leaks into the launch spec.
- **Boundary conditions**: empty config, absent settings, and one settings artifact path are all covered explicitly.

## Inputs

- ``src/scc_cli/ports/agent_provider.py``
- ``src/scc_cli/core/contracts.py``
- ``src/scc_cli/adapters/claude_agent_provider.py``
- ``tests/test_claude_agent_provider.py``

## Expected Output

- ``src/scc_cli/adapters/codex_agent_provider.py``
- ``tests/test_codex_agent_provider.py``

## Verification

uv run pytest tests/test_codex_agent_provider.py -q && uv run pyright src/scc_cli/adapters/codex_agent_provider.py tests/test_codex_agent_provider.py && uv run ruff check && uv run mypy src/scc_cli

## Observability Impact

Focused adapter tests become the first-stop diagnostic for Codex seam drift; inspect with `uv run pytest tests/test_codex_agent_provider.py -q`, which exposes provider metadata, argv, artifact-path, and env-contract regressions without touching a live Codex binary.
