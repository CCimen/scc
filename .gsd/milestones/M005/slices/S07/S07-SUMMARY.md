---
id: S07
parent: M005
milestone: M005
provides:
  - D023 implementation: portable skills and MCP servers renderable without provider bindings
requires:
  - slice: S04
    provides: Bundle resolver, ArtifactRenderPlan, provider-native renderers
  - slice: S05
    provides: 100% branch coverage baseline on pipeline modules
affects:
  []
key_files:
  - src/scc_cli/core/governed_artifacts.py
  - src/scc_cli/core/bundle_resolver.py
  - src/scc_cli/adapters/claude_renderer.py
  - src/scc_cli/adapters/codex_renderer.py
  - tests/test_claude_renderer.py
  - tests/test_codex_renderer.py
  - tests/test_render_pipeline_integration.py
  - tests/test_docs_truthfulness.py
key_decisions:
  - PortableArtifact carries source metadata from GovernedArtifact for renderer consumption
  - Only SKILL and MCP_SERVER kinds qualify as portable — NATIVE_INTEGRATION always requires bindings
  - Portable marker (portable: true) distinguishes from binding-rendered artifacts in metadata
  - Updated truthfulness test to verify D023 implementation
patterns_established:
  - Portable artifact rendering pattern: resolver populates portable_artifacts, renderers iterate them after bindings
  - Source-metadata-driven rendering: renderers use artifact.source_url, source_type, source_ref for output without provider bindings
observability_surfaces:
  - RendererResult.rendered_paths now includes portable artifact outputs
  - Portable artifacts marked with portable: true in metadata files for diagnostic distinction
drill_down_paths:
  - .gsd/milestones/M005/slices/S07/tasks/T01-SUMMARY.md
  - .gsd/milestones/M005/slices/S07/tasks/T02-SUMMARY.md
  - .gsd/milestones/M005/slices/S07/tasks/T03-SUMMARY.md
  - .gsd/milestones/M005/slices/S07/tasks/T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-04-04T21:31:00.724Z
blocker_discovered: false
---

# S07: Render portable artifacts from effective_artifacts without provider bindings (D023)

**Implemented D023: portable skills and MCP servers without provider bindings are now renderable by both Claude and Codex renderers via PortableArtifact metadata in ArtifactRenderPlan, adding 23 new tests (4486 total).**

## What Happened

S07 closed the D023 architecture gap: before this slice, the resolver correctly placed portable artifacts into plan.effective_artifacts but renderers only iterated plan.bindings, leaving those artifacts with zero rendering output. T01 added PortableArtifact dataclass to governed_artifacts.py and populated portable_artifacts on ArtifactRenderPlan in the resolver. T02 extended the Claude renderer with _render_portable_skill and _render_portable_mcp, producing .claude/.scc-managed/skills/ metadata and mcpServers settings fragments. T03 did the same for Codex targeting .agents/skills/ and mcp_fragment. T04 added 5 cross-provider pipeline integration tests and updated the truthfulness test to reflect the new reality. All 4486 tests pass, ruff clean, mypy clean.

## Verification

uv run pytest --rootdir "$PWD" -q → 4486 passed, 23 skipped, 2 xfailed (70.48s); uv run ruff check → All checks passed; uv run mypy src/scc_cli → Success: 289 files

## Requirements Advanced

- R001 — D023 implementation completes the portable artifact rendering pipeline, ensuring all governed artifacts are renderable not just policy-effective

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Deviations

None.

## Known Limitations

Portable MCP server rendering defaults to SSE transport from source_url — stdio-based portable MCP servers would need additional source metadata (command, args) not yet modeled.

## Follow-ups

None.

## Files Created/Modified

- `src/scc_cli/core/governed_artifacts.py` — Added PortableArtifact dataclass and portable_artifacts field on ArtifactRenderPlan
- `src/scc_cli/core/bundle_resolver.py` — Resolver now populates portable_artifacts for binding-less SKILL and MCP_SERVER artifacts
- `src/scc_cli/adapters/claude_renderer.py` — Added _render_portable_skill and _render_portable_mcp; integrated into render_claude_artifacts
- `src/scc_cli/adapters/codex_renderer.py` — Added _render_portable_skill and _render_portable_mcp; integrated into render_codex_artifacts
- `tests/test_claude_renderer.py` — Added 9 portable artifact tests across 3 test classes
- `tests/test_codex_renderer.py` — Added 9 portable artifact tests across 3 test classes
- `tests/test_render_pipeline_integration.py` — Added 5 cross-provider pipeline integration tests for portable artifacts
- `tests/test_docs_truthfulness.py` — Updated truthfulness test to verify D023 implementation
