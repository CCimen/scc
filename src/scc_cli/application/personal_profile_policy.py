"""Policy helpers for filtering personal profiles before applying."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from scc_cli.application.compute_effective_config import (
    match_blocked_mcp,
    matches_blocked_plugin,
    validate_stdio_server,
)
from scc_cli.core.enums import MCPServerType, TargetType


@dataclass(frozen=True)
class ProfilePolicySkip:
    """Represents a profile item skipped due to org security policy."""

    item: str
    reason: str
    target_type: str


def filter_personal_profile_settings(
    personal_settings: dict[str, Any],
    org_config: dict[str, Any],
) -> tuple[dict[str, Any], list[ProfilePolicySkip]]:
    """Filter personal profile settings against org security blocks."""
    security = org_config.get("security", {})
    blocked_plugins = security.get("blocked_plugins", [])
    if not personal_settings or not blocked_plugins:
        return personal_settings, []

    skips: list[ProfilePolicySkip] = []
    filtered = dict(personal_settings)

    plugins_raw = personal_settings.get("enabledPlugins")
    if isinstance(plugins_raw, list):
        filtered_plugin_list: list[str] = []
        for plugin in plugins_raw:
            plugin_ref = str(plugin)
            blocked_by = matches_blocked_plugin(plugin_ref, blocked_plugins)
            if blocked_by:
                skips.append(
                    ProfilePolicySkip(
                        item=plugin_ref,
                        reason=f"blocked by org policy ({blocked_by})",
                        target_type=TargetType.PLUGIN,
                    )
                )
                continue
            filtered_plugin_list.append(plugin_ref)
        filtered["enabledPlugins"] = filtered_plugin_list
    elif isinstance(plugins_raw, dict):
        filtered_plugin_map: dict[str, bool] = {}
        for plugin, enabled in plugins_raw.items():
            plugin_ref = str(plugin)
            blocked_by = matches_blocked_plugin(plugin_ref, blocked_plugins)
            if blocked_by:
                skips.append(
                    ProfilePolicySkip(
                        item=plugin_ref,
                        reason=f"blocked by org policy ({blocked_by})",
                        target_type=TargetType.PLUGIN,
                    )
                )
                continue
            filtered_plugin_map[plugin_ref] = bool(enabled)
        filtered["enabledPlugins"] = filtered_plugin_map

    return filtered, skips


def filter_personal_profile_mcp(
    personal_mcp: dict[str, Any],
    org_config: dict[str, Any],
) -> tuple[dict[str, Any], list[ProfilePolicySkip]]:
    """Filter personal profile MCP servers against org security blocks."""
    if not personal_mcp:
        return personal_mcp, []

    security = org_config.get("security", {})
    blocked_mcp_servers = security.get("blocked_mcp_servers", [])
    servers_raw = personal_mcp.get("mcpServers")
    if not isinstance(servers_raw, dict):
        return personal_mcp, []

    skips: list[ProfilePolicySkip] = []
    filtered_servers: dict[str, Any] = {}

    for name, server in servers_raw.items():
        server_dict = dict(server) if isinstance(server, dict) else {}
        server_dict.setdefault("name", str(name))
        blocked_by = match_blocked_mcp(server_dict, blocked_mcp_servers)
        if blocked_by:
            skips.append(
                ProfilePolicySkip(
                    item=str(name),
                    reason=f"blocked by org policy ({blocked_by})",
                    target_type=TargetType.MCP_SERVER,
                )
            )
            continue

        if server_dict.get("type") == MCPServerType.STDIO:
            stdio_result = validate_stdio_server(server_dict, org_config)
            if stdio_result.blocked:
                skips.append(
                    ProfilePolicySkip(
                        item=str(name),
                        reason=stdio_result.reason,
                        target_type=TargetType.MCP_SERVER,
                    )
                )
                continue

        filtered_servers[str(name)] = server

    filtered = dict(personal_mcp)
    filtered["mcpServers"] = filtered_servers
    if not filtered_servers and set(filtered.keys()) == {"mcpServers"}:
        return {}, skips
    return filtered, skips
