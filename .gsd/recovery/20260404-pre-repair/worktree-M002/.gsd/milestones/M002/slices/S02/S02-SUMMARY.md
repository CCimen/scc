---
id: S02
parent: M002
milestone: M002
provides:
  - Adapter-owned Claude settings rendering and auth-artifact handling with no package-root compatibility shim.
  - A preserved bootstrap composition boundary for non-adapter callers that still need adapter helpers.
  - A reusable four-test characterization pattern for provider adapters that downstream slices can apply to Codex and future validation work.
requires:
  - slice: S01
    provides: The live `AgentProvider` seam and `AgentLaunchSpec` wiring introduced in S01, which this slice used as the stable contract boundary for Claude cleanup.
affects:
  - S04
  - S05
key_files:
  - src/scc_cli/adapters/claude_settings.py
  - src/scc_cli/bootstrap.py
  - src/scc_cli/application/start_session.py
  - src/scc_cli/commands/launch/sandbox.py
  - tests/test_claude_adapter.py
  - tests/test_mcp_servers.py
  - tests/test_config_inheritance.py
  - tests/test_no_root_sprawl.py
  - tests/test_claude_agent_provider.py
key_decisions:
  - Claude settings logic now lives only in `src/scc_cli/adapters/claude_settings.py`; the deleted package-root shim is not retained as a compatibility alias.
  - `bootstrap.py` is the only non-adapter import surface for adapter helpers needed by application and command layers, including the `merge_mcp_servers` re-export.
  - Claude provider behavior is now pinned by the canonical four-test `AgentProvider` characterization shape, including the env str-to-str guard from D003.
patterns_established:
  - Keep provider-specific settings/auth/marketplace translation inside `src/scc_cli/adapters/*_settings.py`; higher layers consume only provider-neutral contracts or bootstrap re-exports.
  - When a higher layer needs an adapter helper, re-export it from `bootstrap.py` with `# noqa: F401` rather than importing from `scc_cli.adapters.*` directly.
  - Every `AgentProvider` adapter should be pinned by the canonical four-test characterization suite: metadata, clean spec, settings artifact, and env-is-clean.
observability_surfaces:
  - `tests/test_import_boundaries.py` enforces that only `bootstrap.py` may bridge higher layers to the adapter package.
  - `tests/test_no_root_sprawl.py` detects accidental reintroduction of top-level adapter shims such as `claude_adapter.py`.
  - `tests/test_claude_agent_provider.py` is the authoritative provider-contract diagnostic for Claude launch spec shape.
  - `uv run pyright ...` and `uv run mypy src/scc_cli` provide typed-boundary verification for the moved adapter and its callers.
drill_down_paths:
  - .gsd/milestones/M002/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M002/slices/S02/tasks/T02-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-03T19:18:44.016Z
blocker_discovered: false
---

# S02: Claude adapter extraction and cleanup

**Claude-specific settings and launch-shape behavior now live behind adapter-owned modules and bootstrap re-exports, with characterization tests locking the provider contract in place.**

## What Happened

S02 finished the Claude-side cleanup that S01 made possible. The legacy package-root module `src/scc_cli/claude_adapter.py` was removed and its behavior was preserved in the canonical adapter module `src/scc_cli/adapters/claude_settings.py`, making Claude settings rendering, auth artifact handling, marketplace translation, and MCP merge helpers explicitly adapter-owned. During the move, the existing architecture check `test_only_bootstrap_imports_adapters` surfaced the real boundary rule: application and command layers may not import `scc_cli.adapters.*` directly. The fix was to keep `bootstrap.py` as the composition root and re-export `merge_mcp_servers` there so `application/start_session.py` and `commands/launch/sandbox.py` could keep working without leaking adapter imports into higher layers. The slice then added `tests/test_claude_agent_provider.py` in the canonical four-test shape, pinning Claude capability metadata, clean launch-spec behavior when no settings file exists, artifact-path handling when settings are present, and the D003 env str-to-str contract. Net effect: Claude is now the first fully cleaned-up provider on the seam, bootstrap remains the only allowed adapter boundary for higher layers, and future provider work has an explicit characterization template to copy instead of relying on implicit behavior.

## Verification

Verified the full slice contract at the planned slice level. The architectural check `! test -f src/scc_cli/claude_adapter.py && test -f src/scc_cli/adapters/claude_settings.py` passed, proving the legacy root module is gone and the adapter-owned module exists. The focused regression suite `uv run pytest tests/test_import_boundaries.py tests/test_no_root_sprawl.py tests/test_claude_adapter.py tests/test_config_inheritance.py tests/test_mcp_servers.py tests/test_claude_agent_provider.py -q` passed (182 tests), confirming the bootstrap import boundary, root-sprawl rule, Claude settings behavior, MCP merge path, and new provider characterization suite. Scoped type verification `uv run pyright src/scc_cli/adapters/claude_settings.py src/scc_cli/adapters/claude_agent_provider.py src/scc_cli/bootstrap.py src/scc_cli/application/start_session.py src/scc_cli/commands/launch/sandbox.py tests/test_claude_agent_provider.py` passed with 0 errors. The full gate `uv run ruff check && uv run mypy src/scc_cli && uv run pytest --tb=short -q` also passed, yielding 3249 passed, 23 skipped, 3 xfailed, and 1 xpassed.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

T01 revealed that the initial move plan could not leave `application/start_session.py` and `commands/launch/sandbox.py` importing from `scc_cli.adapters.*` directly. To preserve the existing `test_only_bootstrap_imports_adapters` invariant, `merge_mcp_servers` was re-exported from `bootstrap.py` with `# noqa: F401`, and the non-adapter callers were routed through the composition root instead of importing the adapter module directly.

## Known Limitations

This slice intentionally does not add pre-launch provider destination validation, durable launch audit persistence, or new runtime diagnostics. Claude is now adapter-owned on the seam, but S04 still needs to prove provider requirements before launch and S05 still needs broader hardening/observability follow-through.

## Follow-ups

Use the same adapter-owned settings + canonical four-test pattern when expanding or tightening provider seams in S04/S05 so new validation and audit work does not reintroduce provider-specific logic into core/application layers.

## Files Created/Modified

- `src/scc_cli/adapters/claude_settings.py` — New canonical Claude settings adapter module; owns Claude settings rendering, marketplace/auth translation, and MCP merge helpers after the root-module removal.
- `src/scc_cli/bootstrap.py` — Re-exported `merge_mcp_servers` from the composition root and preserved adapter wiring without letting higher layers import adapters directly.
- `src/scc_cli/application/start_session.py` — Continues to prepare start-session plans without direct adapter imports, preserving the bootstrap boundary introduced in S01.
- `src/scc_cli/commands/launch/sandbox.py` — Launch-path sandbox wiring now consumes Claude MCP merge behavior through `bootstrap.py` rather than directly from the adapter package.
- `tests/test_claude_adapter.py` — Relocation-safe characterization coverage for Claude settings behavior after the module move.
- `tests/test_config_inheritance.py` — Config inheritance regression coverage kept green across the Claude settings relocation.
- `tests/test_mcp_servers.py` — MCP server merge behavior remained covered after the bootstrap re-export change.
- `tests/test_no_root_sprawl.py` — Root-sprawl allowlist continues to enforce removal of the old top-level `claude_adapter.py` module.
- `tests/test_claude_agent_provider.py` — Canonical four-test characterization suite that pins ClaudeAgentProvider metadata, clean launch specs, artifact-path behavior, and the env str-to-str contract.
