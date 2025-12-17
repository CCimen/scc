"""
Team profile management.

Simplified architecture: SCC generates extraKnownMarketplaces + enabledPlugins,
Claude Code handles plugin fetching, installation, and updates natively.
"""

from . import config as config_module


def list_teams(cfg: dict) -> list[dict]:
    """List available teams from configuration."""

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


def get_team_details(team: str, cfg: dict) -> dict | None:
    """
    Get detailed information for a specific team.

    Returns None if team doesn't exist.
    """
    profiles = cfg.get("profiles", {})
    team_info = profiles.get(team)

    if not team_info:
        return None

    marketplace = cfg.get("marketplace", {})

    return {
        "name": team,
        "description": team_info.get("description", ""),
        "plugin": team_info.get("plugin"),
        "marketplace": marketplace.get("name"),
        "marketplace_repo": marketplace.get("repo"),
    }


def get_team_sandbox_settings(team_name: str, cfg: dict | None = None) -> dict:
    """
    Generate sandbox settings for a team profile.

    Returns settings.json content with extraKnownMarketplaces
    and enabledPlugins configured for Claude Code.

    This is the core function of the simplified architecture:
    - SCC injects these settings into the Docker sandbox volume
    - Claude Code sees extraKnownMarketplaces and fetches the marketplace
    - Claude Code installs the specified plugin automatically
    - Teams maintain their plugins in the marketplace repo

    Args:
        team_name: Name of the team profile (e.g., "api-team")
        cfg: Optional config dict. If None, loads from config file.

    Returns:
        Dict with extraKnownMarketplaces and enabledPlugins for settings.json
        Returns empty dict if team has no plugin configured.
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


def get_team_plugin_id(team_name: str, cfg: dict | None = None) -> str | None:
    """
    Get the full plugin ID for a team (e.g., "api-team@sundsvall").

    Returns None if team has no plugin configured.
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


def validate_team_profile(team_name: str, cfg: dict | None = None) -> dict:
    """
    Validate a team profile configuration.

    Returns dict with:
        - valid: bool
        - team: team name
        - plugin: plugin name or None
        - errors: list of validation errors
        - warnings: list of warnings
    """
    if cfg is None:
        cfg = config_module.load_config()

    result = {
        "valid": True,
        "team": team_name,
        "plugin": None,
        "errors": [],
        "warnings": [],
    }

    # Check if team exists
    profiles = cfg.get("profiles", {})
    if team_name not in profiles:
        result["valid"] = False
        result["errors"].append(f"Team '{team_name}' not found in profiles")
        return result

    profile = profiles[team_name]
    result["plugin"] = profile.get("plugin")

    # Check marketplace configuration
    marketplace = cfg.get("marketplace", {})
    if not marketplace.get("repo"):
        result["warnings"].append("No marketplace repo configured")

    # Check if plugin is configured (not required for 'base' profile)
    if not result["plugin"] and team_name != "base":
        result["warnings"].append(
            f"Team '{team_name}' has no plugin configured - using base settings"
        )

    return result
