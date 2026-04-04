"""Provider-neutral launch preparation contract."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from scc_cli.core.contracts import AgentLaunchSpec, ProviderCapabilityProfile


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
