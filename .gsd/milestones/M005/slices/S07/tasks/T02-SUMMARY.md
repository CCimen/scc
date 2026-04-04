---
id: T02
parent: S07
milestone: M005
key_files:
  - src/scc_cli/adapters/claude_renderer.py
  - tests/test_claude_renderer.py
key_decisions:
  - Portable skills use artifact.name as filesystem ref (sanitized)
  - Portable MCP servers default to SSE transport from source_url
  - Portable marker (portable: true) distinguishes from binding-rendered artifacts
duration: 
verification_result: passed
completed_at: 2026-04-04T21:30:04.037Z
blocker_discovered: false
---

# T02: Extended Claude renderer to render portable skills and MCP servers from artifact metadata

**Extended Claude renderer to render portable skills and MCP servers from artifact metadata**

## What Happened

Added _render_portable_skill() and _render_portable_mcp() to claude_renderer.py. _render_portable_skill writes skill.json metadata under .claude/.scc-managed/skills/ using artifact source fields, marked portable: true. _render_portable_mcp produces a settings_fragment mcpServers entry with SSE transport from source_url. Integrated both into render_claude_artifacts() after the binding loop, iterating plan.portable_artifacts. Added 9 tests across 3 test classes: TestPortableSkillRendering (4 tests), TestPortableMcpRendering (3 tests), TestPortableMixedWithBindings (2 tests). All 83 Claude renderer tests pass.

## Verification

uv run pytest tests/test_claude_renderer.py -v → 83 passed; uv run mypy src/scc_cli/adapters/claude_renderer.py → Success

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest tests/test_claude_renderer.py -q` | 0 | ✅ pass | 1710ms |
| 2 | `uv run mypy src/scc_cli/adapters/claude_renderer.py` | 0 | ✅ pass | 3000ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/adapters/claude_renderer.py`
- `tests/test_claude_renderer.py`
