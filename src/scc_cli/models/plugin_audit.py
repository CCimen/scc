"""Define data models for plugin audit feature.

Provide models for auditing Claude Code plugins, including manifest
parsing results and status reporting.

The audit feature gives visibility into plugin components (MCP servers,
hooks) without enforcing any policies.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ManifestStatus(str, Enum):
    """Status of a manifest file parsing attempt."""

    PARSED = "parsed"
    """Manifest found and successfully parsed."""

    MISSING = "missing"
    """Manifest file not found at expected location."""

    UNREADABLE = "unreadable"
    """Manifest exists but cannot be read (permission error)."""

    MALFORMED = "malformed"
    """Manifest exists but contains invalid JSON."""


@dataclass
class ParseError:
    """Details of a JSON parse error with location info."""

    message: str
    """Human-readable error message."""

    line: int | None = None
    """Line number where error occurred (1-indexed), if available."""

    column: int | None = None
    """Column number where error occurred (1-indexed), if available."""

    @classmethod
    def from_json_error(cls, error: json.JSONDecodeError) -> ParseError:
        """Create ParseError from a JSONDecodeError.

        Args:
            error: The JSON decode error with position info.

        Returns:
            ParseError with line/column if available.
        """
        return cls(
            message=error.msg,
            line=error.lineno,
            column=error.colno,
        )

    def format(self) -> str:
        """Format error for display.

        Returns:
            Formatted string like "line 15, col 8: Expected ',' but found '}'"
        """
        if self.line is not None and self.column is not None:
            return f"line {self.line}, col {self.column}: {self.message}"
        elif self.line is not None:
            return f"line {self.line}: {self.message}"
        else:
            return self.message


@dataclass
class ManifestResult:
    """Result of parsing a single manifest file."""

    status: ManifestStatus
    """The parsing status."""

    path: Path | None = None
    """Path to the manifest file (relative to plugin root)."""

    content: dict[str, Any] | None = None
    """Parsed content if status is PARSED."""

    error: ParseError | None = None
    """Parse error details if status is MALFORMED."""

    error_message: str | None = None
    """Raw error message for UNREADABLE status."""

    @property
    def is_ok(self) -> bool:
        """Check if manifest was successfully parsed or is cleanly missing.

        Returns:
            True if status is PARSED or MISSING (clean states).
        """
        return self.status in (ManifestStatus.PARSED, ManifestStatus.MISSING)

    @property
    def has_problems(self) -> bool:
        """Check if manifest has problems that should fail CI.

        Returns:
            True if status is MALFORMED or UNREADABLE.
        """
        return self.status in (ManifestStatus.MALFORMED, ManifestStatus.UNREADABLE)


@dataclass
class MCPServerInfo:
    """Extracted information about an MCP server from manifest."""

    name: str
    """Server name/identifier."""

    transport: str
    """Transport type: 'stdio', 'http', 'sse', etc."""

    command: str | None = None
    """Command to run (for stdio transport)."""

    url: str | None = None
    """URL (for http/sse transport)."""

    description: str | None = None
    """Server description if provided."""


@dataclass
class HookInfo:
    """Extracted information about a hook from manifest."""

    event: str
    """Event type: 'PreToolUse', 'PostToolUse', etc."""

    hook_type: str
    """Hook type: 'command', 'prompt', 'agent'."""

    matcher: str | None = None
    """Matcher pattern if specified."""


@dataclass
class PluginManifests:
    """Aggregated manifest information for a plugin."""

    mcp: ManifestResult
    """Result of parsing .mcp.json."""

    hooks: ManifestResult
    """Result of parsing hooks/hooks.json or inline hooks."""

    plugin_json: ManifestResult | None = None
    """Result of parsing .claude-plugin/plugin.json (optional)."""

    @property
    def has_declarations(self) -> bool:
        """Check if plugin has any component declarations.

        Returns:
            True if MCP or hooks manifests exist and are parsed.
        """
        return (
            self.mcp.status == ManifestStatus.PARSED or self.hooks.status == ManifestStatus.PARSED
        )

    @property
    def has_problems(self) -> bool:
        """Check if any manifest has problems.

        Returns:
            True if any manifest is MALFORMED or UNREADABLE.
        """
        return self.mcp.has_problems or self.hooks.has_problems

    @property
    def mcp_servers(self) -> list[MCPServerInfo]:
        """Extract MCP server info from parsed manifest.

        Returns:
            List of MCPServerInfo from .mcp.json content.
        """
        if self.mcp.status != ManifestStatus.PARSED or self.mcp.content is None:
            return []

        servers = []
        mcp_servers = self.mcp.content.get("mcpServers", {})
        if not isinstance(mcp_servers, dict):
            return []
        for name, config in mcp_servers.items():
            if not isinstance(config, dict):
                continue
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

    @property
    def hooks_info(self) -> list[HookInfo]:
        """Extract hook info from parsed manifest.

        Returns:
            List of HookInfo from hooks content.
        """
        if self.hooks.status != ManifestStatus.PARSED or self.hooks.content is None:
            return []

        hooks_list = []
        hooks_config = self.hooks.content.get("hooks", {})
        if not isinstance(hooks_config, dict):
            return []
        for event, event_hooks in hooks_config.items():
            if isinstance(event_hooks, list):
                for hook_group in event_hooks:
                    matcher = hook_group.get("matcher")
                    for hook in hook_group.get("hooks", []):
                        hooks_list.append(
                            HookInfo(
                                event=event,
                                hook_type=hook.get("type", "unknown"),
                                matcher=matcher,
                            )
                        )
        return hooks_list


@dataclass
class PluginAuditResult:
    """Full audit result for a single plugin."""

    plugin_id: str
    """Plugin identifier in format 'name@marketplace'."""

    plugin_name: str
    """Plugin name (without marketplace)."""

    marketplace: str
    """Marketplace name."""

    version: str
    """Installed version."""

    install_path: Path | None = None
    """Absolute path to installed plugin, if installed."""

    installed: bool = False
    """Whether the plugin is currently installed."""

    manifests: PluginManifests | None = None
    """Manifest parsing results, if installed."""

    @property
    def status_summary(self) -> str:
        """Get a summary status for the plugin.

        Returns:
            Summary string: 'clean', 'parsed', 'malformed', 'unreadable', 'not installed'
        """
        if not self.installed:
            return "not installed"

        if self.manifests is None:
            return "unknown"

        if self.manifests.has_problems:
            # Report the worst status
            if self.manifests.mcp.status == ManifestStatus.MALFORMED:
                return "malformed"
            if self.manifests.hooks.status == ManifestStatus.MALFORMED:
                return "malformed"
            return "unreadable"

        if self.manifests.has_declarations:
            return "parsed"

        return "clean"

    @property
    def has_ci_failures(self) -> bool:
        """Check if this plugin should cause CI failure.

        Returns:
            True if any manifest is malformed or unreadable.
        """
        if self.manifests is None:
            return False
        return self.manifests.has_problems


@dataclass
class AuditOutput:
    """Overall audit output for all plugins."""

    schema_version: int = 1
    """Schema version for JSON output."""

    plugins: list[PluginAuditResult] = field(default_factory=list)
    """Results for each audited plugin."""

    warnings: list[str] = field(default_factory=list)
    """Warning messages (non-fatal issues)."""

    @property
    def total_plugins(self) -> int:
        """Total number of plugins audited."""
        return len(self.plugins)

    @property
    def clean_count(self) -> int:
        """Number of clean plugins (no declarations)."""
        return sum(1 for p in self.plugins if p.status_summary == "clean")

    @property
    def parsed_count(self) -> int:
        """Number of plugins with parsed manifests."""
        return sum(1 for p in self.plugins if p.status_summary == "parsed")

    @property
    def problem_count(self) -> int:
        """Number of plugins with problems."""
        return sum(1 for p in self.plugins if p.has_ci_failures)

    @property
    def has_ci_failures(self) -> bool:
        """Check if any plugin should cause CI failure.

        Returns:
            True if any plugin has malformed or unreadable manifests.
        """
        return any(p.has_ci_failures for p in self.plugins)

    @property
    def exit_code(self) -> int:
        """Get CI exit code.

        Returns:
            0 if all plugins OK, 1 if any have problems.
        """
        return 1 if self.has_ci_failures else 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dict with schemaVersion and structured plugin data.
        """
        return {
            "schemaVersion": self.schema_version,
            "summary": {
                "total": self.total_plugins,
                "clean": self.clean_count,
                "parsed": self.parsed_count,
                "problems": self.problem_count,
            },
            "plugins": [self._plugin_to_dict(p) for p in self.plugins],
            "warnings": self.warnings,
        }

    def _plugin_to_dict(self, plugin: PluginAuditResult) -> dict[str, Any]:
        """Convert a single plugin result to dictionary."""
        result: dict[str, Any] = {
            "pluginId": plugin.plugin_id,
            "name": plugin.plugin_name,
            "marketplace": plugin.marketplace,
            "version": plugin.version,
            "installed": plugin.installed,
            "status": plugin.status_summary,
        }

        if plugin.install_path:
            # Use relative path for security (don't leak full paths in CI logs)
            try:
                result["installPath"] = str(plugin.install_path.relative_to(Path.home()))
            except ValueError:
                # Path not under home, use just the name
                result["installPath"] = plugin.install_path.name

        if plugin.manifests:
            result["manifests"] = {
                "mcp": self._manifest_to_dict(plugin.manifests.mcp),
                "hooks": self._manifest_to_dict(plugin.manifests.hooks),
            }

            # Add extracted component info
            if plugin.manifests.mcp_servers:
                result["mcpServers"] = [
                    {
                        "name": s.name,
                        "transport": s.transport,
                        "description": s.description,
                    }
                    for s in plugin.manifests.mcp_servers
                ]

            if plugin.manifests.hooks_info:
                result["hooks"] = [
                    {
                        "event": h.event,
                        "type": h.hook_type,
                        "matcher": h.matcher,
                    }
                    for h in plugin.manifests.hooks_info
                ]

        return result

    def _manifest_to_dict(self, manifest: ManifestResult) -> dict[str, Any]:
        """Convert manifest result to dictionary."""
        result: dict[str, Any] = {"status": manifest.status.value}

        if manifest.path:
            result["path"] = str(manifest.path)

        if manifest.error:
            result["error"] = manifest.error.format()

        if manifest.error_message:
            result["errorMessage"] = manifest.error_message

        return result
