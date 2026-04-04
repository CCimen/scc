---
estimated_steps: 5
estimated_files: 2
skills_used: []
---

# T03: Extend Codex renderer to render portable artifacts

1. In render_codex_artifacts(), after the binding loop, iterate plan.portable_artifacts.
2. For SKILL kind: render skill metadata under .agents/skills/ using PortableArtifact fields.
3. For MCP_SERVER kind: render an .mcp.json fragment entry using artifact source metadata.
4. Add tests for binding-less skill and MCP rendering.
5. Verify idempotency and existing tests pass.

## Inputs

- `src/scc_cli/adapters/codex_renderer.py`
- `src/scc_cli/core/governed_artifacts.py`

## Expected Output

- `src/scc_cli/adapters/codex_renderer.py rendering portable artifacts`

## Verification

uv run pytest tests/test_codex_renderer.py -v && uv run mypy src/scc_cli/adapters/codex_renderer.py
