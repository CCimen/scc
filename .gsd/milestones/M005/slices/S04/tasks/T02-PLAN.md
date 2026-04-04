---
estimated_steps: 8
estimated_files: 2
skills_used: []
---

# T02: Claude renderer: project ArtifactRenderPlan into Claude-native surfaces

Create src/scc_cli/adapters/claude_renderer.py with a function render_claude_artifacts(plan: ArtifactRenderPlan, workspace: Path) -> RendererResult. This adapter-owned renderer:
1. Consumes an ArtifactRenderPlan produced by the core bundle resolver
2. Renders skills into the Claude skill installation surface
3. Renders MCP server definitions into Claude-native MCP config
4. Renders native_integration bindings into Claude-specific surfaces (marketplace metadata, hook config, plugin directories)
5. Returns a RendererResult with rendered paths, skipped items, and any warnings

The renderer is adapter-owned — it may import from marketplace/ for Claude-specific materialization helpers but the planning input is always an ArtifactRenderPlan.

Add characterization tests that verify the renderer produces expected file structures from known plans.

## Inputs

- `src/scc_cli/core/governed_artifacts.py`
- `src/scc_cli/marketplace/render.py`
- `src/scc_cli/marketplace/materialize.py`
- `specs/06-governed-artifacts.md`

## Expected Output

- `src/scc_cli/adapters/claude_renderer.py`
- `tests/test_claude_renderer.py`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_claude_renderer.py -v && uv run pytest --rootdir "$PWD" -q
