"""
Team profile management.

Simplified architecture: SCC generates extraKnownMarketplaces + enabledPlugins,
Claude Code handles plugin fetching, installation, and updates natively.
"""

from __future__ import annotations

from dataclasses import dataclass
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
        plugin: Optional plugin name for the team.
        marketplace: Optional marketplace name.
        marketplace_type: Optional marketplace type (e.g., "github").
        marketplace_repo: Optional marketplace repository path.
        credential_status: Credential state ("valid", "expired", "expiring", None).
    """

    name: str
    description: str = ""
    plugin: str | None = None
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
            plugin=data.get("plugin"),
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
                "plugin": info.get("plugin"),
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
        marketplaces = org_config.get("marketplaces", [])
    else:
        # Legacy fallback
        profiles = cfg.get("profiles", {})
        marketplaces = []

    team_info = profiles.get(team)
    if not team_info:
        return None

    # Get marketplace info
    if org_config is not None:
        # NEW: look up marketplace by name from org_config
        marketplace_name = team_info.get("marketplace")
        marketplace: dict[str, Any] = next(
            (m for m in marketplaces if m.get("name") == marketplace_name),
            {},
        )
        return {
            "name": team,
            "description": team_info.get("description", ""),
            "plugin": team_info.get("plugin"),
            "marketplace": marketplace.get("name"),
            "marketplace_type": marketplace.get("type"),
            "marketplace_repo": marketplace.get("repo"),
        }
    else:
        # Legacy: single marketplace in cfg
        marketplace = cfg.get("marketplace", {})
        return {
            "name": team,
            "description": team_info.get("description", ""),
            "plugin": team_info.get("plugin"),
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
    - Claude Code installs the specified plugin automatically
    - Teams maintain their plugins in the marketplace repo

    Args:
        team_name: Name of the team profile (e.g., "api-team").
        cfg: Optional config dict. If None, load from config file.

    Returns:
        Dict with extraKnownMarketplaces and enabledPlugins for settings.json.
        Return empty dict if team has no plugin configured.
    """
    if cfg is None:
        cfg = config_module.load_config()

    marketplace = cfg.get("marketplace", {})
    marketplace_name = marketplace.get("name", "sundsvall")
    marketplace_repo = marketplace.get("repo", "sundsvall/claude-plugins-marketplace")

    profile = cfg.get("profiles", {}).get(team_name, {})
    plugin_name = profile.get("plugin")

    # No plugin configured for this profile
    if not plugin_name:
        return {}

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
        "enabledPlugins": [f"{plugin_name}@{marketplace_name}"],
    }


def get_team_plugin_id(team_name: str, cfg: dict[str, Any] | None = None) -> str | None:
    """Get the full plugin ID for a team (e.g., "api-team@sundsvall").

    Args:
        team_name: Name of the team profile.
        cfg: Optional config dict. If None, load from config file.

    Returns:
        Full plugin ID string, or None if team has no plugin configured.
    """
    if cfg is None:
        cfg = config_module.load_config()

    marketplace = cfg.get("marketplace", {})
    marketplace_name = marketplace.get("name", "sundsvall")

    profile = cfg.get("profiles", {}).get(team_name, {})
    plugin_name = profile.get("plugin")

    if not plugin_name:
        return None

    return f"{plugin_name}@{marketplace_name}"


def validate_team_profile(
    team_name: str,
    cfg: dict[str, Any] | None = None,
    org_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a team profile configuration.

    Args:
        team_name: Name of the team/profile to validate.
        cfg: User config (deprecated, kept for backward compatibility).
        org_config: Organization config with profiles and marketplaces.
            If provided, use NEW architecture. If None, fall back to
            legacy behavior (reading profiles from cfg).

    Returns:
        Dict with keys: valid (bool), team (str), plugin (str or None),
        errors (list of str), warnings (list of str).
    """
    if cfg is None:
        cfg = config_module.load_config()

    result: dict[str, Any] = {
        "valid": True,
        "team": team_name,
        "plugin": None,
        "errors": [],
        "warnings": [],
    }

    # NEW architecture: use org_config for profiles
    if org_config is not None:
        profiles = org_config.get("profiles", {})
        marketplaces = org_config.get("marketplaces", [])
    else:
        # Legacy fallback: read from user config (deprecated)
        profiles = cfg.get("profiles", {})
        marketplaces = []

    # Check if team exists
    if team_name not in profiles:
        result["valid"] = False
        result["errors"].append(f"Team '{team_name}' not found in profiles")
        return result

    profile = profiles[team_name]
    result["plugin"] = profile.get("plugin")

    # Check marketplace configuration (NEW architecture)
    if org_config is not None:
        marketplace_name = profile.get("marketplace")
        if marketplace_name:
            # Find the marketplace in org_config
            marketplace_found = any(m.get("name") == marketplace_name for m in marketplaces)
            if not marketplace_found:
                result["warnings"].append(f"Marketplace '{marketplace_name}' not found")
    else:
        # Legacy: check single marketplace
        marketplace = cfg.get("marketplace", {})
        if not marketplace.get("repo"):
            result["warnings"].append("No marketplace repo configured")

    # Check if plugin is configured (not required for 'base' profile)
    if not result["plugin"] and team_name != "base":
        result["warnings"].append(
            f"Team '{team_name}' has no plugin configured - using base settings"
        )

    return result
