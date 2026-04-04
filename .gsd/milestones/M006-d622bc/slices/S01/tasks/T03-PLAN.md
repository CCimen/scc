---
estimated_steps: 19
estimated_files: 3
skills_used: []
---

# T03: Bootstrap dispatch wiring and slice-level verification

Wire provider resolution into the launch path so bootstrap dispatches the correct adapters:

1. Update `build_start_session_dependencies()` in `src/scc_cli/commands/launch/dependencies.py` to accept a `provider_id: str` parameter. Use it to select the correct `agent_provider` and `safety_adapter` from `DefaultAdapters`:
   - `'claude'` → `adapters.agent_provider`, `adapters.claude_safety_adapter`
   - `'codex'` → `adapters.codex_agent_provider`, `adapters.codex_safety_adapter`
   - For `agent_runner`: always use `adapters.agent_runner` (ClaudeAgentRunner) for now — CodexAgentRunner is S02's scope. If provider_id is 'codex' and no codex runner exists, this is acceptable — the runner will error at actual launch time in S02.
   Use a dict-based lookup, not an if/else chain.

2. Update `prepare_live_start_plan()` in the same file to accept and pass through `provider_id`.

3. In `src/scc_cli/commands/launch/flow.py`, before building `StartSessionRequest`, call `resolve_active_provider()` with the CLI `--provider` flag and `get_selected_provider()` config value. Extract `allowed_providers` from the `NormalizedOrgConfig` team config if available. Pass the resolved `provider_id` to `prepare_live_start_plan()`.

4. Write `tests/test_provider_dispatch.py` covering:
   - Default dispatch (no provider_id) → uses Claude provider and safety adapter
   - Explicit 'claude' → same result
   - Explicit 'codex' → uses codex_agent_provider and codex_safety_adapter
   - Policy violation in flow (mocked org config with restricted allowed_providers) → ProviderNotAllowedError

5. Run the full test suite to verify zero regressions.

Constraints:
- Do NOT modify `get_default_adapters()` or the lru_cache. Provider dispatch is per-invocation in `build_start_session_dependencies()`, not at bootstrap time (D028).
- `StartSessionDependencies.agent_provider` must carry the provider-dispatched value, not always Claude.
- The `allowed_providers` field must be read from the team-level config in NormalizedOrgConfig, falling back to empty (all allowed) if no team config.
- Keep `safety_adapter` dispatch in `dependencies.py` — thread it into `StartSessionDependencies` if needed, or track it alongside for S04.

## Inputs

- ``src/scc_cli/core/provider_resolution.py` — resolve_active_provider() from T01`
- ``src/scc_cli/config.py` — get_selected_provider() from T01`
- ``src/scc_cli/commands/launch/dependencies.py` — build_start_session_dependencies to modify`
- ``src/scc_cli/commands/launch/flow.py` — start() with --provider flag from T02`
- ``src/scc_cli/application/start_session.py` — StartSessionRequest.provider_id from T02`
- ``src/scc_cli/bootstrap.py` — DefaultAdapters field names for dispatch lookup`

## Expected Output

- ``src/scc_cli/commands/launch/dependencies.py` — provider-aware build_start_session_dependencies`
- ``src/scc_cli/commands/launch/flow.py` — resolve_active_provider() call wired into start()`
- ``tests/test_provider_dispatch.py` — dispatch and policy tests`

## Verification

uv run pytest tests/test_provider_dispatch.py -v && uv run pytest --rootdir "$PWD" -q && uv run mypy src/scc_cli/commands/launch/dependencies.py src/scc_cli/commands/launch/flow.py && uv run ruff check
