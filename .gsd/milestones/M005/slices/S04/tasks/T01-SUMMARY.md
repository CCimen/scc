---
id: T01
parent: S04
milestone: M005
key_files:
  - src/scc_cli/core/bundle_resolver.py
  - src/scc_cli/ports/config_models.py
  - src/scc_cli/adapters/config_normalizer.py
  - tests/test_bundle_resolver.py
  - .gsd/DECISIONS.md
key_decisions:
  - D022: Fixed D019 ID collision (replan→D021) and tightened T05 — bundle pipeline is canonical, not parallel with long-lived Claude fallback
  - GovernedArtifactsCatalog as typed bridge between raw config and resolution
  - Skills and MCP servers portable without binding; native_integrations require provider binding
duration: 
verification_result: passed
completed_at: 2026-04-04T18:49:22.101Z
blocker_discovered: false
---

# T01: Created pure core bundle resolver (resolve_render_plan), extended config models with GovernedArtifactsCatalog/enabled_bundles, fixed D019 ID collision (→D021), tightened T05 to make bundle pipeline canonical (D022)

**Created pure core bundle resolver (resolve_render_plan), extended config models with GovernedArtifactsCatalog/enabled_bundles, fixed D019 ID collision (→D021), tightened T05 to make bundle pipeline canonical (D022)**

## What Happened

Applied two user-directed alignment fixes (D022): reassigned S03 closeout/replan from D019 to D021 to fix collision with the asymmetric-surfaces architecture decision, and tightened S04/T05 so the bundle/team-pack pipeline is canonical (no long-lived Claude fallback in core). Then implemented the pure core bundle resolver: added GovernedArtifactsCatalog (artifacts + bindings + bundles) and enabled_bundles to config models, extended the normalizer to parse the spec-06 governed_artifacts section, and created core/bundle_resolver.py with resolve_render_plan() that reads a team's enabled bundles, resolves against the catalog, filters by install_intent and provider compatibility, and returns ArtifactRenderPlans with skip diagnostics. 23 new tests, all 4140 tests passing.

## Verification

ruff check: 0 errors. mypy: 0 errors in 286 files. pytest tests/test_bundle_resolver.py -v: 23 passed (100% coverage on bundle_resolver.py). pytest full suite: 4140 passed, 23 skipped, 3 xfailed, 1 xpassed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 12000ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 16000ms |
| 3 | `uv run pytest tests/test_bundle_resolver.py -v` | 0 | ✅ pass | 7000ms |
| 4 | `uv run pytest --rootdir "$PWD" -q` | 0 | ✅ pass | 69000ms |

## Deviations

Added pre-task D022 alignment fixes (D019→D021 ID reassignment, T05 fallback language tightening) per user directive before starting T01 implementation.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/core/bundle_resolver.py`
- `src/scc_cli/ports/config_models.py`
- `src/scc_cli/adapters/config_normalizer.py`
- `tests/test_bundle_resolver.py`
- `.gsd/DECISIONS.md`
