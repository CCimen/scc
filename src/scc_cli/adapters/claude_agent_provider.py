"""Claude Code adapter for AgentProvider port."""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from scc_cli.adapters.claude_auth import run_claude_browser_auth
from scc_cli.adapters.claude_renderer import render_claude_artifacts
from scc_cli.core.contracts import (
    AgentLaunchSpec,
    AuthReadiness,
    ProviderCapabilityProfile,
    RenderArtifactsResult,
)
from scc_cli.core.errors import ProviderNotReadyError
from scc_cli.core.governed_artifacts import ArtifactRenderPlan

logger = logging.getLogger(__name__)

_CLAUDE_OAUTH_FILE = ".credentials.json"
_CLAUDE_HOST_AUTH_FILE = ".claude.json"
_CLAUDE_DATA_VOLUME = "docker-claude-sandbox-data"


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

    def auth_check(self) -> AuthReadiness:
        """Check whether Claude auth credentials are cached in the data volume."""
        volume = _CLAUDE_DATA_VOLUME
        mechanism = "oauth_file"

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
                guidance="Run 'scc start --provider claude' to perform initial auth setup",
            )

        oauth_state = _read_volume_json(volume, _CLAUDE_OAUTH_FILE)
        if oauth_state == "present":
            return AuthReadiness(
                status="present",
                mechanism=mechanism,
                guidance="Claude auth cache present — no action needed",
            )
        if oauth_state == "invalid":
            return AuthReadiness(
                status="missing",
                mechanism=mechanism,
                guidance=(
                    f"Auth file '{_CLAUDE_OAUTH_FILE}' contains invalid JSON. "
                    "Run 'scc start --provider claude' to re-authenticate."
                ),
            )

        host_state = _read_volume_json(volume, _CLAUDE_HOST_AUTH_FILE)
        if host_state == "present":
            return AuthReadiness(
                status="present",
                mechanism=mechanism,
                guidance="Claude auth cache present — no action needed",
            )
        if host_state == "invalid":
            return AuthReadiness(
                status="missing",
                mechanism=mechanism,
                guidance=(
                    f"Auth file '{_CLAUDE_HOST_AUTH_FILE}' contains invalid JSON. "
                    "Run 'scc start --provider claude' to re-authenticate."
                ),
            )

        return AuthReadiness(
            status="missing",
            mechanism=mechanism,
            guidance=(
                f"Auth files '{_CLAUDE_OAUTH_FILE}' and '{_CLAUDE_HOST_AUTH_FILE}' "
                f"not found in volume '{volume}'. Run 'scc start --provider claude' "
                "to authenticate."
            ),
        )

    def bootstrap_auth(self) -> None:
        """Establish Claude auth using the provider's own browser flow."""
        return_code = run_claude_browser_auth()
        readiness = self.auth_check()
        if readiness.status == "present":
            return
        if return_code != 0:
            raise ProviderNotReadyError(
                provider_id="claude",
                user_message="Claude browser sign-in did not complete successfully.",
                suggested_action="Retry the sign-in flow and complete the provider login.",
            )
        raise ProviderNotReadyError(
            provider_id="claude",
            user_message="Claude sign-in finished, but no reusable auth cache was written.",
            suggested_action="Retry the sign-in flow and confirm the provider login completed.",
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


def _read_volume_json(volume: str, auth_file: str) -> str:
    """Return ``present``, ``missing``, or ``invalid`` for one Claude auth file."""
    try:
        file_result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{volume}:/check",
                "alpine",
                "cat",
                f"/check/{auth_file}",
            ],
            capture_output=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return "missing"

    if file_result.returncode != 0:
        return "missing"

    content = file_result.stdout.strip()
    if not content:
        return "missing"

    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return "invalid"

    if auth_file == _CLAUDE_HOST_AUTH_FILE:
        return "present" if isinstance(parsed, dict) and parsed.get("oauthAccount") else "missing"
    return "present" if parsed else "missing"
