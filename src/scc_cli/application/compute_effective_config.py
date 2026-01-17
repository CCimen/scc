"""Compute effective configuration for profiles and projects."""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from scc_cli import config as config_module

if TYPE_CHECKING:
    pass


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
    target_type: str = "plugin"  # "plugin" | "mcp_server"


@dataclass
class DelegationDenied:
    """Tracks an addition denied due to delegation rules."""

    item: str
    requested_by: str  # "team" | "project"
    reason: str
    target_type: str = "plugin"  # "plugin" | "mcp_server"


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


def matches_blocked(item: str, blocked_patterns: list[str]) -> str | None:
    """Check whether item matches any blocked pattern using fnmatch.

    Use casefold() for case-insensitive matching. This is important because:
    - casefold() handles Unicode edge cases (e.g., German ss -> ss)
    - Pattern "Malicious-*" should block "malicious-tool"

    Args:
        item: The item to check (plugin name, MCP server name/URL, etc.)
        blocked_patterns: List of fnmatch patterns

    Returns:
        The pattern that matched, or None if no match
    """
    normalized_item = item.strip().casefold()

    for pattern in blocked_patterns:
        normalized_pattern = pattern.strip().casefold()
        if fnmatch(normalized_item, normalized_pattern):
            return pattern
    return None


def is_allowed(item: str, allowed_patterns: list[str] | None) -> bool:
    """Check whether item is allowed by an optional allowlist."""
    if allowed_patterns is None:
        return True
    if not allowed_patterns:
        return False
    return matches_blocked(item, allowed_patterns) is not None


def mcp_candidates(server: dict[str, Any]) -> list[str]:
    """Collect candidate strings for MCP allow/block matching."""
    candidates: list[str] = []
    name = server.get("name", "")
    if name:
        candidates.append(name)
    url = server.get("url", "")
    if url:
        candidates.append(url)
        domain = _extract_domain(url)
        if domain:
            candidates.append(domain)
    command = server.get("command", "")
    if command:
        candidates.append(command)
    return candidates


def is_mcp_allowed(server: dict[str, Any], allowed_patterns: list[str] | None) -> bool:
    """Check whether MCP server is allowed by patterns."""
    if allowed_patterns is None:
        return True
    if not allowed_patterns:
        return False
    for candidate in mcp_candidates(server):
        if matches_blocked(candidate, allowed_patterns):
            return True
    return False


def validate_stdio_server(
    server: dict[str, Any],
    org_config: dict[str, Any],
) -> StdioValidationResult:
    """Validate a stdio MCP server configuration against org security policy.

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

    if not security.get("allow_stdio_mcp", False):
        return StdioValidationResult(
            blocked=True,
            reason="stdio MCP disabled by org policy",
        )

    if not os.path.isabs(command):
        return StdioValidationResult(
            blocked=True,
            reason="stdio command must be absolute path",
        )

    prefixes = security.get("allowed_stdio_prefixes", [])
    if prefixes:
        try:
            resolved = os.path.realpath(command)
        except OSError:
            resolved = command

        normalized_prefixes = []
        for prefix in prefixes:
            try:
                normalized_prefixes.append(os.path.realpath(prefix.rstrip("/")))
            except OSError:
                normalized_prefixes.append(prefix.rstrip("/"))

        allowed = False
        for prefix in normalized_prefixes:
            try:
                common = os.path.commonpath([resolved, prefix])
                if common == prefix:
                    allowed = True
                    break
            except ValueError:
                continue

        if not allowed:
            return StdioValidationResult(
                blocked=True,
                reason=f"Resolved path {resolved} not in allowed prefixes",
            )

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
    """Check whether team is allowed to add additional plugins."""
    if not team_name:
        return False

    delegation = org_config.get("delegation", {})
    teams_delegation = delegation.get("teams", {})
    allowed_patterns = teams_delegation.get("allow_additional_plugins", [])

    return matches_blocked(team_name, allowed_patterns) is not None


def is_team_delegated_for_mcp(org_config: dict[str, Any], team_name: str | None) -> bool:
    """Check whether team is allowed to add MCP servers."""
    if not team_name:
        return False

    delegation = org_config.get("delegation", {})
    teams_delegation = delegation.get("teams", {})
    allowed_patterns = teams_delegation.get("allow_additional_mcp_servers", [])

    return matches_blocked(team_name, allowed_patterns) is not None


def is_project_delegated(org_config: dict[str, Any], team_name: str | None) -> tuple[bool, str]:
    """Check whether project-level additions are allowed."""
    if not team_name:
        return (False, "No team specified")

    delegation = org_config.get("delegation", {})
    projects_delegation = delegation.get("projects", {})
    org_allows = projects_delegation.get("inherit_team_delegation", False)

    if not org_allows:
        return (False, "Org disabled project delegation (inherit_team_delegation: false)")

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
    team_name: str | None,
    project_config: dict[str, Any] | None = None,
    workspace_path: str | Path | None = None,
) -> EffectiveConfig:
    """Compute effective configuration by merging org defaults → team → project."""
    if workspace_path is not None:
        project_config = config_module.read_project_config(workspace_path)

    result = EffectiveConfig()

    security = org_config.get("security", {})
    blocked_plugins = security.get("blocked_plugins", [])
    blocked_mcp_servers = security.get("blocked_mcp_servers", [])

    defaults = org_config.get("defaults", {})
    default_plugins = defaults.get("enabled_plugins", [])
    disabled_plugins = defaults.get("disabled_plugins", [])
    allowed_plugins = defaults.get("allowed_plugins")
    allowed_mcp_servers = defaults.get("allowed_mcp_servers")
    default_network_policy = defaults.get("network_policy")
    default_session = defaults.get("session", {})

    for plugin in default_plugins:
        blocked_by = matches_blocked(plugin, blocked_plugins)
        if blocked_by:
            result.blocked_items.append(
                BlockedItem(item=plugin, blocked_by=blocked_by, source="org.security")
            )
            continue

        if matches_blocked(plugin, disabled_plugins):
            continue

        result.plugins.add(plugin)
        result.decisions.append(
            ConfigDecision(
                field="plugins",
                value=plugin,
                reason="Included in organization defaults",
                source="org.defaults",
            )
        )

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

    profiles = org_config.get("profiles", {})
    team_config = profiles.get(team_name, {})

    team_plugins = team_config.get("additional_plugins", [])
    team_delegated_plugins = is_team_delegated_for_plugins(org_config, team_name)

    for plugin in team_plugins:
        blocked_by = matches_blocked(plugin, blocked_plugins)
        if blocked_by:
            result.blocked_items.append(
                BlockedItem(item=plugin, blocked_by=blocked_by, source="org.security")
            )
            continue

        if not team_delegated_plugins:
            result.denied_additions.append(
                DelegationDenied(
                    item=plugin,
                    requested_by="team",
                    reason=f"Team '{team_name}' not allowed to add plugins",
                )
            )
            continue

        if not is_allowed(plugin, allowed_plugins):
            result.denied_additions.append(
                DelegationDenied(
                    item=plugin,
                    requested_by="team",
                    reason="Plugin not allowed by defaults.allowed_plugins",
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

    team_mcp_servers = team_config.get("additional_mcp_servers", [])
    team_delegated_mcp = is_team_delegated_for_mcp(org_config, team_name)

    for server_dict in team_mcp_servers:
        server_name = server_dict.get("name", "")
        server_url = server_dict.get("url", "")

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

        if not is_mcp_allowed(server_dict, allowed_mcp_servers):
            result.denied_additions.append(
                DelegationDenied(
                    item=server_name or server_url,
                    requested_by="team",
                    reason="MCP server not allowed by defaults.allowed_mcp_servers",
                    target_type="mcp_server",
                )
            )
            continue

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

    if project_config:
        project_delegated, delegation_reason = is_project_delegated(org_config, team_name)

        project_plugins = project_config.get("additional_plugins", [])
        for plugin in project_plugins:
            blocked_by = matches_blocked(plugin, blocked_plugins)
            if blocked_by:
                result.blocked_items.append(
                    BlockedItem(item=plugin, blocked_by=blocked_by, source="org.security")
                )
                continue

            if not project_delegated:
                result.denied_additions.append(
                    DelegationDenied(
                        item=plugin,
                        requested_by="project",
                        reason=delegation_reason,
                    )
                )
                continue

            if not is_allowed(plugin, allowed_plugins):
                result.denied_additions.append(
                    DelegationDenied(
                        item=plugin,
                        requested_by="project",
                        reason="Plugin not allowed by defaults.allowed_plugins",
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

        project_mcp_servers = project_config.get("additional_mcp_servers", [])
        for server_dict in project_mcp_servers:
            server_name = server_dict.get("name", "")
            server_url = server_dict.get("url", "")

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

            if not is_mcp_allowed(server_dict, allowed_mcp_servers):
                result.denied_additions.append(
                    DelegationDenied(
                        item=server_name or server_url,
                        requested_by="project",
                        reason="MCP server not allowed by defaults.allowed_mcp_servers",
                        target_type="mcp_server",
                    )
                )
                continue

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
