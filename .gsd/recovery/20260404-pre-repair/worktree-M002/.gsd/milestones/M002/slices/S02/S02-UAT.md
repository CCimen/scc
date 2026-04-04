# S02: Claude adapter extraction and cleanup — UAT

**Milestone:** M002
**Written:** 2026-04-03T19:18:44.016Z

# S02: Claude adapter extraction and cleanup — UAT

**Milestone:** M002
**Written:** 2026-04-03

## UAT Type

- UAT mode: artifact-driven
- Why this mode is sufficient: This slice is an internal architectural extraction with no new interactive runtime surface. The claim is proven by repository state, import-boundary checks, typed verification, and provider characterization tests.

## Preconditions

- Run from the synced repo worktree for M002.
- Project dependencies are installed via `uv`.
- No local edits are hiding or reintroducing `src/scc_cli/claude_adapter.py`.

## Smoke Test

Run:

```bash
! test -f src/scc_cli/claude_adapter.py && test -f src/scc_cli/adapters/claude_settings.py
```

Expected result: the legacy root module is absent and the adapter-owned Claude settings module exists.

## Test Cases

### 1. Bootstrap remains the only adapter bridge for higher layers

1. Run:
   ```bash
   uv run pytest tests/test_import_boundaries.py tests/test_no_root_sprawl.py -q
   ```
2. Confirm the suite passes.
3. **Expected:** import-boundary enforcement proves application/command layers are not importing `scc_cli.adapters.*` directly, and root-sprawl enforcement proves `src/scc_cli/claude_adapter.py` was not left behind or reintroduced.

### 2. Claude settings behavior still works after relocation

1. Run:
   ```bash
   uv run pytest tests/test_claude_adapter.py tests/test_config_inheritance.py tests/test_mcp_servers.py -q
   ```
2. Confirm all tests pass.
3. **Expected:** Claude settings rendering, config inheritance, marketplace/auth path handling, and MCP server merge behavior still behave exactly as before the module move.

### 3. ClaudeAgentProvider contract is explicitly pinned

1. Run:
   ```bash
   uv run pytest tests/test_claude_agent_provider.py -q
   ```
2. Inspect the four passing tests.
3. **Expected:** the provider reports stable Claude metadata, produces a clean `AgentLaunchSpec` without settings, includes the settings artifact path when present, and never emits non-string env values.

### 4. Typed and repo-wide regression gate stays green

1. Run:
   ```bash
   uv run pyright src/scc_cli/adapters/claude_settings.py src/scc_cli/adapters/claude_agent_provider.py src/scc_cli/bootstrap.py src/scc_cli/application/start_session.py src/scc_cli/commands/launch/sandbox.py tests/test_claude_agent_provider.py
   ```
2. Run:
   ```bash
   uv run ruff check && uv run mypy src/scc_cli && uv run pytest --tb=short -q
   ```
3. **Expected:** no type regressions, no lint regressions, and the full repository gate remains green after the Claude extraction.

## Edge Cases

### Settings file absent

1. Run the provider characterization suite from Test Case 3.
2. Confirm `test_prepare_launch_without_settings_produces_clean_spec` passes.
3. **Expected:** `artifact_paths` is empty and `env` remains `{}` when no Claude settings file is supplied.

### Settings file present

1. Run the provider characterization suite from Test Case 3.
2. Confirm `test_prepare_launch_with_settings_includes_artifact_path` passes.
3. **Expected:** the generated settings path is surfaced through `artifact_paths`, not serialized into env vars.

## Failure Signals

- `src/scc_cli/claude_adapter.py` exists again.
- `tests/test_import_boundaries.py` fails because a higher layer imported `scc_cli.adapters.*` directly.
- `tests/test_no_root_sprawl.py` fails because a new top-level shim leaked back into `src/scc_cli/`.
- `tests/test_claude_agent_provider.py` fails because provider metadata, argv, artifact paths, or env cleanliness changed unexpectedly.
- `pyright`, `mypy`, or the full pytest gate fail after the extraction.

## Not Proven By This UAT

- This UAT does not prove live provider-core destination validation; that is planned for S04.
- This UAT does not prove durable runtime audit persistence or broader launch diagnostics hardening; those remain for later slices.

## Notes for Tester

- Treat `bootstrap.py` as the authoritative composition root for any adapter helper needed above the adapter layer.
- If a future refactor needs a Claude helper outside `scc_cli.adapters`, re-export it from `bootstrap.py` rather than restoring a root-level module or importing the adapter package directly.
