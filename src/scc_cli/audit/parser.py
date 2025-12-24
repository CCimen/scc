"""Provide pure functions for parsing plugin manifest files.

Implement parsing logic for:
- .mcp.json files (MCP server definitions)
- hooks/hooks.json files (hook definitions)

All functions are pure (no I/O) - file reading is handled elsewhere.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scc_cli.models.plugin_audit import (
    HookInfo,
    ManifestResult,
    ManifestStatus,
    MCPServerInfo,
    ParseError,
    PluginManifests,
)


def parse_json_content(content: str) -> ManifestResult:
    """Parse JSON content string into a ManifestResult.

    Args:
        content: Raw JSON string to parse.

    Returns:
        ManifestResult with PARSED status if valid JSON,
        or MALFORMED status with error details if invalid.
    """
    try:
        parsed = json.loads(content)
        return ManifestResult(
            status=ManifestStatus.PARSED,
            content=parsed,
        )
    except json.JSONDecodeError as e:
        return ManifestResult(
            status=ManifestStatus.MALFORMED,
            error=ParseError.from_json_error(e),
        )


def parse_mcp_content(content: dict[str, Any]) -> list[MCPServerInfo]:
    """Extract MCP server information from parsed .mcp.json content.

    Args:
        content: Parsed JSON content from .mcp.json file.

    Returns:
        List of MCPServerInfo objects for each declared server.
    """
    servers: list[MCPServerInfo] = []
    mcp_servers = content.get("mcpServers", {})

    for name, config in mcp_servers.items():
        if not isinstance(config, dict):
            continue

        # Default transport is 'stdio' when not specified
        transport = config.get("transport", "stdio")

        servers.append(
            MCPServerInfo(
                name=name,
                transport=transport,
                command=config.get("command"),
                url=config.get("url"),
                description=config.get("description"),
            )
        )

    return servers


def parse_hooks_content(content: dict[str, Any]) -> list[HookInfo]:
    """Extract hook information from parsed hooks.json content.

    Args:
        content: Parsed JSON content from hooks.json file.

    Returns:
        List of HookInfo objects for each declared hook.
    """
    hooks_list: list[HookInfo] = []
    hooks_config = content.get("hooks", {})

    for event, event_hooks in hooks_config.items():
        if not isinstance(event_hooks, list):
            continue

        for hook_group in event_hooks:
            if not isinstance(hook_group, dict):
                continue

            matcher = hook_group.get("matcher")
            hooks = hook_group.get("hooks", [])

            if not isinstance(hooks, list):
                continue

            for hook in hooks:
                if not isinstance(hook, dict):
                    continue

                hook_type = hook.get("type", "unknown")
                hooks_list.append(
                    HookInfo(
                        event=event,
                        hook_type=hook_type,
                        matcher=matcher,
                    )
                )

    return hooks_list


def create_missing_result(path: Path) -> ManifestResult:
    """Create a ManifestResult for a missing manifest file.

    Args:
        path: Relative path where manifest was expected.

    Returns:
        ManifestResult with MISSING status.
    """
    return ManifestResult(
        status=ManifestStatus.MISSING,
        path=path,
    )


def create_unreadable_result(path: Path, error_message: str) -> ManifestResult:
    """Create a ManifestResult for an unreadable manifest file.

    Args:
        path: Relative path to the manifest file.
        error_message: Description of the read error.

    Returns:
        ManifestResult with UNREADABLE status.
    """
    return ManifestResult(
        status=ManifestStatus.UNREADABLE,
        path=path,
        error_message=error_message,
    )


def create_parsed_result(path: Path, content: dict[str, Any]) -> ManifestResult:
    """Create a ManifestResult for a successfully parsed manifest.

    Args:
        path: Relative path to the manifest file.
        content: Parsed JSON content.

    Returns:
        ManifestResult with PARSED status.
    """
    return ManifestResult(
        status=ManifestStatus.PARSED,
        path=path,
        content=content,
    )


def create_plugin_manifests(
    mcp_result: ManifestResult,
    hooks_result: ManifestResult,
    plugin_json_result: ManifestResult | None = None,
) -> PluginManifests:
    """Create a PluginManifests aggregate from individual manifest results.

    Args:
        mcp_result: Result of parsing .mcp.json.
        hooks_result: Result of parsing hooks/hooks.json.
        plugin_json_result: Optional result of parsing .claude-plugin/plugin.json.

    Returns:
        PluginManifests containing all manifest results.
    """
    return PluginManifests(
        mcp=mcp_result,
        hooks=hooks_result,
        plugin_json=plugin_json_result,
    )
