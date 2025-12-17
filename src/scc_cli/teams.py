"""
Team profile management.

Simplified architecture: SCC generates extraKnownMarketplaces + enabledPlugins,
Claude Code handles plugin fetching, installation, and updates natively.
"""

from . import config as config_module


def list_teams(cfg: dict, org_config: dict | None = None) -> list[dict]:
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


def get_team_details(team: str, cfg: dict, org_config: dict | None = None) -> dict | None:
    """
    Get detailed information for a specific team.

    Args:
        team: Team/profile name
        cfg: User config (used for legacy fallback)
        org_config: Organization config. If provided, uses NEW architecture.

    Returns None if team doesn't exist.
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
        marketplace = next(
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


def validate_team_profile(
    team_name: str,
    cfg: dict | None = None,
    org_config: dict | None = None,
) -> dict:
    """
    Validate a team profile configuration.

    Args:
        team_name: Name of the team/profile to validate
        cfg: User config (deprecated, kept for backward compatibility)
        org_config: Organization config with profiles and marketplaces.
            If provided, uses NEW architecture. If None, falls back to
            legacy behavior (reading profiles from cfg).

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
