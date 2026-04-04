---
id: T04
parent: S04
milestone: M005
key_files:
  - src/scc_cli/core/errors.py
  - src/scc_cli/core/bundle_resolver.py
  - src/scc_cli/adapters/claude_renderer.py
  - src/scc_cli/adapters/codex_renderer.py
  - tests/test_bundle_resolver.py
  - tests/test_claude_renderer.py
  - tests/test_codex_renderer.py
key_decisions:
  - RendererError hierarchy with exit_code=4 for external-surface materialization
  - fail_closed opt-in (default False) for backward compatibility
  - Disabled bundles skip with audit diagnostic even in fail_closed mode
  - Hooks merge wraps entire read-check-write cycle for macOS permission handling
  - D023: Shared artifacts must be renderable without provider bindings (user)
  - D024: Codex renderer must produce real native surfaces (user)
  - D025: T05 wires bundle pipeline through AgentProvider (user)
duration: 
verification_result: passed
completed_at: 2026-04-04T19:26:53.137Z
blocker_discovered: false
---

# T04: Add RendererError exception hierarchy and fail-closed error handling to bundle resolver and both provider renderers, with 27 negative tests

**Add RendererError exception hierarchy and fail-closed error handling to bundle resolver and both provider renderers, with 27 negative tests**

## What Happened

Created RendererError exception hierarchy (RendererError → BundleResolutionError, InvalidArtifactReferenceError, MaterializationError, MergeConflictError) in core/errors.py. Added fail_closed mode to resolve_render_plan() that raises typed exceptions for missing bundles and invalid artifact references. Wrapped every file-write path in both Claude and Codex renderers with MaterializationError fail-closed semantics. Added 27 negative tests covering every failure path. Discovered and handled macOS edge case where hooks_path.exists() raises PermissionError on locked directories. Recorded decisions D023–D025 from user direction on shared artifact rendering, Codex native surfaces, and T05 wiring scope.

## Verification

All verification commands pass: ruff check (0 errors), mypy (0 issues in 288 files), pytest targeted (105 passed), pytest full suite (4222 passed, 23 skipped, 3 xfailed, 1 xpassed).

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 2000ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4000ms |
| 3 | `uv run pytest tests/test_bundle_resolver.py tests/test_claude_renderer.py tests/test_codex_renderer.py -v` | 0 | ✅ pass (105 tests) | 2000ms |
| 4 | `uv run pytest -q -x` | 0 | ✅ pass (4222 tests) | 76000ms |

## Deviations

Codex hooks section required wrapping entire read-stat-write cycle in single OSError handler because hooks_path.exists() raises PermissionError on macOS when parent is read-only. MergeConflictError defined but not yet raised by renderers — available for T05 merge layer.

## Known Issues

D023: Shared/portable artifacts in effective_artifacts without bindings not yet rendered. D024: Codex renderer produces metadata placeholders, not real native surfaces yet. D025: Bundle pipeline not yet wired through AgentProvider/start_session.

## Files Created/Modified

- `src/scc_cli/core/errors.py`
- `src/scc_cli/core/bundle_resolver.py`
- `src/scc_cli/adapters/claude_renderer.py`
- `src/scc_cli/adapters/codex_renderer.py`
- `tests/test_bundle_resolver.py`
- `tests/test_claude_renderer.py`
- `tests/test_codex_renderer.py`
