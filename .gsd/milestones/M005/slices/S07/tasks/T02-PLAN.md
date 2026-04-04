---
estimated_steps: 5
estimated_files: 2
skills_used: []
---

# T02: Extend Claude renderer to render portable artifacts

1. In render_claude_artifacts(), after the binding loop, iterate plan.portable_artifacts.
2. For SKILL kind: render the same skill metadata as _render_skill_binding but using PortableArtifact fields (name as ref, source metadata in native_config).
3. For MCP_SERVER kind: render an MCP settings fragment entry using artifact source metadata (url, transport from source).
4. Add tests for binding-less skill and MCP rendering.
5. Verify idempotency and existing tests pass.

## Inputs

- `src/scc_cli/adapters/claude_renderer.py`
- `src/scc_cli/core/governed_artifacts.py`

## Expected Output

- `src/scc_cli/adapters/claude_renderer.py rendering portable artifacts`

## Verification

uv run pytest tests/test_claude_renderer.py -v && uv run mypy src/scc_cli/adapters/claude_renderer.py
