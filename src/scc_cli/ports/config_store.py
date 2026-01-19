"""Port for accessing configuration data.

Provides typed access to user, organization, and project configuration.
All config is normalized at load time to provide type-safe access.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from scc_cli.ports.config_models import (
    NormalizedOrgConfig,
    NormalizedProjectConfig,
    NormalizedUserConfig,
)


class ConfigStore(Protocol):
    """Protocol for configuration storage and retrieval.

    Implementations should:
    - Load and normalize config at retrieval time
    - Return typed models instead of raw dicts
    - Handle missing/invalid config gracefully
    """

    def load_user_config(self) -> NormalizedUserConfig:
        """Load and normalize user configuration.

        Returns:
            NormalizedUserConfig with typed fields.
        """
        ...

    def load_org_config(self) -> NormalizedOrgConfig | None:
        """Load and normalize cached organization configuration.

        Returns:
            NormalizedOrgConfig if available, None otherwise.
        """
        ...

    def load_project_config(self, workspace_path: Path) -> NormalizedProjectConfig | None:
        """Load and normalize project configuration from workspace.

        Args:
            workspace_path: Path to the workspace containing .scc.yaml.

        Returns:
            NormalizedProjectConfig if available, None otherwise.
        """
        ...

    def get_selected_profile(self) -> str | None:
        """Get the currently selected profile/team name.

        Returns:
            Profile name if selected, None otherwise.
        """
        ...

    def is_standalone_mode(self) -> bool:
        """Check if running in standalone (solo) mode.

        Returns:
            True if standalone mode is enabled.
        """
        ...

    def is_organization_configured(self) -> bool:
        """Check if organization source is configured.

        Returns:
            True if organization source URL is set.
        """
        ...
