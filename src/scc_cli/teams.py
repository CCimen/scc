"""Team profile helpers for organization configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

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


def list_teams(org_config: dict[str, Any] | None) -> list[dict[str, Any]]:
    """List available teams from organization configuration."""
    if not org_config:
        return []

    profiles = org_config.get("profiles", {})
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


def get_team_details(team: str, org_config: dict[str, Any] | None) -> dict[str, Any] | None:
    """Get detailed information for a specific team."""
    if not org_config:
        return None

    profiles = org_config.get("profiles", {})
    marketplaces = org_config.get("marketplaces", {})

    team_info = profiles.get(team)
    if not team_info:
        return None

    plugins = team_info.get("additional_plugins", [])

    marketplace_names = sorted(
        {plugin_id.split("@")[1] for plugin_id in plugins if "@" in plugin_id}
    )
    marketplace_label: str | None = None
    marketplace_type: str | None = None
    marketplace_repo: str | None = None

    if len(marketplace_names) == 1:
        marketplace_label = marketplace_names[0]
        marketplace_info = marketplaces.get(marketplace_label, {})
        marketplace_type = marketplace_info.get("source")
        if marketplace_type == "github":
            owner = marketplace_info.get("owner")
            repo = marketplace_info.get("repo")
            if owner and repo:
                marketplace_repo = f"{owner}/{repo}"
            else:
                marketplace_repo = repo
        elif marketplace_type == "git":
            marketplace_repo = marketplace_info.get("url")
        elif marketplace_type == "url":
            marketplace_repo = marketplace_info.get("url")
        elif marketplace_type == "directory":
            marketplace_repo = marketplace_info.get("path")
        else:
            marketplace_repo = marketplace_info.get("repo")
    elif marketplace_names:
        marketplace_label = ", ".join(marketplace_names)

    return {
        "name": team,
        "description": team_info.get("description", ""),
        "plugins": plugins,
        "marketplace": marketplace_label,
        "marketplace_type": marketplace_type,
        "marketplace_repo": marketplace_repo,
    }


def validate_team_profile(
    team_name: str,
    org_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a team profile configuration.

    Returns:
        Dict with keys: valid (bool), team (str), plugins (list of str),
        errors (list of str), warnings (list of str).
    """
    result: dict[str, Any] = {
        "valid": True,
        "team": team_name,
        "plugins": [],
        "errors": [],
        "warnings": [],
    }

    if not org_config:
        result["valid"] = False
        result["errors"].append("No organization configuration found")
        return result

    profiles = org_config.get("profiles", {})
    marketplaces = org_config.get("marketplaces", {})

    if team_name not in profiles:
        result["valid"] = False
        result["errors"].append(f"Team '{team_name}' not found in profiles")
        return result

    profile = profiles[team_name]
    result["plugins"] = profile.get("additional_plugins", [])

    for plugin_id in result["plugins"]:
        if "@" in plugin_id:
            marketplace_name = plugin_id.split("@")[1]
            if marketplace_name not in marketplaces:
                result["warnings"].append(
                    f"Marketplace '{marketplace_name}' for plugin '{plugin_id}' not found"
                )

    if not result["plugins"] and team_name not in ("base", "default"):
        result["warnings"].append(
            f"Team '{team_name}' has no plugins configured - using base settings"
        )

    return result
