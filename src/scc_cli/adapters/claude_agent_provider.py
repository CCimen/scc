"""Claude Code adapter for AgentProvider port."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from scc_cli.adapters.claude_renderer import render_claude_artifacts
from scc_cli.core.contracts import AgentLaunchSpec, ProviderCapabilityProfile, RenderArtifactsResult
from scc_cli.core.governed_artifacts import ArtifactRenderPlan

logger = logging.getLogger(__name__)


class ClaudeAgentProvider:
    """AgentProvider implementation for Claude Code.

    Translates provider config and workspace context into a typed AgentLaunchSpec
    that the runtime layer can consume without importing Claude internals directly.
    """

    def capability_profile(self) -> ProviderCapabilityProfile:
        return ProviderCapabilityProfile(
            provider_id="claude",
            display_name="Claude Code",
            required_destination_set="anthropic-core",
            supports_resume=True,
            supports_skills=True,
            supports_native_integrations=True,
        )

    def prepare_launch(
        self,
        *,
        config: Mapping[str, Any],
        workspace: Path,
        settings_path: Path | None = None,
    ) -> AgentLaunchSpec:
        """Build a Claude-owned launch specification for one workspace.

        Args:
            config: Rendered agent settings payload (plugins, mcpServers, etc.).
                    Consumed by the settings artifact; not injected as env vars.
            workspace: Launch working directory.
            settings_path: Container path for the rendered settings.json artifact,
                           if any was built by the sync path.

        Returns:
            Typed launch spec carrying Claude's argv, workdir, and artifact paths.
        """
        artifact_paths: tuple[Path, ...] = (settings_path,) if settings_path is not None else ()
        return AgentLaunchSpec(
            provider_id="claude",
            argv=("claude", "--dangerously-skip-permissions"),
            env={},
            workdir=workspace,
            artifact_paths=artifact_paths,
            required_destination_sets=("anthropic-core",),
        )

    def render_artifacts(
        self,
        plan: ArtifactRenderPlan,
        workspace: Path,
    ) -> RenderArtifactsResult:
        """Render governed artifacts into Claude-native surfaces.

        Delegates to :func:`claude_renderer.render_claude_artifacts` and wraps
        the adapter-specific ``RendererResult`` into the provider-neutral
        ``RenderArtifactsResult`` for the launch pipeline.

        Args:
            plan: ArtifactRenderPlan targeting provider ``'claude'``.
            workspace: Root directory for the workspace (project root).

        Returns:
            RenderArtifactsResult with rendered paths, skipped artifacts,
            warnings, and a settings fragment for the caller to merge.

        Raises:
            RendererError: If fail-closed rendering encounters a failure.
        """
        result = render_claude_artifacts(plan, workspace)
        logger.info(
            "Claude renderer: %d paths rendered, %d skipped, %d warnings for bundle '%s'",
            len(result.rendered_paths),
            len(result.skipped_artifacts),
            len(result.warnings),
            plan.bundle_id,
        )
        return RenderArtifactsResult(
            rendered_paths=result.rendered_paths,
            skipped_artifacts=result.skipped_artifacts,
            warnings=result.warnings,
            settings_fragment=result.settings_fragment,
        )
