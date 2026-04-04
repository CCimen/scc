# S03: Codex adapter as a first-class provider on the same seam

**Goal:** Implement `CodexAgentProvider` — a second conformant `AgentProvider` implementation — and wire it into `DefaultAdapters` alongside the existing Claude adapter, proving the seam is genuinely provider-neutral.
**Demo:** After this: TBD

## Tasks
- [x] **T01: Add CodexAgentProvider adapter and 4 characterization tests pinning its AgentLaunchSpec and ProviderCapabilityProfile** — Create the Codex adapter mirroring ClaudeAgentProvider's shape, and add 4 characterization tests that pin the exact AgentLaunchSpec and ProviderCapabilityProfile it produces. No existing files are modified in this task — pure additions only.

Steps:
1. Create `src/scc_cli/adapters/codex_agent_provider.py`. The class `CodexAgentProvider` must:
   - Implement `capability_profile()` returning `ProviderCapabilityProfile(provider_id='codex', display_name='Codex', required_destination_set='openai-core', supports_resume=False, supports_skills=False, supports_native_integrations=False)`
   - Implement `prepare_launch(*, config, workspace, settings_path=None)` returning `AgentLaunchSpec(provider_id='codex', argv=('codex',), env={}, workdir=workspace, artifact_paths=(settings_path,) if settings_path else (), required_destination_sets=('openai-core',))`
   - Use `from __future__ import annotations` and typed parameters matching the `AgentProvider` protocol exactly
2. Create `tests/test_codex_agent_provider.py` with 4 tests mirroring `tests/test_claude_agent_provider.py`:
   - `test_capability_profile_returns_codex_metadata`: asserts provider_id=='codex', display_name=='Codex', required_destination_set=='openai-core', supports_resume is False
   - `test_prepare_launch_without_settings_produces_clean_spec`: asserts provider_id, argv==('codex',), env=={}, artifact_paths==(), required_destination_sets==('openai-core',), workdir==tmp_path
   - `test_prepare_launch_with_settings_includes_artifact_path`: asserts settings path is in artifact_paths, env is still empty
   - `test_prepare_launch_env_is_clean_str_to_str`: asserts all env keys and values are str (D003 contract guard)
3. Run `uv run ruff check` and fix any issues before committing
  - Estimate: 30m
  - Files: src/scc_cli/adapters/codex_agent_provider.py, tests/test_codex_agent_provider.py
  - Verify: uv run pytest tests/test_codex_agent_provider.py -q && uv run ruff check && uv run mypy src/scc_cli
- [x] **T02: All 4 DefaultAdapters construction sites confirmed wired with CodexAgentProvider; full suite (3255 tests) passes green** — Add `codex_agent_provider` to `DefaultAdapters` and update all 4 known construction sites. This proves the seam accepts two providers simultaneously without breaking any existing callers.

Steps:
1. In `src/scc_cli/bootstrap.py`:
   - Add `from scc_cli.adapters.codex_agent_provider import CodexAgentProvider` import
   - Add `codex_agent_provider: AgentProvider | None = None` field to `DefaultAdapters` dataclass (use a None default so any construction site we miss compiles safely per KNOWLEDGE.md)
   - In `get_default_adapters()`, add `codex_agent_provider=CodexAgentProvider()` to the `DefaultAdapters(...)` call
2. In `tests/fakes/__init__.py`:
   - Add `codex_agent_provider=FakeAgentProvider()` to `build_fake_adapters()` call
3. In `tests/test_cli.py`:
   - Find the inline `DefaultAdapters(...)` construction and add `codex_agent_provider=FakeAgentProvider()` (import `FakeAgentProvider` if not already present)
4. In `tests/test_integration.py`:
   - Find the inline `DefaultAdapters(...)` construction and add `codex_agent_provider=FakeAgentProvider()` (import `FakeAgentProvider` if not already present)
5. Run `uv run pytest --tb=short -q` — the full suite must be green. If new ruff/mypy errors appear, fix before finalizing.

Constraints:
- Do NOT remove the existing `agent_provider` field — it stays pointing to `ClaudeAgentProvider()`. The `codex_agent_provider` field is additive.
- The import boundary invariant (`test_only_bootstrap_imports_adapters`) requires that only `bootstrap.py` imports from `scc_cli.adapters.*`. `CodexAgentProvider` is imported in `bootstrap.py` — this is correct.
- If `uv run pytest tests/test_import_boundaries.py` fails, check that no application or command layer imports `codex_agent_provider` directly.
  - Estimate: 30m
  - Files: src/scc_cli/bootstrap.py, tests/fakes/__init__.py, tests/test_cli.py, tests/test_integration.py
  - Verify: uv run pytest --tb=short -q && uv run ruff check && uv run mypy src/scc_cli
