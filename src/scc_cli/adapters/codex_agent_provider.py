"""Codex adapter for AgentProvider port."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from scc_cli.core.contracts import AgentLaunchSpec, ProviderCapabilityProfile


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
