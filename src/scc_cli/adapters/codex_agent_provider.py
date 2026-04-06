"""Codex adapter for AgentProvider port."""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from scc_cli.adapters.codex_auth import run_codex_browser_auth
from scc_cli.adapters.codex_launch import build_codex_container_argv
from scc_cli.adapters.codex_renderer import render_codex_artifacts
from scc_cli.core.contracts import (
    AgentLaunchSpec,
    AuthReadiness,
    ProviderCapabilityProfile,
    RenderArtifactsResult,
)
from scc_cli.core.errors import ProviderNotReadyError
from scc_cli.core.governed_artifacts import ArtifactRenderPlan

logger = logging.getLogger(__name__)

_CODEX_AUTH_FILE = "auth.json"
_CODEX_DATA_VOLUME = "docker-codex-sandbox-data"


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
            supports_skills=True,
            supports_native_integrations=True,
        )

    def auth_check(self) -> AuthReadiness:
        """Check whether Codex auth credentials are cached in the data volume.

        Probes the Docker named volume for ``auth.json``.  Validates that the
        file exists, is non-empty, and contains parseable JSON.  Wording is
        truthful: "auth cache present" — we verify the file, not whether the
        token is actually valid or unexpired.
        """
        volume = _CODEX_DATA_VOLUME
        auth_file = _CODEX_AUTH_FILE
        mechanism = "auth_json_file"

        # Step 1: volume existence
        try:
            vol_result = subprocess.run(
                ["docker", "volume", "inspect", volume],
                capture_output=True,
                timeout=10,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return AuthReadiness(
                status="missing",
                mechanism=mechanism,
                guidance=f"Cannot reach Docker to check volume '{volume}'",
            )

        if vol_result.returncode != 0:
            return AuthReadiness(
                status="missing",
                mechanism=mechanism,
                guidance="Run 'scc start --provider codex' to perform initial auth setup",
            )

        # Step 2: read file content from volume
        try:
            file_result = subprocess.run(
                [
                    "docker", "run", "--rm",
                    "-v", f"{volume}:/check",
                    "alpine",
                    "cat", f"/check/{auth_file}",
                ],
                capture_output=True,
                timeout=30,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return AuthReadiness(
                status="missing",
                mechanism=mechanism,
                guidance="Timed out reading auth file from volume",
            )

        if file_result.returncode != 0:
            return AuthReadiness(
                status="missing",
                mechanism=mechanism,
                guidance=(
                    f"Auth file '{auth_file}' not found in volume '{volume}'. "
                    "Run 'scc start --provider codex' to authenticate."
                ),
            )

        # Step 3: non-empty + parseable JSON
        content = file_result.stdout.strip()
        if not content:
            return AuthReadiness(
                status="missing",
                mechanism=mechanism,
                guidance=(
                    f"Auth file '{auth_file}' is empty. "
                    "Run 'scc start --provider codex' to authenticate."
                ),
            )

        try:
            json.loads(content)
        except (json.JSONDecodeError, ValueError):
            return AuthReadiness(
                status="missing",
                mechanism=mechanism,
                guidance=(
                    f"Auth file '{auth_file}' contains invalid JSON. "
                    "Run 'scc start --provider codex' to re-authenticate."
                ),
            )

        return AuthReadiness(
            status="present",
            mechanism=mechanism,
            guidance="Codex auth cache present — no action needed",
        )

    def bootstrap_auth(self) -> None:
        """Establish Codex auth using the normal browser flow on the host."""
        return_code = run_codex_browser_auth()
        readiness = self.auth_check()
        if readiness.status == "present":
            return
        if return_code != 0:
            raise ProviderNotReadyError(
                provider_id="codex",
                user_message=(
                    "Codex browser sign-in did not complete successfully."
                ),
                suggested_action=(
                    "Retry the sign-in flow. If browser login is unavailable, use the "
                    "device-code fallback instead."
                ),
            )
        raise ProviderNotReadyError(
            provider_id="codex",
            user_message="Codex sign-in finished, but no reusable auth cache was written.",
            suggested_action=(
                "Retry the sign-in flow. If browser login is unavailable, use the "
                "device-code fallback instead."
            ),
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
            argv=build_codex_container_argv(),
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
