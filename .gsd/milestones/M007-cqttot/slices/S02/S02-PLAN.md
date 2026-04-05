# S02: Session, resume, and machine-readable output provider hardening

**Goal:** Session, resume, and machine-readable output surfaces are provider-parameterized. No Claude-specific function names remain in session/audit/sandbox helpers. Session list CLI shows provider column. Quick Resume surfaces provider_id. Legacy sandbox path records provider_id='claude' explicitly.
**Demo:** After this: sessions.get_claude_sessions_dir renamed to provider-parameterized helper. audit.py derives path from provider. sandbox.py records provider_id='claude'. Quick Resume shows provider_id. Session list CLI displays provider column.

## Tasks
- [x] **T01: Renamed three Claude-hardcoded helpers to provider-parameterized versions using registry, fixed sandbox provider_id, added provider_id to WorkContext, and surfaced provider in session list CLI and Quick Resume display** — ## Description

All production code changes for S02. Rename three Claude-named helper functions to provider-parameterized versions using the ProviderRuntimeSpec registry from S01. Fix sandbox.py provider_id recording. Add provider_id to WorkContext. Surface provider in session list CLI and Quick Resume display_label.

## Steps

1. **Rename helpers in `sessions.py`:**
   - Rename `get_claude_sessions_dir()` → `get_provider_sessions_dir(provider_id: str = 'claude')` 
   - Replace `Path.home() / AGENT_CONFIG_DIR` with `Path.home() / get_runtime_spec(provider_id).config_dir`
   - Import `get_runtime_spec` from `scc_cli.core.provider_registry`
   - Rename `get_claude_recent_sessions()` → `get_provider_recent_sessions(provider_id: str = 'claude')`
   - Update internal call from `get_claude_sessions_dir()` to `get_provider_sessions_dir(provider_id)`
   - Keep default parameter `'claude'` for backward compatibility

2. **Rename helper in `commands/audit.py`:**
   - Rename `get_claude_dir()` → `get_provider_config_dir(provider_id: str = 'claude')`
   - Replace `Path.home() / AGENT_CONFIG_DIR` with `Path.home() / get_runtime_spec(provider_id).config_dir`
   - Import `get_runtime_spec` from `scc_cli.core.provider_registry`
   - Update the caller in `audit_plugins_cmd` to call `get_provider_config_dir()` (no arg needed — defaults to claude, plugin audit is Claude-specific)

3. **Fix sandbox.py provider_id:**
   - In `commands/launch/sandbox.py` line ~103, change `provider_id=None` to `provider_id='claude'`
   - The legacy sandbox path is always Claude — make this explicit per D032

4. **Add provider_id to WorkContext in `contexts.py`:**
   - Add field `provider_id: str | None = None` to the WorkContext dataclass (after `pinned`)
   - Add `"provider_id": self.provider_id` to `to_dict()`
   - Add `provider_id=data.get("provider_id")` to `from_dict()` for backward compat
   - Update `display_label` property: if `self.provider_id` is not None and not `'claude'`, append provider info. Format: `"{self.team_label} · {self.repo_name} · {name} ({self.provider_id})"` when provider is non-default

5. **Add provider column to session list CLI in `session_commands.py`:**
   - In the `session_dicts` list comprehension (~line 87), add `"provider_id": session.provider_id or "claude"` 
   - In the `rows` construction (~line 137), add `session.provider_id or "claude"` as fifth element
   - In `render_responsive_table` call (~line 155), add `("Provider", "magenta")` to `wide_columns` list

6. **Run lint and type checks:**
   - `uv run ruff check` on all 6 touched files
   - `uv run mypy` on all 6 touched files
   - `uv run pytest -q` full suite to verify zero regressions

## Must-Haves

- [ ] `get_claude_sessions_dir` renamed to `get_provider_sessions_dir(provider_id)` using registry
- [ ] `get_claude_recent_sessions` renamed to `get_provider_recent_sessions(provider_id)` using registry  
- [ ] `get_claude_dir` renamed to `get_provider_config_dir(provider_id)` using registry
- [ ] `sandbox.py` records `provider_id='claude'` not `None`
- [ ] `WorkContext` has `provider_id` field with backward-compat serialization
- [ ] `display_label` surfaces non-default provider
- [ ] Session list CLI includes provider_id in data and table columns
- [ ] All existing tests pass

## Verification

- `uv run ruff check src/scc_cli/sessions.py src/scc_cli/commands/audit.py src/scc_cli/commands/launch/sandbox.py src/scc_cli/commands/worktree/session_commands.py src/scc_cli/contexts.py src/scc_cli/application/launch/start_wizard.py` — zero errors
- `uv run mypy src/scc_cli/sessions.py src/scc_cli/commands/audit.py src/scc_cli/commands/launch/sandbox.py src/scc_cli/commands/worktree/session_commands.py src/scc_cli/contexts.py src/scc_cli/application/launch/start_wizard.py` — zero errors
- `uv run pytest -q` — full suite passes with zero regressions

## Inputs

- `src/scc_cli/sessions.py` — contains get_claude_sessions_dir and get_claude_recent_sessions to rename
- `src/scc_cli/commands/audit.py` — contains get_claude_dir to rename
- `src/scc_cli/commands/launch/sandbox.py` — contains provider_id=None to fix
- `src/scc_cli/commands/worktree/session_commands.py` — session list CLI to add provider column
- `src/scc_cli/contexts.py` — WorkContext to add provider_id field
- `src/scc_cli/application/launch/start_wizard.py` — Quick Resume display to surface provider
- `src/scc_cli/core/provider_registry.py` — S01 output: get_runtime_spec() and PROVIDER_REGISTRY

## Expected Output

- `src/scc_cli/sessions.py` — renamed helpers using registry
- `src/scc_cli/commands/audit.py` — renamed get_claude_dir to get_provider_config_dir
- `src/scc_cli/commands/launch/sandbox.py` — provider_id='claude' recorded
- `src/scc_cli/commands/worktree/session_commands.py` — provider column in session list
- `src/scc_cli/contexts.py` — WorkContext with provider_id field and updated display_label
- `src/scc_cli/application/launch/start_wizard.py` — no functional change needed if display_label change in contexts.py covers Quick Resume
  - Estimate: 45m
  - Files: src/scc_cli/sessions.py, src/scc_cli/commands/audit.py, src/scc_cli/commands/launch/sandbox.py, src/scc_cli/commands/worktree/session_commands.py, src/scc_cli/contexts.py, src/scc_cli/application/launch/start_wizard.py
  - Verify: uv run ruff check src/scc_cli/sessions.py src/scc_cli/commands/audit.py src/scc_cli/commands/launch/sandbox.py src/scc_cli/commands/worktree/session_commands.py src/scc_cli/contexts.py src/scc_cli/application/launch/start_wizard.py && uv run mypy src/scc_cli/sessions.py src/scc_cli/commands/audit.py src/scc_cli/commands/launch/sandbox.py src/scc_cli/commands/worktree/session_commands.py src/scc_cli/contexts.py src/scc_cli/application/launch/start_wizard.py && uv run pytest -q
- [x] **T02: Added 21 tests covering provider-parameterized session, audit, context, and CLI surfaces** — ## Description

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
  - Estimate: 30m
  - Files: tests/test_s02_provider_sessions.py
  - Verify: uv run pytest tests/test_s02_provider_sessions.py -v && uv run ruff check tests/test_s02_provider_sessions.py && uv run pytest -q
