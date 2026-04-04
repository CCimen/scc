# S04: Provider-neutral artifact planning pipeline and provider-native renderers with hardened failure handling — UAT

**Milestone:** M005
**Written:** 2026-04-04T19:44:01.873Z

## UAT: S04 — Provider-neutral artifact planning pipeline and provider-native renderers

### Preconditions
- Python 3.10+ with `uv sync` completed
- Working directory: `scc-sync-1.7.3/`
- All tests passing: `uv run pytest --rootdir "$PWD" -q`

---

### TC-01: Bundle resolution produces typed ArtifactRenderPlan
**Steps:**
1. Run `uv run pytest tests/test_bundle_resolver.py::TestBasicResolution -v`
2. Verify tests confirm resolve_render_plan returns ArtifactRenderPlan with correct bindings for single skill, multiple bundles, and multiple artifact kinds
**Expected:** All 3 tests pass. Plan contains typed bindings with artifact_id, artifact_kind, provider, native_ref, and native_config.

### TC-02: Bundle resolution filters by provider and install_intent
**Steps:**
1. Run `uv run pytest tests/test_bundle_resolver.py::TestProviderFiltering tests/test_bundle_resolver.py::TestInstallIntentFiltering -v`
2. Verify binding_only_for_other_provider is skipped, disabled/request_only artifacts are skipped, skills/MCP without bindings still appear in effective_artifacts
**Expected:** All 8 tests pass. Skip diagnostics contain reason strings.

### TC-03: Bundle resolution fail_closed mode
**Steps:**
1. Run `uv run pytest tests/test_bundle_resolver.py::TestFailClosedMissingBundle tests/test_bundle_resolver.py::TestFailClosedInvalidArtifact -v`
2. Verify missing bundle raises BundleResolutionError with available_bundles list
3. Verify invalid artifact ref raises InvalidArtifactReferenceError with bundle_id
4. Verify disabled bundle skips (not raises) even in fail_closed mode
**Expected:** All 7 tests pass. Error messages include actionable alternatives.

### TC-04: Claude renderer projects all binding types
**Steps:**
1. Run `uv run pytest tests/test_claude_renderer.py::TestSkillBinding tests/test_claude_renderer.py::TestMCPBinding tests/test_claude_renderer.py::TestNativeIntegrationBinding -v`
2. Verify skills create metadata files under .claude/.scc-managed/skills/
3. Verify MCP servers (SSE, HTTP, stdio) produce settings_fragment entries
4. Verify native integrations produce hooks, marketplace, plugin, instruction metadata
**Expected:** All 14 tests pass. Rendered paths are Path objects. Settings fragment is a dict.

### TC-05: Codex renderer projects asymmetric native surfaces
**Steps:**
1. Run `uv run pytest tests/test_codex_renderer.py::TestSkillBinding tests/test_codex_renderer.py::TestMCPBinding tests/test_codex_renderer.py::TestNativeIntegrationBinding -v`
2. Verify skills create files under .agents/skills/
3. Verify MCP servers produce mcp_fragment dict entries
4. Verify plugin_bundle creates .codex-plugin/plugin.json
5. Verify rules create .codex/rules/*.rules.json
6. Verify hooks merge preserves existing content via scc_managed namespace
7. Verify instructions go to .codex/.scc-managed/instructions/
**Expected:** All 14 tests pass. Codex surfaces differ from Claude per D019.

### TC-06: Renderers handle materialization failures
**Steps:**
1. Run `uv run pytest tests/test_claude_renderer.py::TestSkillMaterializationFailure tests/test_claude_renderer.py::TestNativeIntegrationMaterializationFailure tests/test_codex_renderer.py::TestSkillMaterializationFailure tests/test_codex_renderer.py::TestPluginCreationFailure tests/test_codex_renderer.py::TestRulesWriteFailure tests/test_codex_renderer.py::TestHooksWriteFailure -v`
2. Verify read-only workspace raises MaterializationError
3. Verify all file-write failures raise MaterializationError with structured fields
4. Verify hooks read OSError raises MaterializationError (macOS PermissionError case)
**Expected:** All 10 tests pass. MaterializationError inherits from RendererError (exit_code=4).

### TC-07: Error hierarchy structure
**Steps:**
1. Run `uv run pytest tests/test_bundle_resolver.py::TestErrorHierarchy tests/test_claude_renderer.py::TestRendererErrorHierarchy tests/test_codex_renderer.py::TestRendererErrorHierarchy -v`
2. Verify BundleResolutionError, InvalidArtifactReferenceError, MaterializationError, MergeConflictError all inherit from RendererError
3. Verify RendererError has exit_code=4
**Expected:** All 7 tests pass.

### TC-08: Launch pipeline wires bundle rendering
**Steps:**
1. Run `uv run pytest tests/test_application_start_session.py::TestBundlePipelineWiring -v`
2. Verify happy-path renders artifacts into StartSessionPlan.bundle_render_results
3. Verify pipeline skips when no team, dry-run, offline, standalone, or no provider
4. Verify resolution error captured on plan.bundle_render_error
5. Verify renderer error captured on plan.bundle_render_error
6. Verify empty bundles produce no error
**Expected:** All 10 tests pass.

### TC-09: AgentProvider render_artifacts delegation
**Steps:**
1. Run `uv run pytest tests/test_application_start_session.py::TestAgentProviderRenderArtifacts -v`
2. Verify ClaudeAgentProvider delegates to claude_renderer and returns settings_fragment
3. Verify CodexAgentProvider delegates to codex_renderer and maps mcp_fragment to settings_fragment
4. Verify wrong-provider plan returns warnings
**Expected:** All 5 tests pass.

### TC-10: Idempotent rendering
**Steps:**
1. Run `uv run pytest tests/test_claude_renderer.py::TestIdempotent tests/test_codex_renderer.py::TestIdempotent -v`
2. Verify same plan produces identical output on re-render
3. Verify existing files are overwritten cleanly
**Expected:** All 4 tests pass.

### TC-11: Full regression suite
**Steps:**
1. Run `uv run ruff check`
2. Run `uv run mypy src/scc_cli`
3. Run `uv run pytest --rootdir "$PWD" -q`
**Expected:** 0 lint errors, 0 type errors in 288 files, 4237 passed / 23 skipped / 3 xfailed / 1 xpassed.
