"""Provider-neutral launch preparation contract."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from scc_cli.core.contracts import (
    AgentLaunchSpec,
    AuthReadiness,
    ProviderCapabilityProfile,
    RenderArtifactsResult,
)
from scc_cli.core.governed_artifacts import ArtifactRenderPlan


class AgentProvider(Protocol):
    """Prepare provider-owned launch plans for the runtime layer.

    Implementations own provider-specific auth, artifacts, argv/env generation,
    and provider-core destination requirements while exposing a provider-neutral
    contract to the rest of the application.
    """

    def capability_profile(self) -> ProviderCapabilityProfile:
        """Return the provider capability profile used by planning and diagnostics."""
        ...

    def prepare_launch(
        self,
        *,
        config: Mapping[str, Any],
        workspace: Path,
        settings_path: Path | None = None,
    ) -> AgentLaunchSpec:
        """Build a provider-owned launch specification for one workspace."""
        ...

    def auth_check(self) -> AuthReadiness:
        """Check whether provider auth credentials are present and usable.

        Each adapter owns the definition of "ready": file existence, non-empty
        content, parseable format. Wording must be truthful — "auth cache
        present" not "logged in" (we check file presence, not token validity).

        Returns:
            AuthReadiness with status, mechanism, and user-facing guidance.
        """
        ...

    def render_artifacts(
        self,
        plan: ArtifactRenderPlan,
        workspace: Path,
    ) -> RenderArtifactsResult:
        """Render governed artifacts into provider-native surfaces.

        Consumes a provider-neutral ``ArtifactRenderPlan`` (produced by
        ``core.bundle_resolver.resolve_render_plan``) and projects it into
        provider-specific files, settings fragments, and config surfaces.

        The returned ``RenderArtifactsResult`` carries rendered paths,
        skipped artifacts, warnings, and a settings fragment for the
        launch pipeline to merge into the active config surface.

        Implementations MUST be deterministic and idempotent — the same
        plan + workspace always produce the same output.

        Raises:
            RendererError: If fail-closed rendering encounters a
                materialization error, merge conflict, or invalid reference.
        """
        ...
