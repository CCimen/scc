---
estimated_steps: 6
estimated_files: 5
skills_used: []
---

# T05: Wire renderers into launch pipeline via AgentProvider.render_artifacts

Add a render_artifacts(plan: ArtifactRenderPlan, workspace: Path) -> RendererResult method to the AgentProvider protocol. Wire ClaudeAgentProvider to call claude_renderer and CodexAgentProvider to call codex_renderer. Update the launch flow (start_session or sync_marketplace_settings_for_start) to:
1. Resolve render plan from org_config + team + provider
2. Call provider.render_artifacts(plan, workspace)
3. Handle renderer failures according to fail-closed semantics
4. Log/audit rendered artifacts

The bundle/team-pack pipeline is the canonical artifact path. The old Claude-shaped marketplace pipeline is not preserved as a long-lived fallback in core. If a short-term migration shim is genuinely needed for Claude sessions during the transition, it must be explicitly adapter-local (inside claude_agent_provider.py only), clearly marked as transitional, and must not leak marketplace-shaped assumptions into core, ports, or the AgentProvider protocol.

## Inputs

- `src/scc_cli/ports/agent_provider.py`
- `src/scc_cli/core/bundle_resolver.py`
- `src/scc_cli/adapters/claude_renderer.py`
- `src/scc_cli/adapters/codex_renderer.py`

## Expected Output

- `src/scc_cli/ports/agent_provider.py (render_artifacts method)`
- `src/scc_cli/adapters/claude_agent_provider.py (wired)`
- `src/scc_cli/adapters/codex_agent_provider.py (wired)`

## Verification

uv run ruff check && uv run mypy src/scc_cli && uv run pytest tests/test_application_start_session.py -v && uv run pytest --rootdir "$PWD" -q
