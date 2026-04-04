"""Fake AgentProvider for tests."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from scc_cli.core.contracts import AgentLaunchSpec, ProviderCapabilityProfile


class FakeAgentProvider:
    """Simple AgentProvider stub for unit tests."""

    def capability_profile(self) -> ProviderCapabilityProfile:
        return ProviderCapabilityProfile(
            provider_id="fake",
            display_name="Fake provider",
            required_destination_set="fake-core",
            supports_resume=True,
            supports_skills=True,
        )

    def prepare_launch(
        self,
        *,
        config: Mapping[str, Any],
        workspace: Path,
        settings_path: Path | None = None,
    ) -> AgentLaunchSpec:
        artifact_paths = (settings_path,) if settings_path is not None else ()
        return AgentLaunchSpec(
            provider_id="fake",
            argv=("fake-agent",),
            env={"HAS_SETTINGS": "1"} if config else {},
            workdir=workspace,
            artifact_paths=artifact_paths,
            required_destination_sets=("fake-core",),
        )
