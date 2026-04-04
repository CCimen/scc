"""Claude Code adapter for AgentProvider port."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from scc_cli.core.contracts import AgentLaunchSpec, ProviderCapabilityProfile


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
