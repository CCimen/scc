"""Compute effective configuration for profiles and projects."""

from __future__ import annotations

from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from scc_cli import config as config_module
from scc_cli.core.enums import MCPServerType, NetworkPolicy, RequestSource, TargetType
from scc_cli.core.network_policy import is_more_or_equal_restrictive

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
    blocked_by: str
    source: str  # Always "org.security"
    target_type: str = TargetType.PLUGIN


@dataclass
class DelegationDenied:
    """Tracks an addition denied due to delegation rules."""

    item: str
    requested_by: str  # RequestSource.TEAM or RequestSource.PROJECT
    reason: str
    target_type: str = TargetType.PLUGIN


@dataclass
class MCPServer:
    """Represents an MCP server configuration.

    Supports three transport types:
    - sse: Server-Sent Events (requires url)
    - stdio: Standard I/O (requires command, optional args and env)
    - http: HTTP transport (requires url, optional headers)
    """

    name: str
    type: str  # MCPServerType value
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


def matches_plugin_pattern(plugin_ref: str, pattern: str) -> bool:
    """Check plugin patterns, allowing bare names to match any marketplace."""
    if not plugin_ref or not pattern:
        return False
    normalized_ref = plugin_ref.strip().casefold()
    normalized_pattern = pattern.strip().casefold()
    if "@" not in normalized_pattern and "@" in normalized_ref:
        plugin_name = normalized_ref.split("@", 1)[0]
        return fnmatch(plugin_name, normalized_pattern)
    return fnmatch(normalized_ref, normalized_pattern)


def matches_blocked_plugin(plugin_ref: str, blocked_patterns: list[str]) -> str | None:
    """Return the matching pattern for a blocked plugin, if any."""
    for pattern in blocked_patterns:
        if matches_plugin_pattern(plugin_ref, pattern):
            return pattern
    return None


def is_plugin_allowed(plugin_ref: str, allowed_patterns: list[str] | None) -> bool:
    """Check whether plugin is allowed by an optional allowlist."""
    if allowed_patterns is None:
        return True
    if not allowed_patterns:
        return False
    for pattern in allowed_patterns:
        if matches_plugin_pattern(plugin_ref, pattern):
            return True
    return False


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


def match_blocked_mcp(server: dict[str, Any], blocked_patterns: list[str]) -> str | None:
    """Return the matching pattern for a blocked MCP server, if any."""
    for candidate in mcp_candidates(server):
        matched = matches_blocked(candidate, blocked_patterns)
        if matched:
            return matched
    return None


def is_network_mcp(server: dict[str, Any]) -> bool:
    """Return True for MCP transports that require network access."""
    return server.get("type") in {MCPServerType.SSE, MCPServerType.HTTP}


def record_network_policy_decision(
    result: EffectiveConfig,
    *,
    policy: str,
    reason: str,
    source: str,
) -> None:
    """Record the active network_policy decision (replace any prior entries)."""
    result.decisions = [d for d in result.decisions if d.field != "network_policy"]
    result.decisions.append(
        ConfigDecision(
            field="network_policy",
            value=policy,
            reason=reason,
            source=source,
        )
    )


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
        blocked_by = matches_blocked_plugin(plugin, blocked_plugins)
        if blocked_by:
            result.blocked_items.append(
                BlockedItem(item=plugin, blocked_by=blocked_by, source="org.security")
            )
            continue

        if matches_blocked_plugin(plugin, disabled_plugins):
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

    network_policy_source: str | None = None
    if default_network_policy:
        result.network_policy = default_network_policy
        network_policy_source = "org.defaults"
        record_network_policy_decision(
            result,
            policy=default_network_policy,
            reason="Organization default network policy",
            source="org.defaults",
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
        result.decisions.append(
            ConfigDecision(
                field="session.auto_resume",
                value=default_session["auto_resume"],
                reason="Organization default session auto-resume",
                source="org.defaults",
            )
        )

    profiles = org_config.get("profiles", {})
    team_config = profiles.get(team_name, {})

    team_network_policy = team_config.get("network_policy")
    if team_network_policy:
        if result.network_policy is None:
            result.network_policy = team_network_policy
            network_policy_source = f"team.{team_name}"
            record_network_policy_decision(
                result,
                policy=team_network_policy,
                reason=f"Overridden by team profile '{team_name}'",
                source=f"team.{team_name}",
            )
        elif is_more_or_equal_restrictive(team_network_policy, result.network_policy):
            result.network_policy = team_network_policy
            network_policy_source = f"team.{team_name}"
            record_network_policy_decision(
                result,
                policy=team_network_policy,
                reason=f"Overridden by team profile '{team_name}'",
                source=f"team.{team_name}",
            )

    team_plugins = team_config.get("additional_plugins", [])
    team_delegated_plugins = is_team_delegated_for_plugins(org_config, team_name)

    for plugin in team_plugins:
        blocked_by = matches_blocked_plugin(plugin, blocked_plugins)
        if blocked_by:
            result.blocked_items.append(
                BlockedItem(item=plugin, blocked_by=blocked_by, source="org.security")
            )
            continue

        if not team_delegated_plugins:
            result.denied_additions.append(
                DelegationDenied(
                    item=plugin,
                    requested_by=RequestSource.TEAM,
                    reason=f"Team '{team_name}' not allowed to add plugins",
                )
            )
            continue

        if not is_plugin_allowed(plugin, allowed_plugins):
            result.denied_additions.append(
                DelegationDenied(
                    item=plugin,
                    requested_by=RequestSource.TEAM,
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

        blocked_by = match_blocked_mcp(server_dict, blocked_mcp_servers)

        if blocked_by:
            result.blocked_items.append(
                BlockedItem(
                    item=server_name or server_url,
                    blocked_by=blocked_by,
                    source="org.security",
                    target_type=TargetType.MCP_SERVER,
                )
            )
            continue

        if not team_delegated_mcp:
            result.denied_additions.append(
                DelegationDenied(
                    item=server_name,
                    requested_by=RequestSource.TEAM,
                    reason=f"Team '{team_name}' not allowed to add MCP servers",
                    target_type=TargetType.MCP_SERVER,
                )
            )
            continue

        if not is_mcp_allowed(server_dict, allowed_mcp_servers):
            result.denied_additions.append(
                DelegationDenied(
                    item=server_name or server_url,
                    requested_by=RequestSource.TEAM,
                    reason="MCP server not allowed by defaults.allowed_mcp_servers",
                    target_type=TargetType.MCP_SERVER,
                )
            )
            continue

        if result.network_policy == NetworkPolicy.ISOLATED.value and is_network_mcp(server_dict):
            result.blocked_items.append(
                BlockedItem(
                    item=server_name or server_url,
                    blocked_by="network_policy=isolated",
                    source=network_policy_source or "org.defaults",
                    target_type=TargetType.MCP_SERVER,
                )
            )
            continue

        if server_dict.get("type") == MCPServerType.STDIO:
            stdio_result = validate_stdio_server(server_dict, org_config)
            if stdio_result.blocked:
                result.blocked_items.append(
                    BlockedItem(
                        item=server_name,
                        blocked_by=stdio_result.reason,
                        source="org.security",
                        target_type=TargetType.MCP_SERVER,
                    )
                )
                continue

        mcp_server = MCPServer(
            name=server_name,
            type=server_dict.get("type", MCPServerType.SSE),
            url=server_url or None,
            command=server_dict.get("command"),
            args=server_dict.get("args"),
            env=server_dict.get("env"),
            headers=server_dict.get("headers"),
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
    if team_session.get("auto_resume") is not None:
        result.session_config.auto_resume = team_session["auto_resume"]
        result.decisions.append(
            ConfigDecision(
                field="session.auto_resume",
                value=team_session["auto_resume"],
                reason=f"Overridden by team profile '{team_name}'",
                source=f"team.{team_name}",
            )
        )

    if project_config:
        project_delegated, delegation_reason = is_project_delegated(org_config, team_name)

        project_plugins = project_config.get("additional_plugins", [])
        for plugin in project_plugins:
            blocked_by = matches_blocked_plugin(plugin, blocked_plugins)
            if blocked_by:
                result.blocked_items.append(
                    BlockedItem(item=plugin, blocked_by=blocked_by, source="org.security")
                )
                continue

            if not project_delegated:
                result.denied_additions.append(
                    DelegationDenied(
                        item=plugin,
                        requested_by=RequestSource.PROJECT,
                        reason=delegation_reason,
                    )
                )
                continue

            if not is_plugin_allowed(plugin, allowed_plugins):
                result.denied_additions.append(
                    DelegationDenied(
                        item=plugin,
                        requested_by=RequestSource.PROJECT,
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

            blocked_by = match_blocked_mcp(server_dict, blocked_mcp_servers)

            if blocked_by:
                result.blocked_items.append(
                    BlockedItem(
                        item=server_name or server_url,
                        blocked_by=blocked_by,
                        source="org.security",
                        target_type=TargetType.MCP_SERVER,
                    )
                )
                continue

            if not project_delegated:
                result.denied_additions.append(
                    DelegationDenied(
                        item=server_name,
                        requested_by=RequestSource.PROJECT,
                        reason=delegation_reason,
                        target_type=TargetType.MCP_SERVER,
                    )
                )
                continue

            if not is_mcp_allowed(server_dict, allowed_mcp_servers):
                result.denied_additions.append(
                    DelegationDenied(
                        item=server_name or server_url,
                        requested_by=RequestSource.PROJECT,
                        reason="MCP server not allowed by defaults.allowed_mcp_servers",
                        target_type=TargetType.MCP_SERVER,
                    )
                )
                continue

            if result.network_policy == NetworkPolicy.ISOLATED.value and is_network_mcp(
                server_dict
            ):
                result.blocked_items.append(
                    BlockedItem(
                        item=server_name or server_url,
                        blocked_by="network_policy=isolated",
                        source=network_policy_source or "org.defaults",
                        target_type=TargetType.MCP_SERVER,
                    )
                )
                continue

            if server_dict.get("type") == MCPServerType.STDIO:
                stdio_result = validate_stdio_server(server_dict, org_config)
                if stdio_result.blocked:
                    result.blocked_items.append(
                        BlockedItem(
                            item=server_name,
                            blocked_by=stdio_result.reason,
                            source="org.security",
                            target_type=TargetType.MCP_SERVER,
                        )
                    )
                    continue

            mcp_server = MCPServer(
                name=server_name,
                type=server_dict.get("type", MCPServerType.SSE),
                url=server_url or None,
                command=server_dict.get("command"),
                args=server_dict.get("args"),
                env=server_dict.get("env"),
                headers=server_dict.get("headers"),
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
        if project_session.get("auto_resume") is not None:
            if project_delegated:
                result.session_config.auto_resume = project_session["auto_resume"]
                result.decisions.append(
                    ConfigDecision(
                        field="session.auto_resume",
                        value=project_session["auto_resume"],
                        reason="Overridden by project config",
                        source="project",
                    )
                )

    return result
