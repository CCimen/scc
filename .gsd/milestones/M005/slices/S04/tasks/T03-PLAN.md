---
estimated_steps: 15
estimated_files: 2
skills_used: []
---

# T03: Codex renderer: project ArtifactRenderPlan into Codex-native surfaces

Create src/scc_cli/adapters/codex_renderer.py with a function render_codex_artifacts(plan: ArtifactRenderPlan, workspace: Path) -> RendererResult. This adapter-owned renderer:
1. Consumes an ArtifactRenderPlan produced by the core bundle resolver
2. Renders skills into Codex skill installation surface (.agents/skills/)
3. Renders MCP server definitions into .codex/config.toml or .mcp.json
4. Renders native_integration bindings into Codex-specific surfaces:
   - .codex-plugin/plugin.json for plugin bundles
   - .codex/rules/*.rules for rule files
   - .codex/hooks.json for hook definitions
   - AGENTS.md content for instruction layers
5. Does NOT try to force Codex surfaces into Claude plugin shapes or vice versa
6. Returns RendererResult with rendered paths, skipped items, and warnings

Codex surfaces are intentionally asymmetric from Claude (D019). The renderer handles:
- Plugin bundle != all Codex artifacts (rules, hooks, config.toml, AGENTS.md are separate)
- Merge strategy for single-file surfaces (hooks.json, config.toml)
- SCC-managed section marking in shared files

## Inputs

- `src/scc_cli/core/governed_artifacts.py`
- `src/scc_cli/adapters/codex_agent_provider.py`
- `specs/06-governed-artifacts.md`
- `specs/03-provider-boundary.md`

## Expected Output

- `src/scc_cli/adapters/codex_renderer.py`
- `tests/test_codex_renderer.py`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_codex_renderer.py -v && uv run pytest --rootdir "$PWD" -q
