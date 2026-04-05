"""Fake AgentProvider for tests."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from scc_cli.core.contracts import (
    AgentLaunchSpec,
    AuthReadiness,
    ProviderCapabilityProfile,
    RenderArtifactsResult,
)
from scc_cli.core.governed_artifacts import ArtifactRenderPlan


class FakeAgentProvider:
    """Simple AgentProvider stub for unit tests."""

    def __init__(self) -> None:
        self.render_artifacts_calls: list[tuple[ArtifactRenderPlan, Path]] = []

    def capability_profile(self) -> ProviderCapabilityProfile:
        return ProviderCapabilityProfile(
            provider_id="fake",
            display_name="Fake provider",
            required_destination_set="fake-core",
            supports_resume=True,
            supports_skills=True,
        )

    def auth_check(self) -> AuthReadiness:
        return AuthReadiness(
            status="present",
            mechanism="fake",
            guidance="Fake auth always present",
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

    def render_artifacts(
        self,
        plan: ArtifactRenderPlan,
        workspace: Path,
    ) -> RenderArtifactsResult:
        self.render_artifacts_calls.append((plan, workspace))
        return RenderArtifactsResult(
            rendered_paths=(),
            skipped_artifacts=plan.skipped,
            warnings=(),
            settings_fragment={},
        )
