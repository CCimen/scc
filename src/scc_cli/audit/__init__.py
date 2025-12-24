"""Provide plugin audit module for SCC.

Expose functionality for auditing Claude Code plugins,
including manifest parsing, file reading, and plugin discovery.
"""

from scc_cli.audit.parser import (
    create_missing_result,
    create_parsed_result,
    create_plugin_manifests,
    create_unreadable_result,
    parse_hooks_content,
    parse_json_content,
    parse_mcp_content,
)
from scc_cli.audit.reader import (
    audit_all_plugins,
    audit_plugin,
    discover_installed_plugins,
    read_plugin_manifests,
)

__all__ = [
    # Parser functions
    "create_missing_result",
    "create_parsed_result",
    "create_plugin_manifests",
    "create_unreadable_result",
    "parse_hooks_content",
    "parse_json_content",
    "parse_mcp_content",
    # Reader functions
    "audit_all_plugins",
    "audit_plugin",
    "discover_installed_plugins",
    "read_plugin_manifests",
]
