"""
Profile resolution and marketplace URL logic.

Renamed from teams.py to better reflect profile resolution responsibilities.
Supports multi-marketplace architecture with org/team/project inheritance.

Key features:
- HTTPS-only enforcement: All marketplace URLs must use HTTPS protocol.
- Config inheritance: 3-layer merge (org defaults -> team -> project)
- Security boundaries: Blocked items (fnmatch patterns) never allowed
- Delegation control: Org controls whether teams can delegate to projects
"""

from __future__ import annotations

from typing import Any, cast
from urllib.parse import urlparse, urlunparse

# ═══════════════════════════════════════════════════════════════════════════════
# Core Profile Resolution Functions (New Architecture)
# ═══════════════════════════════════════════════════════════════════════════════


def list_profiles(org_config: dict[str, Any]) -> list[dict[str, Any]]:
    """
    List all available profiles from org config.

    Return list of profile dicts with name, description, plugin, and marketplace.
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


def resolve_profile(org_config: dict[str, Any], profile_name: str) -> dict[str, Any]:
    """
    Resolve profile by name, raise ValueError if not found.

    Return profile dict with name and all profile fields.
    """
    profiles = org_config.get("profiles", {})

    if profile_name not in profiles:
        available = ", ".join(sorted(profiles.keys())) or "(none)"
        raise ValueError(f"Profile '{profile_name}' not found. Available: {available}")

    profile_info = profiles[profile_name]
    return {"name": profile_name, **profile_info}


def resolve_marketplace(org_config: dict[Any, Any], profile: dict[Any, Any]) -> dict[Any, Any]:
    """
    Resolve marketplace for a profile and translate to claude_adapter format.

    This is the SINGLE translation layer between org-config schema and
    claude_adapter expected format. All schema changes should be handled here.

    Schema Translation:
        org-config (source/owner/repo) → claude_adapter (type/repo combined)

    Args:
        org_config: Organization config with marketplaces dict
        profile: Profile dict with a "marketplace" field

    Returns:
        Marketplace dict normalized for claude_adapter:
        - name: marketplace name (from dict key)
        - type: "github" | "gitlab" | "https"
        - repo: combined "owner/repo" for github
        - url: for git/url sources
        - ref: translated from "branch"

    Raises:
        ValueError: If marketplace not found, invalid source, or missing fields
    """
    marketplace_name = profile.get("marketplace")
    if not marketplace_name:
        raise ValueError(f"Profile '{profile.get('name')}' has no marketplace field")

    # Dict-based lookup
    marketplaces: dict[str, dict[Any, Any]] = org_config.get("marketplaces", {})
    marketplace_config = marketplaces.get(marketplace_name)

    if not marketplace_config:
        raise ValueError(
            f"Marketplace '{marketplace_name}' not found for profile '{profile.get('name')}'"
        )

    # Validate and translate source type
    source = marketplace_config.get("source", "")
    valid_sources = {"github", "git", "url"}
    if source not in valid_sources:
        raise ValueError(
            f"Marketplace '{marketplace_name}' has invalid source '{source}'. "
            f"Valid sources: {', '.join(sorted(valid_sources))}"
        )

    result: dict[str, Any] = {"name": marketplace_name}

    if source == "github":
        # GitHub: requires owner + repo, combine into single repo field
        owner = marketplace_config.get("owner", "")
        repo = marketplace_config.get("repo", "")
        if not owner or not repo:
            raise ValueError(
                f"GitHub marketplace '{marketplace_name}' requires 'owner' and 'repo' fields"
            )
        result["type"] = "github"
        result["repo"] = f"{owner}/{repo}"

    elif source == "git":
        # Generic git: maps to gitlab type
        # Supports two patterns:
        # 1. Direct URL: {"source": "git", "url": "https://..."}
        # 2. Host + owner + repo: {"source": "git", "host": "gitlab.example.org", "owner": "group", "repo": "name"}
        url = marketplace_config.get("url", "")
        host = marketplace_config.get("host", "")
        owner = marketplace_config.get("owner", "")
        repo = marketplace_config.get("repo", "")

        result["type"] = "gitlab"

        if url:
            # Pattern 1: Direct URL provided
            result["url"] = url
        elif host and owner and repo:
            # Pattern 2: Construct from host/owner/repo
            result["host"] = host
            result["repo"] = f"{owner}/{repo}"
        else:
            raise ValueError(
                f"Git marketplace '{marketplace_name}' requires either 'url' field "
                f"or 'host', 'owner', 'repo' fields"
            )

    elif source == "url":
        # HTTPS URL: requires url
        url = marketplace_config.get("url", "")
        if not url:
            raise ValueError(f"URL marketplace '{marketplace_name}' requires 'url' field")
        result["type"] = "https"
        result["url"] = url

    # Translate branch -> ref (optional)
    if marketplace_config.get("branch"):
        result["ref"] = marketplace_config["branch"]

    # Preserve optional fields
    for field_name in ("host", "auth", "headers", "path"):
        if marketplace_config.get(field_name):
            result[field_name] = marketplace_config[field_name]

    return result


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


def get_marketplace_url(marketplace: dict[str, Any]) -> str:
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
        return cast(str, urlunparse(normalized))

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
