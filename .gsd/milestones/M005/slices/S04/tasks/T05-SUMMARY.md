---
id: T05
parent: S04
milestone: M005
key_files:
  - src/scc_cli/ports/agent_provider.py
  - src/scc_cli/adapters/claude_agent_provider.py
  - src/scc_cli/adapters/codex_agent_provider.py
  - src/scc_cli/core/contracts.py
  - src/scc_cli/application/start_session.py
  - tests/fakes/fake_agent_provider.py
  - tests/test_application_start_session.py
key_decisions:
  - RenderArtifactsResult as unified provider-neutral return type in core/contracts.py
  - Codex mcp_fragment mapped to settings_fragment in unified result
  - Bundle pipeline gated on org_config + team + provider; skips in dry-run/offline/standalone
  - fail_closed=True for resolution in launch flow; errors captured on plan, not raised
  - StartSessionPlan extended with bundle_render_results and bundle_render_error fields
duration: 
verification_result: passed
completed_at: 2026-04-04T19:37:27.007Z
blocker_discovered: false
---

# T05: Wire render_artifacts into AgentProvider protocol and launch pipeline with fail-closed bundle resolution, Claude/Codex adapter delegation, and 15 new tests

**Wire render_artifacts into AgentProvider protocol and launch pipeline with fail-closed bundle resolution, Claude/Codex adapter delegation, and 15 new tests**

## What Happened

Added RenderArtifactsResult to core/contracts.py as the unified provider-neutral return type. Extended AgentProvider protocol with render_artifacts(plan, workspace) method. Wired ClaudeAgentProvider to delegate to claude_renderer and CodexAgentProvider to codex_renderer, wrapping adapter-specific results into the unified type. Integrated the bundle pipeline into prepare_start_session via _render_bundle_artifacts() which resolves plans with fail_closed=True and captures RendererError as diagnostic messages on StartSessionPlan. Extended StartSessionPlan with bundle_render_results and bundle_render_error fields. Wrote 15 new tests covering happy-path rendering, all skip gates (no team, dry-run, offline, standalone, no provider), resolution error capture, renderer error capture, empty bundles, call recording, Claude/Codex delegation, settings fragment propagation, and wrong-provider warnings.

## Verification

All four verification commands pass: ruff check (0 errors), mypy (0 issues in 288 source files), pytest targeted (21 tests in test_application_start_session.py), and full pytest suite (4237 passed, 23 skipped, 3 xfailed, 1 xpassed). Coverage for modified files: claude_agent_provider.py 100%, codex_agent_provider.py 100%, agent_provider.py 100%, contracts.py 100%, start_session.py 92%.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run ruff check` | 0 | ✅ pass | 5000ms |
| 2 | `uv run mypy src/scc_cli` | 0 | ✅ pass | 4000ms |
| 3 | `uv run pytest tests/test_application_start_session.py -v` | 0 | ✅ pass (21 tests) | 1300ms |
| 4 | `uv run pytest --rootdir "$PWD" -q` | 0 | ✅ pass (4237 tests) | 66000ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/scc_cli/ports/agent_provider.py`
- `src/scc_cli/adapters/claude_agent_provider.py`
- `src/scc_cli/adapters/codex_agent_provider.py`
- `src/scc_cli/core/contracts.py`
- `src/scc_cli/application/start_session.py`
- `tests/fakes/fake_agent_provider.py`
- `tests/test_application_start_session.py`
