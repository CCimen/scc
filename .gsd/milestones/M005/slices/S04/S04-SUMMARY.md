---
id: S04
parent: M005
milestone: M005
provides:
  - ArtifactRenderPlan type and resolve_render_plan() pure function in core/bundle_resolver.py
  - Claude-native renderer (render_claude_artifacts) consuming ArtifactRenderPlan
  - Codex-native renderer (render_codex_artifacts) consuming ArtifactRenderPlan
  - RendererError exception hierarchy in core/errors.py
  - RenderArtifactsResult unified return type in core/contracts.py
  - AgentProvider.render_artifacts() protocol method
  - Bundle pipeline integrated into prepare_start_session launch flow
  - 126 new tests covering resolution, rendering, error handling, and launch wiring
requires:
  - slice: S03
    provides: GovernedArtifact type hierarchy, NormalizedOrgConfig with from_dict, typed StartSessionRequest, 4117-test baseline
affects:
  - S05
  - S06
key_files:
  - src/scc_cli/core/bundle_resolver.py
  - src/scc_cli/adapters/claude_renderer.py
  - src/scc_cli/adapters/codex_renderer.py
  - src/scc_cli/core/errors.py
  - src/scc_cli/core/contracts.py
  - src/scc_cli/ports/agent_provider.py
  - src/scc_cli/ports/config_models.py
  - src/scc_cli/adapters/claude_agent_provider.py
  - src/scc_cli/adapters/codex_agent_provider.py
  - src/scc_cli/application/start_session.py
  - tests/test_bundle_resolver.py
  - tests/test_claude_renderer.py
  - tests/test_codex_renderer.py
  - tests/test_application_start_session.py
  - tests/fakes/fake_agent_provider.py
key_decisions:
  - D022: Fixed D019 ID collision (→D021) and tightened T05 to make bundle pipeline canonical, not parallel with long-lived Claude fallback
  - D023: Shared artifacts must be renderable without provider bindings
  - D024: Codex renderer must produce real native surfaces, not just SCC metadata
  - D025: T05 wires bundle pipeline through AgentProvider as canonical path
  - Renderer returns settings_fragment/mcp_fragment for caller-owned merge — does not write provider config files directly
  - RendererError hierarchy with exit_code=4 for external-surface materialization failures
  - fail_closed opt-in (default False) for backward compatibility; launch pipeline uses fail_closed=True
  - SCC-managed content under .claude/.scc-managed/ and .codex/.scc-managed/ to avoid user file collisions
  - RenderArtifactsResult as unified provider-neutral return type unifying Claude settings_fragment and Codex mcp_fragment
patterns_established:
  - classify→dispatch renderer pattern: _classify_binding heuristic routes each ArtifactBinding to the appropriate provider-native surface writer
  - Fragment-return pattern: renderers return dict fragments for caller-owned merge instead of writing shared config files directly
  - .scc-managed/ namespace pattern: provider-specific managed directories avoid user file collisions while enabling idempotent re-rendering
  - scc_managed namespace in hooks merge: per-bundle namespace key preserves existing user content in shared JSON files
  - Bundle pipeline gating: _render_bundle_artifacts checks org_config + team + provider before resolving; skips cleanly for dry-run/offline/standalone
  - Error capture pattern: launch pipeline catches RendererError and records on StartSessionPlan.bundle_render_error instead of raising
  - Per-bundle audit file pattern: renderers write .scc-settings-{bundle}.json / .scc-mcp-{bundle}.json for diagnostics
observability_surfaces:
  - StartSessionPlan.bundle_render_results — array of RenderArtifactsResult for each rendered bundle
  - StartSessionPlan.bundle_render_error — captured error diagnostic when resolution or rendering fails
  - Per-bundle audit files: .scc-settings-{bundle}.json (Claude) and .scc-mcp-{bundle}.json (Codex) for support bundles
  - RendererResult.skipped_artifacts — list of artifacts skipped with reasons (no binding, disabled, unavailable)
  - RendererResult.warnings — diagnostic messages for wrong-provider, missing native_ref, etc.
drill_down_paths:
  - .gsd/milestones/M005/slices/S04/tasks/T01-SUMMARY.md
  - .gsd/milestones/M005/slices/S04/tasks/T02-SUMMARY.md
  - .gsd/milestones/M005/slices/S04/tasks/T03-SUMMARY.md
  - .gsd/milestones/M005/slices/S04/tasks/T04-SUMMARY.md
  - .gsd/milestones/M005/slices/S04/tasks/T05-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-04T19:44:01.873Z
blocker_discovered: false
---

# S04: Provider-neutral artifact planning pipeline and provider-native renderers with hardened failure handling

**Built the complete provider-neutral bundle resolution → ArtifactRenderPlan → provider-native renderer pipeline for Claude and Codex, with fail-closed error handling and launch pipeline integration, adding 126 new tests (4237 total).**

## What Happened

S04 delivered the core artifact planning pipeline that the governed-artifact/team-pack architecture (D017-D020, specs/03, specs/06) requires. The slice split cleanly into five tasks across three layers:

**T01 — Bundle resolver (core layer).** Created `core/bundle_resolver.py` with a pure function `resolve_render_plan()` that takes NormalizedOrgConfig, team name, and provider, then resolves enabled bundles against the governed_artifacts catalog, filters by install_intent and provider compatibility, produces typed ArtifactRenderPlan with bindings and skip diagnostics. Extended config models with GovernedArtifactsCatalog and enabled_bundles fields. Extended config_normalizer to parse the spec-06 governed_artifacts section. Also fixed a D019 ID collision (replan decision reassigned to D021) and tightened T05 scope to make the bundle pipeline canonical (D022). 33 tests.

**T02 — Claude renderer (adapter layer).** Created `adapters/claude_renderer.py` consuming ArtifactRenderPlan and projecting into Claude-native file structures: skills → .claude/.scc-managed/skills/ metadata, MCP servers (SSE/HTTP/stdio) → settings_fragment entries, native integrations → hooks/instructions/marketplace/plugin metadata. Returns RendererResult with rendered_paths, skipped_artifacts, warnings, and settings_fragment for caller-owned merge. Per-bundle audit file for diagnostics. 34 tests at 98% coverage.

**T03 — Codex renderer (adapter layer).** Created `adapters/codex_renderer.py` with the same classify→dispatch pattern but targeting intentionally asymmetric Codex surfaces per D019: skills → .agents/skills/, MCP servers → mcp_fragment dict, plugin_bundle → .codex-plugin/plugin.json, rules → .codex/rules/*.rules.json, hooks → .codex/hooks.json with merge-safe scc_managed namespace, instructions → .codex/.scc-managed/instructions/. 38 tests at 99% coverage.

**T04 — Error handling (cross-cutting).** Created RendererError exception hierarchy (RendererError → BundleResolutionError, InvalidArtifactReferenceError, MaterializationError, MergeConflictError) in core/errors.py with exit_code=4. Added fail_closed mode to resolve_render_plan(). Wrapped every file-write path in both renderers with MaterializationError fail-closed semantics. Handled macOS PermissionError edge case on locked directories. 27 negative tests covering all failure paths. Recorded D023-D025 from user direction.

**T05 — Launch pipeline wiring (application layer).** Added RenderArtifactsResult to core/contracts.py as unified return type. Extended AgentProvider protocol with render_artifacts(). Wired ClaudeAgentProvider and CodexAgentProvider to delegate to their renderers. Integrated bundle pipeline into prepare_start_session via _render_bundle_artifacts() with fail_closed=True resolution. Extended StartSessionPlan with bundle_render_results and bundle_render_error. Pipeline gated on org_config + team + provider; skips in dry-run/offline/standalone. 15 new tests covering all skip gates, error capture, delegation, and fragment propagation.

**Total: 126 new S04 tests, 4237 total suite (23 skipped, 3 xfailed, 1 xpassed). Zero regressions.**

## Verification

All four verification gates pass:
1. `uv run ruff check` — 0 errors
2. `uv run mypy src/scc_cli` — Success: no issues found in 288 source files
3. `uv run pytest tests/test_bundle_resolver.py tests/test_claude_renderer.py tests/test_codex_renderer.py tests/test_application_start_session.py -v` — 126 passed
4. `uv run pytest --rootdir "$PWD" -q` — 4237 passed, 23 skipped, 3 xfailed, 1 xpassed

Key coverage metrics for new files:
- core/bundle_resolver.py: 100%
- adapters/claude_renderer.py: 98%
- adapters/codex_renderer.py: 99%
- core/contracts.py: 100%
- ports/agent_provider.py: 100%
- adapters/claude_agent_provider.py: 100%
- adapters/codex_agent_provider.py: 100%
- application/start_session.py: 92%

## Requirements Advanced

- R001 — S04 built the provider-neutral bundle resolution pipeline and two provider-native renderers as clean, typed, well-tested modules (100%/98%/99% coverage). The architecture keeps core bundle logic pure (zero adapter/marketplace imports), renderers adapter-owned, and launch integration application-owned — improving maintainability, testability, and changeability of the governed-artifact pipeline.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

T01 included pre-task alignment fixes (D022): D019 ID collision reassigned to D021, and T05 fallback language tightened to make bundle pipeline canonical per user directive. T04 recorded D023-D025 from user direction during implementation. No structural deviations from the slice plan.

## Known Limitations

D023 noted that shared/portable artifacts in effective_artifacts without provider bindings are not yet rendered by the binding-only dispatch path. D024 noted Codex renderer produces metadata-enriched native surface files but full native surface fidelity depends on real bundle content (not yet available from a live registry). MergeConflictError defined but not yet raised — available for future merge layer when concurrent rendering conflicts need detection.

## Follow-ups

S05 (coverage on governed-artifact/team-pack planning and renderer seams) will add contract tests for bundle resolution, render plan computation, and both provider renderers including failure paths. S06 (diagnostics/docs truthfulness) will verify that diagnostic surfaces show active team context, effective bundles, and rendered/skipped/blocked artifacts.

## Files Created/Modified

- `src/scc_cli/core/bundle_resolver.py` — New: pure function resolve_render_plan() computing ArtifactRenderPlan from NormalizedOrgConfig + team + provider
- `src/scc_cli/adapters/claude_renderer.py` — New: render_claude_artifacts() projecting ArtifactRenderPlan into Claude-native skills, MCP config, hooks, marketplace, plugin, instruction metadata
- `src/scc_cli/adapters/codex_renderer.py` — New: render_codex_artifacts() projecting ArtifactRenderPlan into Codex-native skills, MCP config, plugin, rules, hooks, instructions
- `src/scc_cli/core/errors.py` — Extended: RendererError hierarchy (BundleResolutionError, InvalidArtifactReferenceError, MaterializationError, MergeConflictError)
- `src/scc_cli/core/contracts.py` — Extended: RenderArtifactsResult unified return type
- `src/scc_cli/ports/agent_provider.py` — Extended: render_artifacts() method on AgentProvider protocol
- `src/scc_cli/ports/config_models.py` — Extended: GovernedArtifactsCatalog and enabled_bundles fields on NormalizedOrgConfig/NormalizedTeamConfig
- `src/scc_cli/adapters/config_normalizer.py` — Extended: parsing governed_artifacts section from raw org config
- `src/scc_cli/adapters/claude_agent_provider.py` — Extended: render_artifacts() delegating to claude_renderer
- `src/scc_cli/adapters/codex_agent_provider.py` — Extended: render_artifacts() delegating to codex_renderer
- `src/scc_cli/application/start_session.py` — Extended: _render_bundle_artifacts() integrated into prepare_start_session, StartSessionPlan extended with bundle_render_results/bundle_render_error
- `tests/test_bundle_resolver.py` — New: 33 tests for bundle resolution including fail_closed paths
- `tests/test_claude_renderer.py` — New: 34 tests for Claude renderer including materialization failures
- `tests/test_codex_renderer.py` — New: 38 tests for Codex renderer including all failure paths
- `tests/test_application_start_session.py` — Extended: 15 new tests for bundle pipeline wiring, skip gates, error capture
- `tests/fakes/fake_agent_provider.py` — Extended: render_artifacts support with call recording
- `.gsd/DECISIONS.md` — Extended: D022-D025 recorded
- `.gsd/KNOWLEDGE.md` — Extended: 6 new knowledge entries for renderer patterns and gotchas
