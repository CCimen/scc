"""Codex adapter for AgentProvider port."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from scc_cli.adapters.codex_renderer import render_codex_artifacts
from scc_cli.core.contracts import AgentLaunchSpec, ProviderCapabilityProfile, RenderArtifactsResult
from scc_cli.core.governed_artifacts import ArtifactRenderPlan

logger = logging.getLogger(__name__)


class CodexAgentProvider:
    """AgentProvider implementation for OpenAI Codex.

    Translates provider config and workspace context into a typed AgentLaunchSpec
    that the runtime layer can consume without importing Codex internals directly.
    """

    def capability_profile(self) -> ProviderCapabilityProfile:
        return ProviderCapabilityProfile(
            provider_id="codex",
            display_name="Codex",
            required_destination_set="openai-core",
            supports_resume=False,
            supports_skills=False,
            supports_native_integrations=False,
        )

    def prepare_launch(
        self,
        *,
        config: Mapping[str, Any],
        workspace: Path,
        settings_path: Path | None = None,
    ) -> AgentLaunchSpec:
        """Build a Codex-owned launch specification for one workspace.

        Args:
            config: Rendered agent settings payload. Consumed by the settings
                    artifact; not injected as env vars.
            workspace: Launch working directory.
            settings_path: Container path for a rendered settings artifact,
                           if any was built by the sync path.

        Returns:
            Typed launch spec carrying Codex's argv, workdir, and artifact paths.
        """
        artifact_paths: tuple[Path, ...] = (settings_path,) if settings_path is not None else ()
        return AgentLaunchSpec(
            provider_id="codex",
            argv=("codex",),
            env={},
            workdir=workspace,
            artifact_paths=artifact_paths,
            required_destination_sets=("openai-core",),
        )

    def render_artifacts(
        self,
        plan: ArtifactRenderPlan,
        workspace: Path,
    ) -> RenderArtifactsResult:
        """Render governed artifacts into Codex-native surfaces.

        Delegates to :func:`codex_renderer.render_codex_artifacts` and wraps
        the adapter-specific ``RendererResult`` into the provider-neutral
        ``RenderArtifactsResult`` for the launch pipeline.

        Args:
            plan: ArtifactRenderPlan targeting provider ``'codex'``.
            workspace: Root directory for the workspace (project root).

        Returns:
            RenderArtifactsResult with rendered paths, skipped artifacts,
            warnings, and a settings fragment (mcp_fragment from Codex
            renderer mapped to settings_fragment in the unified result).

        Raises:
            RendererError: If fail-closed rendering encounters a failure.
        """
        result = render_codex_artifacts(plan, workspace)
        logger.info(
            "Codex renderer: %d paths rendered, %d skipped, %d warnings for bundle '%s'",
            len(result.rendered_paths),
            len(result.skipped_artifacts),
            len(result.warnings),
            plan.bundle_id,
        )
        return RenderArtifactsResult(
            rendered_paths=result.rendered_paths,
            skipped_artifacts=result.skipped_artifacts,
            warnings=result.warnings,
            # Codex renderer returns mcp_fragment; map to unified settings_fragment
            settings_fragment=result.mcp_fragment,
        )
