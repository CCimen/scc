# S05: Coverage on governed-artifact/team-pack planning and renderer seams

**Goal:** Drive coverage on the governed-artifact/team-pack planning and renderer seams. Add contract tests for bundle resolution, render plan computation, and both provider renderers. Cover failure paths: missing bundles, invalid bindings, renderer errors. Ensure the planning→rendering pipeline has sufficient test protection to support future evolution.
**Demo:** After this: Contract tests verify bundle resolution, render plan computation, and both provider renderers; failure paths (missing bundles, invalid bindings, renderer errors) have explicit test coverage

## Tasks
- [ ] **T01: Contract tests for bundle resolution and render plan computation** — Write comprehensive contract tests for src/scc_cli/core/bundle_resolver.py:
1. Happy path: team with enabled bundles → complete ArtifactRenderPlan with correct bindings and effective_artifacts
2. Multi-bundle: team enables multiple bundles → artifacts deduplicated and ordered
3. Shared artifacts: skill + MCP appear in plan for both providers with no provider-specific bindings
4. Provider-specific: native_integration with Claude binding → appears for Claude, skipped for Codex
5. Install intent filtering: disabled artifacts excluded, required auto-included, available preserved
6. Missing bundle reference: clear error message listing available bundles
7. Missing artifact in bundle: partial resolution with skip report
8. Empty team config: empty plan, no error
9. Coverage target: >95% branch coverage on bundle_resolver.py
  - Estimate: 1h30m
  - Files: tests/test_bundle_resolver.py, tests/test_bundle_resolver_contracts.py
  - Verify: uv run pytest tests/test_bundle_resolver_contracts.py -v && uv run pytest --cov=scc_cli.core.bundle_resolver --cov-report=term-missing --cov-branch
- [ ] **T02: Characterization tests for Claude renderer** — Write characterization tests for src/scc_cli/adapters/claude_renderer.py:
1. Skill rendering: skill artifact → installed in Claude skill surface
2. MCP rendering: MCP server artifact → Claude-native MCP configuration
3. Marketplace rendering: native_integration with Claude marketplace binding → marketplace metadata
4. Hook rendering: native_integration with Claude hook binding → hook configuration
5. Mixed bundle: bundle with skills + MCP + native → all rendered correctly
6. Skipped artifact: artifact with only Codex binding → skipped with reason
7. Idempotency: same plan rendered twice → identical output
8. Failure: materialization error → blocked with diagnostic
9. Coverage target: >90% branch coverage on claude_renderer.py
  - Estimate: 1h30m
  - Files: tests/test_claude_renderer.py
  - Verify: uv run pytest tests/test_claude_renderer.py -v && uv run pytest --cov=scc_cli.adapters.claude_renderer --cov-report=term-missing --cov-branch
- [ ] **T03: Characterization tests for Codex renderer** — Write characterization tests for src/scc_cli/adapters/codex_renderer.py:
1. Skill rendering: skill artifact → .agents/skills/ placement
2. MCP rendering: MCP server artifact → .codex/config.toml or .mcp.json entry
3. Plugin bundle rendering: native_integration with Codex plugin binding → .codex-plugin/plugin.json
4. Rules rendering: native_integration with Codex rules binding → .codex/rules/*.rules
5. Hooks rendering: native_integration with Codex hooks binding → .codex/hooks.json
6. AGENTS.md rendering: native_integration with Codex instructions binding → AGENTS.md section
7. Asymmetry test: bundle with Claude-only native_integration → skipped for Codex with clear reason
8. Merge strategy: SCC-managed sections marked; non-SCC content preserved
9. Coverage target: >90% branch coverage on codex_renderer.py
  - Estimate: 1h30m
  - Files: tests/test_codex_renderer.py
  - Verify: uv run pytest tests/test_codex_renderer.py -v && uv run pytest --cov=scc_cli.adapters.codex_renderer --cov-report=term-missing --cov-branch
- [ ] **T04: Cross-provider render plan equivalence and pipeline integration tests** — Write integration tests that exercise the full planning→rendering pipeline:
1. Same org config + same team → same shared artifacts (skills, MCP) appear in both Claude and Codex plans
2. Provider-specific bindings appear only for the matching provider
3. Switching provider re-renders from same plan, produces different native outputs
4. End-to-end: NormalizedOrgConfig → resolve_render_plan → render_*_artifacts → verify file outputs
5. Backward compatibility: teams without governed_artifacts config → old marketplace pipeline still works
6. Coverage across the pipeline seam: bundle_resolver + renderer boundary contracts verified
  - Estimate: 1h30m
  - Files: tests/test_render_pipeline_integration.py
  - Verify: uv run pytest tests/test_render_pipeline_integration.py -v && uv run pytest --rootdir "$PWD" -q
