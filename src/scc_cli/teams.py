"""
Team profile management.

Simplified architecture: SCC generates extraKnownMarketplaces + enabledPlugins,
Claude Code handles plugin fetching, installation, and updates natively.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from . import config as config_module
from .theme import Indicators

if TYPE_CHECKING:
    from .ui.list_screen import ListItem


@dataclass
class TeamInfo:
    """Information about a team profile.

    Provides a typed representation of team data for use in the UI layer.
    Use from_dict() to construct from raw config dicts, and to_list_item()
    to convert for display in pickers.

    Attributes:
        name: Team/profile name (unique identifier).
        description: Human-readable team description.
        plugins: List of plugin identifiers for the team.
        marketplace: Optional marketplace name.
        marketplace_type: Optional marketplace type (e.g., "github").
        marketplace_repo: Optional marketplace repository path.
        credential_status: Credential state ("valid", "expired", "expiring", None).
    """

    name: str
    description: str = ""
    plugins: list[str] = field(default_factory=list)
    marketplace: str | None = None
    marketplace_type: str | None = None
    marketplace_repo: str | None = None
    credential_status: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TeamInfo:
        """Create TeamInfo from a dict representation.

        Args:
            data: Dict with team fields (from list_teams or get_team_details).

        Returns:
            TeamInfo dataclass instance.
        """
        return cls(
            name=data.get("name", "unknown"),
            description=data.get("description", ""),
            plugins=data.get("plugins", []),
            marketplace=data.get("marketplace"),
            marketplace_type=data.get("marketplace_type"),
            marketplace_repo=data.get("marketplace_repo"),
            credential_status=data.get("credential_status"),
        )

    def to_list_item(self, *, current_team: str | None = None) -> ListItem[TeamInfo]:
        """Convert to ListItem for display in pickers.

        Args:
            current_team: Currently selected team name (marked with indicator).

        Returns:
            ListItem suitable for ListScreen display.

        Example:
            >>> team = TeamInfo(name="platform", description="Platform team")
            >>> item = team.to_list_item(current_team="platform")
            >>> item.label
            '✓ platform'
        """
        from .ui.list_screen import ListItem

        is_current = current_team is not None and self.name == current_team

        # Build label with current indicator
        label = f"{Indicators.get('PASS')} {self.name}" if is_current else self.name

        # Check for credential/governance status
        governance_status: str | None = None
        if self.credential_status == "expired":
            governance_status = "blocked"
        elif self.credential_status == "expiring":
            governance_status = "warning"

        # Build description parts
        desc_parts: list[str] = []
        if self.description:
            desc_parts.append(self.description)
        if self.credential_status == "expired":
            desc_parts.append("(credentials expired)")
        elif self.credential_status == "expiring":
            desc_parts.append("(credentials expiring)")

        return ListItem(
            value=self,
            label=label,
            description="  ".join(desc_parts),
            governance_status=governance_status,
        )


def list_teams(
    cfg: dict[str, Any], org_config: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    """List available teams from configuration.

    Args:
        cfg: User config (used for legacy fallback)
        org_config: Organization config with profiles. If provided, uses
            NEW architecture. If None, falls back to legacy behavior.

    Returns:
        List of team dicts with name, description, plugin
    """
    # NEW architecture: use org_config for profiles
    if org_config is not None:
        profiles = org_config.get("profiles", {})
    else:
        # Legacy fallback
        profiles = cfg.get("profiles", {})

    teams = []
    for name, info in profiles.items():
        teams.append(
            {
                "name": name,
                "description": info.get("description", ""),
                "plugins": info.get("additional_plugins", []),
            }
        )

    return teams


def get_team_details(
    team: str, cfg: dict[str, Any], org_config: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    """Get detailed information for a specific team.

    Args:
        team: Team/profile name.
        cfg: User config (used for legacy fallback).
        org_config: Organization config. If provided, uses NEW architecture.

    Returns:
        Team details dict, or None if team doesn't exist.
    """
    # NEW architecture: use org_config for profiles
    if org_config is not None:
        profiles = org_config.get("profiles", {})
        # Marketplaces is a dict where keys are marketplace names
        marketplaces = org_config.get("marketplaces", {})
    else:
        # Legacy fallback
        profiles = cfg.get("profiles", {})
        marketplaces = {}

    team_info = profiles.get(team)
    if not team_info:
        return None

    # Get plugins from new schema (additional_plugins is a list)
    plugins = team_info.get("additional_plugins", [])

    # Get marketplace info
    if org_config is not None:
        # NEW: look up marketplace by name from org_config
        # Marketplace name can be explicit in profile, or inferred from plugins
        marketplace_name = team_info.get("marketplace")
        if marketplace_name and marketplace_name in marketplaces:
            marketplace_info = marketplaces[marketplace_name]
            # New schema: {"source": "github", "owner": "...", "repo": "..."}
            return {
                "name": team,
                "description": team_info.get("description", ""),
                "plugins": plugins,
                "marketplace": marketplace_name,
                "marketplace_type": marketplace_info.get("source"),
                "marketplace_repo": marketplace_info.get("repo"),
            }
        else:
            # No explicit marketplace - infer from first plugin if available
            first_marketplace = None
            if plugins:
                for plugin_id in plugins:
                    if "@" in plugin_id:
                        first_marketplace = plugin_id.split("@")[1]
                        break
            return {
                "name": team,
                "description": team_info.get("description", ""),
                "plugins": plugins,
                "marketplace": first_marketplace,
                "marketplace_type": marketplaces.get(first_marketplace, {}).get("source")
                if first_marketplace
                else None,
                "marketplace_repo": marketplaces.get(first_marketplace, {}).get("repo")
                if first_marketplace
                else None,
            }
    else:
        # Legacy: single marketplace in cfg
        marketplace = cfg.get("marketplace", {})
        return {
            "name": team,
            "description": team_info.get("description", ""),
            "plugins": plugins,  # List of plugin identifiers
            "marketplace": marketplace.get("name"),
            "marketplace_repo": marketplace.get("repo"),
        }


def get_team_sandbox_settings(team_name: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Generate sandbox settings for a team profile.

    Return settings.json content with extraKnownMarketplaces
    and enabledPlugins configured for Claude Code.

    This is the core function of the simplified architecture:
    - SCC injects these settings into the Docker sandbox volume
    - Claude Code sees extraKnownMarketplaces and fetches the marketplace
    - Claude Code installs the specified plugins automatically
    - Teams maintain their plugins in the marketplace repo

    Args:
        team_name: Name of the team profile (e.g., "api-team").
        cfg: Optional config dict. If None, load from config file.

    Returns:
        Dict with extraKnownMarketplaces and enabledPlugins for settings.json.
        Return empty dict if team has no plugins configured.
    """
    if cfg is None:
        cfg = config_module.load_config()

    profile = cfg.get("profiles", {}).get(team_name, {})
    plugins = profile.get("additional_plugins", [])

    # No plugins configured for this profile
    if not plugins:
        return {}

    # Get marketplace config for building extraKnownMarketplaces
    marketplace = cfg.get("marketplace", {})
    marketplace_name = marketplace.get("name", "sundsvall")
    marketplace_repo = marketplace.get("repo", "sundsvall/claude-plugins-marketplace")

    # Generate settings that Claude Code understands
    return {
        "extraKnownMarketplaces": {
            marketplace_name: {
                "source": {
                    "source": "github",
                    "repo": marketplace_repo,
                }
            }
        },
        "enabledPlugins": plugins,
    }


def get_team_plugin_id(team_name: str, cfg: dict[str, Any] | None = None) -> str | None:
    """Get the first plugin ID for a team (e.g., "api-team@sundsvall").

    For teams with multiple plugins, returns the first one.
    Use get_team_plugins() to get all plugins.

    Args:
        team_name: Name of the team profile.
        cfg: Optional config dict. If None, load from config file.

    Returns:
        First plugin ID string, or None if team has no plugins configured.
    """
    if cfg is None:
        cfg = config_module.load_config()

    profile = cfg.get("profiles", {}).get(team_name, {})
    plugins: list[str] = profile.get("additional_plugins", [])

    if not plugins:
        return None

    return plugins[0]


def get_team_plugins(team_name: str, cfg: dict[str, Any] | None = None) -> list[str]:
    """Get all plugin IDs for a team.

    Args:
        team_name: Name of the team profile.
        cfg: Optional config dict. If None, load from config file.

    Returns:
        List of plugin ID strings, or empty list if team has no plugins.
    """
    if cfg is None:
        cfg = config_module.load_config()

    profile = cfg.get("profiles", {}).get(team_name, {})
    plugins: list[str] = profile.get("additional_plugins", [])
    return plugins


def validate_team_profile(
    team_name: str,
    cfg: dict[str, Any] | None = None,
    org_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a team profile configuration.

    Args:
        team_name: Name of the team/profile to validate.
        cfg: User config (for marketplace info when org_config not provided).
        org_config: Organization config with profiles and marketplaces.
            If provided, uses org_config for profiles. If None, reads
            profiles from cfg.

    Returns:
        Dict with keys: valid (bool), team (str), plugins (list of str),
        errors (list of str), warnings (list of str).
    """
    if cfg is None:
        cfg = config_module.load_config()

    result: dict[str, Any] = {
        "valid": True,
        "team": team_name,
        "plugins": [],
        "errors": [],
        "warnings": [],
    }

    # Use org_config for profiles if provided, otherwise use cfg
    if org_config is not None:
        profiles = org_config.get("profiles", {})
        marketplaces = org_config.get("marketplaces", {})
    else:
        profiles = cfg.get("profiles", {})
        marketplaces = {}

    # Check if team exists
    if team_name not in profiles:
        result["valid"] = False
        result["errors"].append(f"Team '{team_name}' not found in profiles")
        return result

    profile = profiles[team_name]
    result["plugins"] = profile.get("additional_plugins", [])

    # Check marketplace configuration
    if org_config is not None:
        # Validate that plugins reference known marketplaces
        for plugin_id in result["plugins"]:
            if "@" in plugin_id:
                marketplace_name = plugin_id.split("@")[1]
                if marketplace_name not in marketplaces:
                    result["warnings"].append(
                        f"Marketplace '{marketplace_name}' for plugin '{plugin_id}' not found"
                    )
    else:
        # Check single marketplace config
        marketplace = cfg.get("marketplace", {})
        if not marketplace.get("repo"):
            result["warnings"].append("No marketplace repo configured")

    # Check if plugins are configured (not required for 'base' or 'default' profile)
    if not result["plugins"] and team_name not in ("base", "default"):
        result["warnings"].append(
            f"Team '{team_name}' has no plugins configured - using base settings"
        )

    return result
