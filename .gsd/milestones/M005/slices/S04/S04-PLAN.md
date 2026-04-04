# S04: Provider-neutral artifact planning pipeline and provider-native renderers with hardened failure handling

**Goal:** Build the provider-neutral artifact planning pipeline (org config → bundle resolution → ArtifactRenderPlan) and provider-native renderers (Claude, Codex) consuming ArtifactRenderPlan. Harden fetch/render/merge/install failure handling with fail-closed semantics. Split provider-neutral planning from provider-native rendering. Team config references bundle IDs, not raw marketplace URLs. Claude and Codex native surfaces are intentionally asymmetric per D019/specs/03/specs/06.
**Demo:** After this: Team config references bundle IDs; SCC resolves bundles to ArtifactRenderPlan; Claude adapter renders settings.local.json + marketplace from plan; Codex adapter renders plugin + rules + hooks from same plan; fetch/render failures are fail-closed with clear diagnostics

## Tasks
- [x] **T01: Created pure core bundle resolver (resolve_render_plan), extended config models with GovernedArtifactsCatalog/enabled_bundles, fixed D019 ID collision (→D021), tightened T05 to make bundle pipeline canonical (D022)** — Create src/scc_cli/core/bundle_resolver.py with a pure function resolve_render_plan(org_config: NormalizedOrgConfig, team_name: str, provider: str) -> ArtifactRenderPlan. This function:
1. Reads the team profile's enabled_bundles list from org_config
2. Resolves each bundle ID against the org's governed_artifacts catalog
3. Filters artifacts by install_intent and provider compatibility
4. Produces bindings for artifacts that have ProviderArtifactBinding for the target provider
5. Reports skipped artifacts (no binding for provider, disabled, unavailable)
6. Returns a complete ArtifactRenderPlan

Also extend NormalizedOrgConfig and NormalizedTeamConfig to carry governed_artifacts and enabled_bundles fields.

This is a pure core function — no imports from marketplace/, adapters/, or commands/.
  - Estimate: 2h
  - Files: src/scc_cli/core/bundle_resolver.py, src/scc_cli/ports/config_models.py, src/scc_cli/adapters/config_normalizer.py, tests/test_bundle_resolver.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_bundle_resolver.py -v && uv run pytest --rootdir "$PWD" -q
- [x] **T02: Created claude_renderer.py with render_claude_artifacts() projecting ArtifactRenderPlan into Claude-native skills, MCP config, hooks/marketplace/plugin/instruction metadata, and settings fragments, with 26 characterization tests at 98% coverage** — Create src/scc_cli/adapters/claude_renderer.py with a function render_claude_artifacts(plan: ArtifactRenderPlan, workspace: Path) -> RendererResult. This adapter-owned renderer:
1. Consumes an ArtifactRenderPlan produced by the core bundle resolver
2. Renders skills into the Claude skill installation surface
3. Renders MCP server definitions into Claude-native MCP config
4. Renders native_integration bindings into Claude-specific surfaces (marketplace metadata, hook config, plugin directories)
5. Returns a RendererResult with rendered paths, skipped items, and any warnings

The renderer is adapter-owned — it may import from marketplace/ for Claude-specific materialization helpers but the planning input is always an ArtifactRenderPlan.

Add characterization tests that verify the renderer produces expected file structures from known plans.
  - Estimate: 2h30m
  - Files: src/scc_cli/adapters/claude_renderer.py, tests/test_claude_renderer.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_claude_renderer.py -v && uv run pytest --rootdir "$PWD" -q
- [ ] **T03: Codex renderer: project ArtifactRenderPlan into Codex-native surfaces** — Create src/scc_cli/adapters/codex_renderer.py with a function render_codex_artifacts(plan: ArtifactRenderPlan, workspace: Path) -> RendererResult. This adapter-owned renderer:
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
  - Estimate: 2h30m
  - Files: src/scc_cli/adapters/codex_renderer.py, tests/test_codex_renderer.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_codex_renderer.py -v && uv run pytest --rootdir "$PWD" -q
- [ ] **T04: Harden fetch/render/merge/install failure handling with fail-closed semantics** — Add explicit error handling to the bundle resolver and both renderers:
1. Bundle resolver: missing bundle ID → clear error with available alternatives; disabled bundle → skip with audit log; invalid artifact reference → fail-closed block
2. Claude renderer: materialization failure → blocked with diagnostic; merge conflict → fail with conflict report; file write failure → blocked
3. Codex renderer: plugin creation failure → blocked; rules/hooks write failure → blocked; merge conflict on single-file surfaces → fail with conflict report
4. Create a RendererError exception hierarchy in core/errors.py
5. Ensure all failure paths produce structured error info suitable for support bundles and doctor checks
6. Add negative tests for each failure path
  - Estimate: 2h
  - Files: src/scc_cli/core/bundle_resolver.py, src/scc_cli/adapters/claude_renderer.py, src/scc_cli/adapters/codex_renderer.py, src/scc_cli/core/errors.py, tests/test_bundle_resolver.py, tests/test_claude_renderer.py, tests/test_codex_renderer.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_bundle_resolver.py tests/test_claude_renderer.py tests/test_codex_renderer.py -v && uv run pytest --rootdir "$PWD" -q
- [ ] **T05: Wire renderers into launch pipeline via AgentProvider.render_artifacts** — Add an optional render_artifacts(plan: ArtifactRenderPlan, workspace: Path) -> RendererResult method to the AgentProvider protocol. Wire ClaudeAgentProvider to call claude_renderer and CodexAgentProvider to call codex_renderer. Update the launch flow (start_session or sync_marketplace_settings_for_start) to:
1. Resolve render plan from org_config + team + provider
2. Call provider.render_artifacts(plan, workspace)
3. Handle renderer failures according to fail-closed semantics
4. Log/audit rendered artifacts

The existing marketplace pipeline continues to work as a fallback for Claude sessions that haven't migrated to bundle-based config. New bundle-based teams use the new pipeline. This is a backward-compatible addition, not a forced migration.
  - Estimate: 2h
  - Files: src/scc_cli/ports/agent_provider.py, src/scc_cli/adapters/claude_agent_provider.py, src/scc_cli/adapters/codex_agent_provider.py, src/scc_cli/application/start_session.py, tests/test_application_start_session.py
  - Verify: uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_application_start_session.py -v && uv run pytest --rootdir "$PWD" -q
