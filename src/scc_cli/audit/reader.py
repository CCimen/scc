"""Provide I/O layer for reading plugin manifests and discovering installed plugins.

Implement file system operations for:
- Reading manifest files from plugin directories
- Discovering installed plugins from the Claude Code registry
- Creating audit results for plugins
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from scc_cli.audit.parser import (
    create_missing_result,
    create_parsed_result,
    create_plugin_manifests,
    create_unreadable_result,
    parse_json_content,
)
from scc_cli.models.plugin_audit import (
    AuditOutput,
    ManifestResult,
    ManifestStatus,
    PluginAuditResult,
    PluginManifests,
)

logger = logging.getLogger(__name__)


def read_manifest_file(plugin_dir: Path, relative_path: Path) -> ManifestResult:
    """Read and parse a manifest file from a plugin directory.

    Args:
        plugin_dir: Absolute path to the plugin directory.
        relative_path: Relative path to the manifest file within the plugin.

    Returns:
        ManifestResult with appropriate status based on file existence,
        readability, and JSON validity.
    """
    full_path = plugin_dir / relative_path

    if not full_path.exists():
        return create_missing_result(relative_path)

    try:
        content = full_path.read_text(encoding="utf-8")
    except PermissionError as e:
        return create_unreadable_result(relative_path, str(e))
    except UnicodeDecodeError as e:
        return create_unreadable_result(relative_path, f"invalid encoding: {e}")
    except OSError as e:
        return create_unreadable_result(relative_path, str(e))

    # Parse the JSON content
    result = parse_json_content(content)

    # Add the path to the result
    if result.status == ManifestStatus.PARSED:
        return create_parsed_result(relative_path, result.content)  # type: ignore[arg-type]
    elif result.status == ManifestStatus.MALFORMED:
        return ManifestResult(
            status=ManifestStatus.MALFORMED,
            path=relative_path,
            error=result.error,
        )
    else:
        return result


def read_plugin_manifests(plugin_dir: Path) -> PluginManifests:
    """Read all manifest files from a plugin directory.

    Args:
        plugin_dir: Absolute path to the plugin directory.

    Returns:
        PluginManifests containing results for all manifest files.
    """
    mcp_result = read_manifest_file(plugin_dir, Path(".mcp.json"))
    hooks_result = read_manifest_file(plugin_dir, Path("hooks/hooks.json"))

    return create_plugin_manifests(mcp_result, hooks_result)


def discover_installed_plugins(claude_dir: Path) -> list[dict[str, Any]]:
    """Discover installed plugins from the Claude Code registry.

    Args:
        claude_dir: Path to the .claude directory (typically ~/.claude).

    Returns:
        List of plugin info dictionaries from installed_plugins.json.
        Returns empty list if registry doesn't exist or is malformed.
    """
    registry_path = claude_dir / "plugins" / "installed_plugins.json"

    if not registry_path.exists():
        return []

    try:
        content = registry_path.read_text(encoding="utf-8")
        data = json.loads(content)
        items: list[dict[str, Any]] = data.get("items", [])
        return items
    except (PermissionError, OSError) as e:
        logger.warning("Cannot read plugin registry: %s", e)
        return []
    except json.JSONDecodeError as e:
        logger.warning("Plugin registry is malformed: %s", e)
        return []


def audit_plugin(plugin_info: dict[str, Any]) -> PluginAuditResult:
    """Audit a single plugin based on its registry information.

    Args:
        plugin_info: Plugin info dictionary from installed_plugins.json.

    Returns:
        PluginAuditResult with manifest parsing results.
    """
    name = plugin_info.get("name", "unknown")
    marketplace = plugin_info.get("marketplace", "unknown")
    version = plugin_info.get("version", "unknown")
    install_path_str = plugin_info.get("installPath", "")

    plugin_id = f"{name}@{marketplace}"
    # Type-safe path creation: only convert if it's a non-empty string
    install_path = (
        Path(install_path_str) if isinstance(install_path_str, str) and install_path_str else None
    )

    # Check if plugin directory exists
    if install_path is None or not install_path.exists():
        return PluginAuditResult(
            plugin_id=plugin_id,
            plugin_name=name,
            marketplace=marketplace,
            version=version,
            install_path=install_path,
            installed=False,
            manifests=None,
        )

    # Read manifests from the plugin directory
    manifests = read_plugin_manifests(install_path)

    return PluginAuditResult(
        plugin_id=plugin_id,
        plugin_name=name,
        marketplace=marketplace,
        version=version,
        install_path=install_path,
        installed=True,
        manifests=manifests,
    )


def audit_all_plugins(claude_dir: Path) -> AuditOutput:
    """Audit all installed plugins.

    Args:
        claude_dir: Path to the .claude directory.

    Returns:
        AuditOutput with results for all plugins.
    """
    plugins = discover_installed_plugins(claude_dir)
    results = [audit_plugin(plugin) for plugin in plugins]

    return AuditOutput(
        schema_version=1,
        plugins=results,
        warnings=[],
    )
