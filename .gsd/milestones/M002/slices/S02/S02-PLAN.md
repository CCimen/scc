# S02: Claude adapter extraction and cleanup

**Goal:** Make Claude the first fully migrated provider on the new seam and remove residual Claude-shaped assumptions from core by extracting `claude_adapter.py` into `adapters/claude_settings.py` and updating all import sites to point at the adapter layer.
**Demo:** After this: TBD

## Tasks
- [x] **T01: Moved claude_adapter.py to adapters/claude_settings.py, redirected all 7 import sites, and re-exported merge_mcp_servers via bootstrap.py to satisfy the import-boundary invariant** — Move the top-level legacy module `src/scc_cli/claude_adapter.py` into the adapters layer as `src/scc_cli/adapters/claude_settings.py`. Update every import site — source files, test files, and the root-sprawl allowlist — so no reference to `scc_cli.claude_adapter` remains. This is a pure copy+delete+import-update with zero logic changes.

Steps:
1. Copy `src/scc_cli/claude_adapter.py` verbatim to `src/scc_cli/adapters/claude_settings.py`. Update the module docstring to reflect the new canonical location.
2. In the new file, update the internal import of `scc_cli.profiles` → keep as-is (cross-adapter imports of stable legacy modules are acceptable while `profiles.py` is still legacy). Same for `scc_cli.auth` imports.
3. Delete `src/scc_cli/claude_adapter.py`.
4. Update import sites in source files:
   - `src/scc_cli/application/start_session.py`: `from scc_cli.claude_adapter import merge_mcp_servers` → `from scc_cli.adapters.claude_settings import merge_mcp_servers`
   - `src/scc_cli/commands/launch/sandbox.py`: `from ...claude_adapter import merge_mcp_servers` → `from scc_cli.adapters.claude_settings import merge_mcp_servers`
5. Update import sites in test files:
   - `tests/test_claude_adapter.py`: `from scc_cli import claude_adapter` → `from scc_cli.adapters import claude_settings as claude_adapter`; `from scc_cli.claude_adapter import AuthResult` → `from scc_cli.adapters.claude_settings import AuthResult`. This preserves all test assertions unchanged.
   - `tests/test_mcp_servers.py`: all `from scc_cli import claude_adapter` → `from scc_cli.adapters import claude_settings as claude_adapter`.
   - `tests/test_config_inheritance.py`: `from scc_cli.claude_adapter import build_settings_from_effective_config` → `from scc_cli.adapters.claude_settings import build_settings_from_effective_config`.
6. Remove `"claude_adapter.py"` from `ALLOWED_LEGACY` in `tests/test_no_root_sprawl.py`. The `test_allowed_items_still_exist` test would fail if the entry is left in after the file is deleted.
7. Run `uv run ruff check --fix` to catch any import sort regressions, then `uv run mypy src/scc_cli`, then `uv run pytest --tb=short -q`.
  - Estimate: 45m
  - Files: src/scc_cli/claude_adapter.py, src/scc_cli/adapters/claude_settings.py, src/scc_cli/application/start_session.py, src/scc_cli/commands/launch/sandbox.py, tests/test_claude_adapter.py, tests/test_mcp_servers.py, tests/test_config_inheritance.py, tests/test_no_root_sprawl.py
  - Verify: cd /Users/ccimen/dev/sccorj/scc-sync-1.7.3/.gsd/worktrees/M002 && ! test -f src/scc_cli/claude_adapter.py && test -f src/scc_cli/adapters/claude_settings.py && ! grep -r 'scc_cli.claude_adapter\|from scc_cli import claude_adapter\|\.claude_adapter' src/ tests/ 2>/dev/null && uv run ruff check && uv run mypy src/scc_cli && uv run pytest --tb=short -q 2>&1 | tail -3
- [x] **T02: Added 4 ClaudeAgentProvider characterization tests pinning the full AgentLaunchSpec shape, bringing claude_agent_provider.py to 100% coverage and the suite to 3251 passing tests** — After T01, `ClaudeAgentProvider` lives at `src/scc_cli/adapters/claude_agent_provider.py` and `claude_settings` at `src/scc_cli/adapters/claude_settings.py`. Write a dedicated characterization test module for `ClaudeAgentProvider` that proves the adapter round-trips correctly through the provider seam — verifying `prepare_launch` builds the expected `AgentLaunchSpec` shape (correct `argv`, empty `env`, settings in `artifact_paths`, correct `required_destination_sets`). Also add a test that confirms `capability_profile()` returns the expected provider metadata. This closes the 18% coverage gap on `claude_agent_provider.py` identified in the S01 summary.

Steps:
1. Create `tests/test_claude_agent_provider.py`. Import `ClaudeAgentProvider` from `scc_cli.adapters.claude_agent_provider`.
2. Write `test_capability_profile_returns_claude_metadata` — checks `provider_id == 'claude'`, `display_name == 'Claude Code'`, `required_destination_set == 'anthropic-core'`, `supports_resume is True`.
3. Write `test_prepare_launch_without_settings_produces_clean_spec(tmp_path)` — calls `provider.prepare_launch(config={}, workspace=tmp_path, settings_path=None)` and asserts `spec.provider_id == 'claude'`, `spec.argv == ('claude', '--dangerously-skip-permissions')`, `spec.env == {}`, `spec.artifact_paths == ()`, `spec.required_destination_sets == ('anthropic-core',)`, `spec.workdir == tmp_path`.
4. Write `test_prepare_launch_with_settings_includes_artifact_path(tmp_path)` — creates a fake settings path and asserts it appears in `spec.artifact_paths`; env remains `{}`.
5. Write `test_prepare_launch_env_is_clean_str_to_str(tmp_path)` — asserts all env values are `str`, not nested dicts (aligns with D003/KNOWLEDGE.md contract).
6. Run `uv run ruff check --fix && uv run mypy src/scc_cli && uv run pytest --tb=short -q` — suite must pass with ≥3247 + 4 new tests (≥3251).
  - Estimate: 30m
  - Files: tests/test_claude_agent_provider.py, src/scc_cli/adapters/claude_agent_provider.py
  - Verify: cd /Users/ccimen/dev/sccorj/scc-sync-1.7.3/.gsd/worktrees/M002 && uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_claude_agent_provider.py -v --tb=short && uv run pytest --tb=short -q 2>&1 | tail -3
