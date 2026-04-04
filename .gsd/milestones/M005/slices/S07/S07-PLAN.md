# S07: Render portable artifacts from effective_artifacts without provider bindings (D023)

**Goal:** Implement D023: make portable artifacts (skills and MCP servers) that appear in effective_artifacts but have NO provider-specific bindings renderable by both Claude and Codex renderers. The resolver must carry artifact metadata into the plan so renderers can produce output without requiring a ProviderArtifactBinding.
**Demo:** After this: TBD

## Tasks
- [x] **T01: Added PortableArtifact type and populated portable_artifacts in ArtifactRenderPlan from resolver** — 1. Add a PortableArtifact dataclass (name, kind, source metadata) to governed_artifacts.py.
2. Add portable_artifacts: tuple[PortableArtifact, ...] field to ArtifactRenderPlan.
3. In _resolve_single_bundle, when an artifact has no provider bindings AND is SKILL or MCP_SERVER kind, create a PortableArtifact from the GovernedArtifact and add it to the plan's portable_artifacts.
4. Update existing resolver tests to verify portable_artifacts population.
5. Verify all existing tests still pass.
  - Estimate: 30min
  - Files: src/scc_cli/core/governed_artifacts.py, src/scc_cli/core/bundle_resolver.py, tests/test_bundle_resolver.py, tests/test_bundle_resolver_contracts.py
  - Verify: uv run pytest tests/test_bundle_resolver.py tests/test_bundle_resolver_contracts.py -v && uv run mypy src/scc_cli/core/governed_artifacts.py src/scc_cli/core/bundle_resolver.py
- [x] **T02: Extended Claude renderer to render portable skills and MCP servers from artifact metadata** — 1. In render_claude_artifacts(), after the binding loop, iterate plan.portable_artifacts.
2. For SKILL kind: render the same skill metadata as _render_skill_binding but using PortableArtifact fields (name as ref, source metadata in native_config).
3. For MCP_SERVER kind: render an MCP settings fragment entry using artifact source metadata (url, transport from source).
4. Add tests for binding-less skill and MCP rendering.
5. Verify idempotency and existing tests pass.
  - Estimate: 25min
  - Files: src/scc_cli/adapters/claude_renderer.py, tests/test_claude_renderer.py
  - Verify: uv run pytest tests/test_claude_renderer.py -v && uv run mypy src/scc_cli/adapters/claude_renderer.py
- [x] **T03: Extended Codex renderer to render portable skills and MCP servers from artifact metadata** — 1. In render_codex_artifacts(), after the binding loop, iterate plan.portable_artifacts.
2. For SKILL kind: render skill metadata under .agents/skills/ using PortableArtifact fields.
3. For MCP_SERVER kind: render an .mcp.json fragment entry using artifact source metadata.
4. Add tests for binding-less skill and MCP rendering.
5. Verify idempotency and existing tests pass.
  - Estimate: 25min
  - Files: src/scc_cli/adapters/codex_renderer.py, tests/test_codex_renderer.py
  - Verify: uv run pytest tests/test_codex_renderer.py -v && uv run mypy src/scc_cli/adapters/codex_renderer.py
- [x] **T04: Added 5 cross-provider pipeline integration tests for portable artifacts and updated truthfulness test** — 1. Add cross-provider integration tests to test_render_pipeline_integration.py verifying portable artifacts render on both providers.
2. Update test_docs_truthfulness.py if the D023 comment in bundle_resolver.py needs updating.
3. Run full test suite, ruff, mypy.
4. Verify no regressions.
  - Estimate: 20min
  - Files: tests/test_render_pipeline_integration.py, tests/test_docs_truthfulness.py
  - Verify: uv run pytest --rootdir "$PWD" -q && uv run ruff check && uv run mypy src/scc_cli
