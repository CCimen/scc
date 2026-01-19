"""Local config store adapter - implements ConfigStore using local filesystem."""

from __future__ import annotations

from pathlib import Path

from scc_cli import config as config_module
from scc_cli.adapters.config_normalizer import (
    normalize_org_config,
    normalize_project_config,
    normalize_user_config,
)
from scc_cli.ports.config_models import (
    NormalizedOrgConfig,
    NormalizedProjectConfig,
    NormalizedUserConfig,
)
from scc_cli.ports.config_store import ConfigStore


class LocalConfigStore:
    """Config store implementation using local filesystem.

    Wraps the existing config module and normalizes results to typed models.
    """

    def load_user_config(self) -> NormalizedUserConfig:
        """Load and normalize user configuration."""
        raw = config_module.load_user_config()
        return normalize_user_config(raw)

    def load_org_config(self) -> NormalizedOrgConfig | None:
        """Load and normalize cached organization configuration."""
        raw = config_module.load_cached_org_config()
        if raw is None:
            return None
        return normalize_org_config(raw)

    def load_project_config(self, workspace_path: Path) -> NormalizedProjectConfig | None:
        """Load and normalize project configuration from workspace."""
        raw = config_module.read_project_config(workspace_path)
        return normalize_project_config(raw)

    def get_selected_profile(self) -> str | None:
        """Get the currently selected profile/team name."""
        return config_module.get_selected_profile()

    def is_standalone_mode(self) -> bool:
        """Check if running in standalone (solo) mode."""
        return config_module.is_standalone_mode()

    def is_organization_configured(self) -> bool:
        """Check if organization source is configured."""
        return config_module.is_organization_configured()


def _assert_implements_protocol() -> None:
    """Type check that LocalConfigStore implements ConfigStore."""
    _: ConfigStore = LocalConfigStore()
