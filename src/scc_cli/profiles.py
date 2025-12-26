"""
Profile resolution and marketplace URL logic.

Renamed from teams.py to better reflect profile resolution responsibilities.
Support new multi-marketplace architecture while maintaining backward compatibility
with legacy single-marketplace config format.

Key features:
- HTTPS-only enforcement: All marketplace URLs must use HTTPS protocol.
- Config inheritance: 3-layer merge (org defaults -> team -> project)
- Security boundaries: Blocked items (fnmatch patterns) never allowed
- Delegation control: Org controls whether teams can delegate to projects
"""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import urlparse, urlunparse

from . import config as config_module

if TYPE_CHECKING:
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# Data Classes for Effective Config (v2 schema)
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ConfigDecision:
    """Tracks where a config value came from (for scc config explain)."""

    field: str
    value: Any
    reason: str
    source: str  # "org.security" | "org.defaults" | "team.X" | "project"


@dataclass
class BlockedItem:
    """Tracks an item blocked by security pattern."""

    item: str
    blocked_by: str  # The pattern that matched
    source: str  # Always "org.security"
    target_type: str = "plugin"  # "plugin" | "mcp_server" | "base_image"


@dataclass
class DelegationDenied:
    """Tracks an addition denied due to delegation rules."""

    item: str
    requested_by: str  # "team" | "project"
    reason: str
    target_type: str = "plugin"  # "plugin" | "mcp_server" | "base_image"


@dataclass
class MCPServer:
    """Represents an MCP server configuration.

    Supports three transport types:
    - sse: Server-Sent Events (requires url)
    - stdio: Standard I/O (requires command, optional args and env)
    - http: HTTP transport (requires url, optional headers)
    """

    name: str
    type: str  # "sse" | "stdio" | "http"
    url: str | None = None
    command: str | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    headers: dict[str, str] | None = None


@dataclass
class SessionConfig:
    """Session configuration."""

    timeout_hours: int | None = None
    auto_resume: bool | None = None


@dataclass
class EffectiveConfig:
    """The computed effective configuration after 3-layer merge.

    Contains:
    - Final resolved values (plugins, mcp_servers, etc.)
    - Tracking information for debugging (decisions, blocked_items, denied_additions)
    """

    plugins: set[str] = field(default_factory=set)
    mcp_servers: list[MCPServer] = field(default_factory=list)
    network_policy: str | None = None
    session_config: SessionConfig = field(default_factory=SessionConfig)

    # For scc config explain
    decisions: list[ConfigDecision] = field(default_factory=list)
    blocked_items: list[BlockedItem] = field(default_factory=list)
    denied_additions: list[DelegationDenied] = field(default_factory=list)


@dataclass
class StdioValidationResult:
    """Result of validating a stdio MCP server configuration.

    stdio servers are the "sharpest knife" - they have elevated privileges:
    - Mounted workspace (write access)
    - Network access (required for some tools)
    - Tokens in environment variables

    This validation implements layered defense:
    - Gate 1: Feature gate (org must explicitly enable)
    - Gate 2: Absolute path required (prevents ./evil injection)
    - Gate 3: Prefix allowlist + commonpath (prevents path traversal)
    - Warnings for host-side checks (command runs in container, not host)
    """

    blocked: bool
    reason: str = ""
    warnings: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# Config Inheritance Functions (3-layer merge)
# ═══════════════════════════════════════════════════════════════════════════════


def matches_blocked(item: str, blocked_patterns: list[str]) -> str | None:
    """
    Check whether item matches any blocked pattern using fnmatch.

    Use casefold() for case-insensitive matching. This is important because:
    - casefold() handles Unicode edge cases (e.g., German ss -> ss)
    - Pattern "Malicious-*" should block "malicious-tool"

    Args:
        item: The item to check (plugin name, MCP server name/URL, etc.)
        blocked_patterns: List of fnmatch patterns

    Returns:
        The pattern that matched, or None if no match
    """
    # Normalize item: strip whitespace and casefold for case-insensitive matching
    normalized_item = item.strip().casefold()

    for pattern in blocked_patterns:
        # Normalize pattern the same way
        normalized_pattern = pattern.strip().casefold()
        if fnmatch(normalized_item, normalized_pattern):
            return pattern  # Return original pattern for error messages
    return None


def normalize_image_for_policy(ref: str) -> str:
    """
    Normalize Docker image reference for policy matching.

    Handle implicit :latest tag - this is crucial for blocking unpinned images.
    For example, blocking "*:latest" should catch "ubuntu" (which implicitly uses :latest).

    Phase 1 scope: Only handle implicit :latest normalization.
    NOT full OCI canonicalization (docker.io/library etc) - that's Phase 2.

    Args:
        ref: Docker image reference (e.g., "ubuntu", "python:3.11", "nginx@sha256:...")

    Returns:
        Normalized reference, casefolded for matching.
        Empty strings remain empty.
    """
    r = ref.strip()
    if not r:
        return r

    # If image has a digest (@sha256:...), don't add :latest
    # Digests are immutable and take precedence over tags
    if "@" in r:
        return r.casefold()

    # Check if the last component (after the last /) has an explicit tag
    # We need to handle registry:port/path:tag correctly
    last_segment = r.rsplit("/", 1)[-1]

    # If no ":" in the last segment, there's no explicit tag → add :latest
    # This handles:
    #   - "ubuntu" → "ubuntu:latest"
    #   - "ghcr.io/owner/repo" → "ghcr.io/owner/repo:latest"
    #   - "registry:5000/ns/img" → "registry:5000/ns/img:latest" (port is before /)
    if ":" not in last_segment:
        r = f"{r}:latest"

    return r.casefold()


def validate_stdio_server(
    server: dict[str, Any],
    org_config: dict[str, Any],
) -> StdioValidationResult:
    """
    Validate a stdio MCP server configuration against org security policy.

    stdio servers are the "sharpest knife" - they have elevated privileges:
    - Mounted workspace (write access)
    - Network access (required for some tools)
    - Tokens in environment variables

    Validation gates (in order):
    1. Feature gate: security.allow_stdio_mcp must be true (default: false)
    2. Absolute path: command must be an absolute path (not relative)
    3. Prefix allowlist: if allowed_stdio_prefixes is set, command must be under one

    Host-side checks (existence, executable) generate warnings only because
    the command runs inside the container, not on the host.

    Args:
        server: MCP server dict with 'name', 'type', 'command' fields
        org_config: Organization config dict

    Returns:
        StdioValidationResult with blocked=True/False, reason, and warnings
    """
    import os

    command = server.get("command", "")
    warnings: list[str] = []
    security = org_config.get("security", {})

    # Gate 1: Feature gate - stdio must be explicitly enabled by org
    # Default is False because stdio servers have elevated privileges
    if not security.get("allow_stdio_mcp", False):
        return StdioValidationResult(
            blocked=True,
            reason="stdio MCP disabled by org policy",
        )

    # Gate 2: Absolute path required - prevents "./evil" injection attacks
    if not os.path.isabs(command):
        return StdioValidationResult(
            blocked=True,
            reason="stdio command must be absolute path",
        )

    # Gate 3: Prefix allowlist with commonpath enforcement
    # Uses realpath to resolve symlinks and ".." traversal attempts
    prefixes = security.get("allowed_stdio_prefixes", [])
    if prefixes:
        # Resolve the actual path (handles symlinks and ..)
        try:
            resolved = os.path.realpath(command)
        except OSError:
            # If we can't resolve, use the original command
            resolved = command

        # Normalize prefixes the same way
        normalized_prefixes = []
        for p in prefixes:
            try:
                # Remove trailing slash for consistent commonpath comparison
                normalized_prefixes.append(os.path.realpath(p.rstrip("/")))
            except OSError:
                normalized_prefixes.append(p.rstrip("/"))

        # Check if resolved path is under any allowed prefix
        allowed = False
        for prefix in normalized_prefixes:
            try:
                # commonpath returns the longest common sub-path
                # If it equals the prefix, command is under that prefix
                common = os.path.commonpath([resolved, prefix])
                if common == prefix:
                    allowed = True
                    break
            except ValueError:
                # Different drives on Windows, or empty sequence
                continue

        if not allowed:
            return StdioValidationResult(
                blocked=True,
                reason=f"Resolved path {resolved} not in allowed prefixes",
            )

    # Host-side checks: WARN only (command runs in container, not host)
    # These are informational because filesystem differs between host and container
    if not os.path.exists(command):
        warnings.append(f"Command not found on host: {command}")
    elif not os.access(command, os.X_OK):
        warnings.append(f"Command not executable on host: {command}")

    return StdioValidationResult(
        blocked=False,
        warnings=warnings,
    )


def _extract_domain(url: str) -> str:
    """Extract domain from URL for pattern matching."""
    parsed = urlparse(url)
    return parsed.netloc or url


def is_team_delegated_for_plugins(org_config: dict[str, Any], team_name: str | None) -> bool:
    """
    Check whether team is allowed to add additional plugins.

    Use fnmatch patterns from delegation.teams.allow_additional_plugins.
    """
    if not team_name:
        return False

    delegation = org_config.get("delegation", {})
    teams_delegation = delegation.get("teams", {})
    allowed_patterns = teams_delegation.get("allow_additional_plugins", [])

    # Check if team name matches any allowed pattern
    for pattern in allowed_patterns:
        if pattern == "*" or fnmatch(team_name, pattern):
            return True
    return False


def is_team_delegated_for_mcp(org_config: dict[str, Any], team_name: str | None) -> bool:
    """
    Check whether team is allowed to add MCP servers.

    Use fnmatch patterns from delegation.teams.allow_additional_mcp_servers.
    """
    if not team_name:
        return False

    delegation = org_config.get("delegation", {})
    teams_delegation = delegation.get("teams", {})
    allowed_patterns = teams_delegation.get("allow_additional_mcp_servers", [])

    # Check if team name matches any allowed pattern
    for pattern in allowed_patterns:
        if pattern == "*" or fnmatch(team_name, pattern):
            return True
    return False


def is_project_delegated(org_config: dict[str, Any], team_name: str | None) -> tuple[bool, str]:
    """
    Check whether project-level additions are allowed.

    TWO-LEVEL CHECK:
    1. Org-level: delegation.projects.inherit_team_delegation must be true
    2. Team-level: profiles.<team>.delegation.allow_project_overrides must be true

    If org disables inheritance (inherit_team_delegation: false), team-level
    settings are ignored - this is the master switch.

    Returns:
        Tuple of (allowed: bool, reason: str)
        Reason explains why delegation was denied if allowed is False
    """
    if not team_name:
        return (False, "No team specified")

    # First check: org-level master switch
    delegation = org_config.get("delegation", {})
    projects_delegation = delegation.get("projects", {})
    org_allows = projects_delegation.get("inherit_team_delegation", False)

    if not org_allows:
        # Org-level master switch is OFF - team settings are ignored
        return (False, "Org disabled project delegation (inherit_team_delegation: false)")

    # Second check: team-level setting
    profiles = org_config.get("profiles", {})
    team_config = profiles.get(team_name, {})
    team_delegation = team_config.get("delegation", {})
    team_allows = team_delegation.get("allow_project_overrides", False)

    if not team_allows:
        return (
            False,
            f"Team '{team_name}' disabled project overrides (allow_project_overrides: false)",
        )

    return (True, "")


def compute_effective_config(
    org_config: dict[str, Any],
    team_name: str,
    project_config: dict[str, Any] | None = None,
    workspace_path: str | Path | None = None,
) -> EffectiveConfig:
    """
    Compute effective configuration by merging org defaults → team → project.

    The merge follows these rules:
    1. Start with org defaults
    2. Apply team additions (if delegated)
    3. Apply project additions (if delegated)
    4. Security blocks are NEVER overridable - checked at every layer

    Args:
        org_config: Organization config (v2 schema)
        team_name: Name of the team profile to apply
        project_config: Optional project-level config (.scc.yaml content)
        workspace_path: Optional path to workspace directory containing .scc.yaml.
                        If provided, takes precedence over project_config.

    Returns:
        EffectiveConfig with merged values and tracking information
    """
    # Load project config from file if workspace_path provided
    if workspace_path is not None:
        project_config = config_module.read_project_config(workspace_path)

    result = EffectiveConfig()

    # Get security blocks (never overridable)
    security = org_config.get("security", {})
    blocked_plugins = security.get("blocked_plugins", [])
    blocked_mcp_servers = security.get("blocked_mcp_servers", [])

    # Get org defaults
    defaults = org_config.get("defaults", {})
    default_plugins = defaults.get("allowed_plugins", [])
    default_network_policy = defaults.get("network_policy")
    default_session = defaults.get("session", {})

    # ─────────────────────────────────────────────────────────────────────────
    # Layer 1: Apply org defaults
    # ─────────────────────────────────────────────────────────────────────────

    # Add default plugins (checking against security blocks)
    for plugin in default_plugins:
        blocked_by = matches_blocked(plugin, blocked_plugins)
        if blocked_by:
            result.blocked_items.append(
                BlockedItem(item=plugin, blocked_by=blocked_by, source="org.security")
            )
        else:
            result.plugins.add(plugin)
            result.decisions.append(
                ConfigDecision(
                    field="plugins",
                    value=plugin,
                    reason="Included in organization defaults",
                    source="org.defaults",
                )
            )

    # Set network policy from defaults
    if default_network_policy:
        result.network_policy = default_network_policy
        result.decisions.append(
            ConfigDecision(
                field="network_policy",
                value=default_network_policy,
                reason="Organization default network policy",
                source="org.defaults",
            )
        )

    # Set session config from defaults
    if default_session.get("timeout_hours") is not None:
        result.session_config.timeout_hours = default_session["timeout_hours"]
        result.decisions.append(
            ConfigDecision(
                field="session.timeout_hours",
                value=default_session["timeout_hours"],
                reason="Organization default session timeout",
                source="org.defaults",
            )
        )
    if default_session.get("auto_resume") is not None:
        result.session_config.auto_resume = default_session["auto_resume"]

    # ─────────────────────────────────────────────────────────────────────────
    # Layer 2: Apply team profile additions
    # ─────────────────────────────────────────────────────────────────────────

    profiles = org_config.get("profiles", {})
    team_config = profiles.get(team_name, {})

    # Add team plugins (if delegated)
    team_plugins = team_config.get("additional_plugins", [])
    team_delegated_plugins = is_team_delegated_for_plugins(org_config, team_name)

    for plugin in team_plugins:
        # Security check first
        blocked_by = matches_blocked(plugin, blocked_plugins)
        if blocked_by:
            result.blocked_items.append(
                BlockedItem(item=plugin, blocked_by=blocked_by, source="org.security")
            )
            continue

        # Delegation check
        if not team_delegated_plugins:
            result.denied_additions.append(
                DelegationDenied(
                    item=plugin,
                    requested_by="team",
                    reason=f"Team '{team_name}' not allowed to add plugins",
                )
            )
            continue

        result.plugins.add(plugin)
        result.decisions.append(
            ConfigDecision(
                field="plugins",
                value=plugin,
                reason=f"Added by team profile '{team_name}'",
                source=f"team.{team_name}",
            )
        )

    # Add team MCP servers (if delegated)
    team_mcp_servers = team_config.get("additional_mcp_servers", [])
    team_delegated_mcp = is_team_delegated_for_mcp(org_config, team_name)

    for server_dict in team_mcp_servers:
        server_name = server_dict.get("name", "")
        server_url = server_dict.get("url", "")

        # Security check - check both name and URL domain
        blocked_by = matches_blocked(server_name, blocked_mcp_servers)
        if not blocked_by and server_url:
            domain = _extract_domain(server_url)
            blocked_by = matches_blocked(domain, blocked_mcp_servers)

        if blocked_by:
            result.blocked_items.append(
                BlockedItem(
                    item=server_name or server_url,
                    blocked_by=blocked_by,
                    source="org.security",
                    target_type="mcp_server",
                )
            )
            continue

        # Delegation check
        if not team_delegated_mcp:
            result.denied_additions.append(
                DelegationDenied(
                    item=server_name,
                    requested_by="team",
                    reason=f"Team '{team_name}' not allowed to add MCP servers",
                    target_type="mcp_server",
                )
            )
            continue

        # stdio-type servers require additional security validation
        if server_dict.get("type") == "stdio":
            stdio_result = validate_stdio_server(server_dict, org_config)
            if stdio_result.blocked:
                result.blocked_items.append(
                    BlockedItem(
                        item=server_name,
                        blocked_by=stdio_result.reason,
                        source="org.security",
                        target_type="mcp_server",
                    )
                )
                continue
            # Warnings are logged inside validate_stdio_server

        mcp_server = MCPServer(
            name=server_name,
            type=server_dict.get("type", "sse"),
            url=server_url or None,
            command=server_dict.get("command"),
            args=server_dict.get("args"),
        )
        result.mcp_servers.append(mcp_server)
        result.decisions.append(
            ConfigDecision(
                field="mcp_servers",
                value=server_name,
                reason=f"Added by team profile '{team_name}'",
                source=f"team.{team_name}",
            )
        )

    # Team session override
    team_session = team_config.get("session", {})
    if team_session.get("timeout_hours") is not None:
        result.session_config.timeout_hours = team_session["timeout_hours"]
        result.decisions.append(
            ConfigDecision(
                field="session.timeout_hours",
                value=team_session["timeout_hours"],
                reason=f"Overridden by team profile '{team_name}'",
                source=f"team.{team_name}",
            )
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Layer 3: Apply project additions (if delegated)
    # ─────────────────────────────────────────────────────────────────────────

    if project_config:
        project_delegated, delegation_reason = is_project_delegated(org_config, team_name)

        # Add project plugins
        project_plugins = project_config.get("additional_plugins", [])
        for plugin in project_plugins:
            # Security check first
            blocked_by = matches_blocked(plugin, blocked_plugins)
            if blocked_by:
                result.blocked_items.append(
                    BlockedItem(item=plugin, blocked_by=blocked_by, source="org.security")
                )
                continue

            # Delegation check
            if not project_delegated:
                result.denied_additions.append(
                    DelegationDenied(
                        item=plugin,
                        requested_by="project",
                        reason=delegation_reason,
                    )
                )
                continue

            result.plugins.add(plugin)
            result.decisions.append(
                ConfigDecision(
                    field="plugins",
                    value=plugin,
                    reason="Added by project config",
                    source="project",
                )
            )

        # Add project MCP servers
        project_mcp_servers = project_config.get("additional_mcp_servers", [])
        for server_dict in project_mcp_servers:
            server_name = server_dict.get("name", "")
            server_url = server_dict.get("url", "")

            # Security check
            blocked_by = matches_blocked(server_name, blocked_mcp_servers)
            if not blocked_by and server_url:
                domain = _extract_domain(server_url)
                blocked_by = matches_blocked(domain, blocked_mcp_servers)

            if blocked_by:
                result.blocked_items.append(
                    BlockedItem(
                        item=server_name or server_url,
                        blocked_by=blocked_by,
                        source="org.security",
                        target_type="mcp_server",
                    )
                )
                continue

            # Delegation check
            if not project_delegated:
                result.denied_additions.append(
                    DelegationDenied(
                        item=server_name,
                        requested_by="project",
                        reason=delegation_reason,
                        target_type="mcp_server",
                    )
                )
                continue

            # stdio-type servers require additional security validation
            if server_dict.get("type") == "stdio":
                stdio_result = validate_stdio_server(server_dict, org_config)
                if stdio_result.blocked:
                    result.blocked_items.append(
                        BlockedItem(
                            item=server_name,
                            blocked_by=stdio_result.reason,
                            source="org.security",
                            target_type="mcp_server",
                        )
                    )
                    continue
                # Warnings are logged inside validate_stdio_server

            mcp_server = MCPServer(
                name=server_name,
                type=server_dict.get("type", "sse"),
                url=server_url or None,
                command=server_dict.get("command"),
                args=server_dict.get("args"),
            )
            result.mcp_servers.append(mcp_server)
            result.decisions.append(
                ConfigDecision(
                    field="mcp_servers",
                    value=server_name,
                    reason="Added by project config",
                    source="project",
                )
            )

        # Project session override
        project_session = project_config.get("session", {})
        if project_session.get("timeout_hours") is not None:
            if project_delegated:
                result.session_config.timeout_hours = project_session["timeout_hours"]
                result.decisions.append(
                    ConfigDecision(
                        field="session.timeout_hours",
                        value=project_session["timeout_hours"],
                        reason="Overridden by project config",
                        source="project",
                    )
                )

    return result


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
    Resolve marketplace for a profile.

    Look up marketplace by name from the marketplaces array.
    Raise ValueError if marketplace not found.
    """
    marketplace_name = profile.get("marketplace")

    # Support both new marketplaces[] array and legacy marketplace{} object
    marketplaces: list[dict[Any, Any]] = org_config.get("marketplaces", [])

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


# ═══════════════════════════════════════════════════════════════════════════════
# Backward Compatibility Functions (Legacy API from teams.py)
# ═══════════════════════════════════════════════════════════════════════════════


def list_teams(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """
    List available teams from configuration.

    BACKWARD COMPATIBILITY: Wrap list_profiles() for legacy code.
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


def get_team_details(team: str, cfg: dict[str, Any]) -> dict[str, Any] | None:
    """
    Get detailed information for a specific team.

    BACKWARD COMPATIBILITY: Support legacy single marketplace format.
    Return None if team doesn't exist.
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


def get_team_sandbox_settings(team_name: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Generate sandbox settings for a team profile.

    BACKWARD COMPATIBILITY: Support legacy single marketplace format.

    Return settings.json content with extraKnownMarketplaces
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


def get_team_plugin_id(team_name: str, cfg: dict[str, Any] | None = None) -> str | None:
    """
    Get the full plugin ID for a team (e.g., "api-team@sundsvall").

    BACKWARD COMPATIBILITY: Support legacy single marketplace format.
    Return None if team has no plugin configured.
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


def validate_team_profile(team_name: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Validate a team profile configuration.

    BACKWARD COMPATIBILITY: Support legacy single marketplace format.

    Return dict with:
        - valid: bool
        - team: team name
        - plugin: plugin name or None
        - errors: list of validation errors
        - warnings: list of warnings
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
