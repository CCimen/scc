"""
Profile resolution and marketplace URL logic.

Renamed from teams.py to better reflect profile resolution responsibilities.
Supports new multi-marketplace architecture while maintaining backward compatibility
with legacy single-marketplace config format.

HTTPS-only enforcement: All marketplace URLs must use HTTPS protocol.
SSH and HTTP URLs are rejected for security.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse, urlunparse

if TYPE_CHECKING:
    pass

# Import config module for backward compatibility functions
from . import config as config_module

# ═══════════════════════════════════════════════════════════════════════════════
# Core Profile Resolution Functions (New Architecture)
# ═══════════════════════════════════════════════════════════════════════════════


def list_profiles(org_config: dict) -> list[dict]:
    """
    List all available profiles from org config.

    Returns list of profile dicts with name, description, plugin, and marketplace.
    """
    profiles = org_config.get("profiles", {})
    result = []

    for name, info in profiles.items():
        result.append(
            {
                "name": name,
                "description": info.get("description", ""),
                "plugin": info.get("plugin"),
                "marketplace": info.get("marketplace"),
            }
        )

    return result


def resolve_profile(org_config: dict, profile_name: str) -> dict:
    """
    Resolve profile by name, raise ValueError if not found.

    Returns profile dict with name and all profile fields.
    """
    profiles = org_config.get("profiles", {})

    if profile_name not in profiles:
        available = ", ".join(sorted(profiles.keys())) or "(none)"
        raise ValueError(
            f"Profile '{profile_name}' not found. Available: {available}"
        )

    profile_info = profiles[profile_name]
    return {"name": profile_name, **profile_info}


def resolve_marketplace(org_config: dict, profile: dict) -> dict:
    """
    Resolve marketplace for a profile.

    Looks up marketplace by name from the marketplaces array.
    Raises ValueError if marketplace not found.
    """
    marketplace_name = profile.get("marketplace")

    # Support both new marketplaces[] array and legacy marketplace{} object
    marketplaces = org_config.get("marketplaces", [])

    for m in marketplaces:
        if m.get("name") == marketplace_name:
            return m

    raise ValueError(
        f"Marketplace '{marketplace_name}' not found for profile '{profile.get('name')}'"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Marketplace URL Resolution (HTTPS-only enforcement)
# ═══════════════════════════════════════════════════════════════════════════════


def _normalize_repo_path(repo: str) -> str:
    """
    Normalize repo path: strip whitespace, leading slashes, .git suffix.
    """
    repo = repo.strip().lstrip("/")
    if repo.endswith(".git"):
        repo = repo[:-4]
    return repo


def get_marketplace_url(marketplace: dict) -> str:
    """
    Resolve marketplace to HTTPS URL.

    SECURITY: Rejects SSH URLs (git@, ssh://) and HTTP URLs.
    Only HTTPS is allowed for marketplace access.

    URL Resolution Logic:
    1. If 'url' is provided, validate and normalize it
    2. Otherwise, construct from 'host' + 'repo'
    3. For github/gitlab types, use default hosts if not specified

    Args:
        marketplace: Marketplace config dict with type, url/host, repo

    Returns:
        Normalized HTTPS URL string

    Raises:
        ValueError: For SSH URLs, HTTP URLs, unsupported schemes, or missing config
    """
    # Check for direct URL first
    if raw := marketplace.get("url"):
        raw = raw.strip()

        # Reject SSH URLs early (git@ format)
        if raw.startswith("git@"):
            raise ValueError(f"SSH URL not supported: {raw}")

        # Reject ssh:// protocol
        if raw.startswith("ssh://"):
            raise ValueError(f"SSH URL not supported: {raw}")

        parsed = urlparse(raw)

        # HTTPS only - reject http:// for security
        if parsed.scheme == "http":
            raise ValueError(f"HTTP not allowed (use HTTPS): {raw}")

        if parsed.scheme != "https":
            raise ValueError(f"Unsupported URL scheme: {parsed.scheme!r}")

        # Normalize: remove trailing slash, drop fragments
        normalized_path = parsed.path.rstrip("/")
        normalized = parsed._replace(path=normalized_path, fragment="")
        return urlunparse(normalized)

    # No URL provided - construct from host + repo
    host = (marketplace.get("host") or "").strip()

    if not host:
        # Use default hosts for known types
        defaults = {"github": "github.com", "gitlab": "gitlab.com"}
        host = defaults.get(marketplace.get("type") or "")

        if not host:
            raise ValueError(
                f"Marketplace type '{marketplace.get('type')}' requires 'url' or 'host'"
            )

    # Reject host with path components (ambiguous config)
    if "/" in host:
        raise ValueError(f"'host' must not include path: {host!r}")

    # Get and normalize repo path
    repo = marketplace.get("repo", "")
    repo = _normalize_repo_path(repo)

    return f"https://{host}/{repo}"


# ═══════════════════════════════════════════════════════════════════════════════
# Backward Compatibility Functions (Legacy API from teams.py)
# ═══════════════════════════════════════════════════════════════════════════════


def list_teams(cfg: dict) -> list[dict]:
    """
    List available teams from configuration.

    BACKWARD COMPATIBILITY: Wraps list_profiles() for legacy code.
    """
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

    BACKWARD COMPATIBILITY: Supports legacy single marketplace format.
    Returns None if team doesn't exist.
    """
    profiles = cfg.get("profiles", {})
    team_info = profiles.get(team)

    if not team_info:
        return None

    # Support legacy single marketplace format
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

    BACKWARD COMPATIBILITY: Supports legacy single marketplace format.

    Returns settings.json content with extraKnownMarketplaces
    and enabledPlugins configured for Claude Code.
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

    BACKWARD COMPATIBILITY: Supports legacy single marketplace format.
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

    BACKWARD COMPATIBILITY: Supports legacy single marketplace format.

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
