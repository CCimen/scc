---
estimated_steps: 45
estimated_files: 1
skills_used: []
---

# T02: Add tests for provider-parameterized helpers and CLI surfaces

## Description

Write comprehensive tests validating all S02 production code changes: renamed session/audit helpers use registry correctly, WorkContext serializes provider_id with backward compat, session list CLI includes provider column, and sandbox records provider_id='claude'.

## Steps

1. **Create `tests/test_s02_provider_sessions.py`** with the following test classes:

2. **Test renamed session helpers (`TestProviderSessionsDir`):**
   - `test_get_provider_sessions_dir_claude` — verify returns `Path.home() / '.claude'` for provider_id='claude'
   - `test_get_provider_sessions_dir_codex` — verify returns `Path.home() / '.codex'` for provider_id='codex'
   - `test_get_provider_sessions_dir_unknown_raises` — verify raises `InvalidProviderError` for unknown provider
   - `test_get_provider_recent_sessions_empty` — verify returns empty list when sessions.json doesn't exist

3. **Test renamed audit helper (`TestProviderConfigDir`):**
   - `test_get_provider_config_dir_claude` — verify returns `Path.home() / '.claude'`
   - `test_get_provider_config_dir_codex` — verify returns `Path.home() / '.codex'`

4. **Test WorkContext provider_id (`TestWorkContextProviderId`):**
   - `test_work_context_provider_id_roundtrip` — create with provider_id='codex', to_dict, from_dict, verify provider_id preserved
   - `test_work_context_provider_id_default_none` — create without provider_id, verify it's None
   - `test_work_context_from_dict_backward_compat` — from_dict with no provider_id key, verify defaults to None
   - `test_display_label_without_provider` — verify display_label unchanged when provider_id is None
   - `test_display_label_with_claude_provider` — verify display_label unchanged when provider is 'claude' (default, not shown)
   - `test_display_label_with_codex_provider` — verify display_label includes '(codex)' suffix

5. **Test session list provider column (`TestSessionListProvider`):**
   - `test_session_dicts_includes_provider_id` — mock sessions with provider_id, verify session_dicts include the field

6. **Run full verification:**
   - `uv run pytest tests/test_s02_provider_sessions.py -v` — all new tests pass
   - `uv run ruff check tests/test_s02_provider_sessions.py` — clean
   - `uv run pytest -q` — full suite, zero regressions

## Must-Haves

- [ ] Tests for renamed session helpers (claude, codex, unknown provider)
- [ ] Tests for renamed audit helper
- [ ] Tests for WorkContext provider_id round-trip and backward compat
- [ ] Tests for display_label with and without provider
- [ ] Tests for session list provider column
- [ ] All tests pass including full suite regression check

## Verification

- `uv run pytest tests/test_s02_provider_sessions.py -v` — all new tests pass
- `uv run ruff check tests/test_s02_provider_sessions.py` — zero errors
- `uv run pytest -q` — full suite passes, zero regressions vs S01 baseline (4654 passed)

## Inputs

- `src/scc_cli/sessions.py` — T01 output: renamed helpers
- `src/scc_cli/commands/audit.py` — T01 output: renamed get_provider_config_dir
- `src/scc_cli/contexts.py` — T01 output: WorkContext with provider_id
- `src/scc_cli/commands/worktree/session_commands.py` — T01 output: session list with provider column
- `src/scc_cli/core/provider_registry.py` — S01 output: get_runtime_spec()
- `src/scc_cli/core/errors.py` — S01 output: InvalidProviderError

## Expected Output

- `tests/test_s02_provider_sessions.py` — comprehensive test file for all S02 changes

## Inputs

- ``src/scc_cli/sessions.py``
- ``src/scc_cli/commands/audit.py``
- ``src/scc_cli/contexts.py``
- ``src/scc_cli/commands/worktree/session_commands.py``
- ``src/scc_cli/core/provider_registry.py``
- ``src/scc_cli/core/errors.py``

## Expected Output

- ``tests/test_s02_provider_sessions.py``

## Verification

uv run pytest tests/test_s02_provider_sessions.py -v && uv run ruff check tests/test_s02_provider_sessions.py && uv run pytest -q
