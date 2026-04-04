---
estimated_steps: 4
estimated_files: 10
skills_used:
  - karpathy-guidelines
---

# T01: Move Claude settings logic into adapters and preserve the bootstrap boundary

**Slice:** S02 — Claude adapter extraction and cleanup
**Milestone:** M002

## Description

Perform a behavior-preserving extraction of the legacy root module `src/scc_cli/claude_adapter.py` into `src/scc_cli/adapters/claude_settings.py`, then update every caller so Claude-specific settings, auth, and marketplace formatting logic is adapter-owned without violating the `test_only_bootstrap_imports_adapters` architecture rule. Keep the change small and maintainable: no logic redesign, no new provider leakage, and no type regressions in touched source files. Because repo-wide pyright is already red from unrelated baseline issues, this task must keep its touched source files clean under scoped pyright and avoid expanding that debt.

## Negative Tests

- **Malformed inputs**: stale import-path grep must find no remaining `claude_adapter` references after the move.
- **Error paths**: `tests/test_import_boundaries.py` must fail if application or command modules reach into `scc_cli.adapters.*` directly instead of using `bootstrap.py`.
- **Boundary conditions**: `tests/test_no_root_sprawl.py` must pass with `src/scc_cli/claude_adapter.py` removed from both disk and the allowlist.

## Steps

1. Move `src/scc_cli/claude_adapter.py` to `src/scc_cli/adapters/claude_settings.py` without changing runtime behavior, and update the module docstring so the adapter-layer ownership is explicit.
2. Redirect all source and test imports to the new module, but preserve the bootstrap composition rule by re-exporting `merge_mcp_servers` from `src/scc_cli/bootstrap.py` for non-adapter callers.
3. Remove the deleted root module from `tests/test_no_root_sprawl.py` and clear any stale `claude_adapter` references across `src/` and `tests/`.
4. Run the focused architecture checks, scoped pyright on touched source files, and `ruff` so the extraction lands cleanly.

## Must-Haves

- [ ] `src/scc_cli/claude_adapter.py` no longer exists and `src/scc_cli/adapters/claude_settings.py` is the only canonical Claude settings module.
- [ ] `src/scc_cli/application/start_session.py` and `src/scc_cli/commands/launch/sandbox.py` continue to work without importing `scc_cli.adapters.*` directly.
- [ ] The root-sprawl and import-boundary tests still pass after the move.

## Verification

- `! test -f src/scc_cli/claude_adapter.py && test -f src/scc_cli/adapters/claude_settings.py && ! grep -r 'scc_cli\.claude_adapter\|from scc_cli import claude_adapter\|\.claude_adapter' src/ tests/ 2>/dev/null`
- `uv run pytest tests/test_import_boundaries.py tests/test_no_root_sprawl.py tests/test_claude_adapter.py tests/test_config_inheritance.py tests/test_mcp_servers.py -q`
- `uv run pyright src/scc_cli/adapters/claude_settings.py src/scc_cli/bootstrap.py src/scc_cli/application/start_session.py src/scc_cli/commands/launch/sandbox.py`
- `uv run ruff check`

## Observability Impact

- Signals added/changed: import-boundary and root-sprawl failures become the primary diagnostics for adapter leakage in this area.
- How a future agent inspects this: run `uv run pytest tests/test_import_boundaries.py tests/test_no_root_sprawl.py -q` and the scoped `uv run pyright ...` command above.
- Failure state exposed: stale import paths, missing bootstrap re-export, or illegal non-bootstrap adapter imports.

## Inputs

- `src/scc_cli/claude_adapter.py` — legacy Claude settings/auth helper module being extracted.
- `src/scc_cli/bootstrap.py` — composition root that must remain the only adapter re-export surface for higher layers.
- `src/scc_cli/application/start_session.py` — application-layer caller that currently needs `merge_mcp_servers`.
- `src/scc_cli/commands/launch/sandbox.py` — command-layer caller that currently needs `merge_mcp_servers`.
- `tests/test_claude_adapter.py` — adapter behavior regression coverage that must follow the file move.
- `tests/test_mcp_servers.py` — Claude MCP rendering coverage that must follow the file move.
- `tests/test_config_inheritance.py` — effective-config-to-Claude-settings coverage that must follow the file move.
- `tests/test_no_root_sprawl.py` — root allowlist that must shrink when the legacy module is deleted.
- `tests/test_import_boundaries.py` — architecture guard that forbids direct adapter imports outside `bootstrap.py`.

## Expected Output

- `src/scc_cli/adapters/claude_settings.py` — canonical adapter-owned Claude settings module.
- `src/scc_cli/bootstrap.py` — re-export point for `merge_mcp_servers` used outside the adapter layer.
- `src/scc_cli/application/start_session.py` — application caller updated to consume the bootstrap re-export.
- `src/scc_cli/commands/launch/sandbox.py` — command caller updated to consume the bootstrap re-export.
- `tests/test_claude_adapter.py` — import path updated to the adapter module.
- `tests/test_mcp_servers.py` — import path updated to the adapter module.
- `tests/test_config_inheritance.py` — import path updated to the adapter module.
- `tests/test_no_root_sprawl.py` — stale `claude_adapter.py` allowlist entry removed.
