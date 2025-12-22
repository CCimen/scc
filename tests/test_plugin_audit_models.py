"""Tests for plugin audit data models.

Tests the data models for the plugin audit feature including
ManifestStatus, ManifestResult, PluginManifests, and AuditOutput.
"""

from __future__ import annotations

import json
from pathlib import Path

from scc_cli.models.plugin_audit import (
    AuditOutput,
    HookInfo,
    ManifestResult,
    ManifestStatus,
    MCPServerInfo,
    ParseError,
    PluginAuditResult,
    PluginManifests,
)


class TestManifestStatus:
    """Tests for ManifestStatus enum."""

    def test_status_values(self) -> None:
        """Test that all expected status values exist."""
        assert ManifestStatus.PARSED.value == "parsed"
        assert ManifestStatus.MISSING.value == "missing"
        assert ManifestStatus.UNREADABLE.value == "unreadable"
        assert ManifestStatus.MALFORMED.value == "malformed"

    def test_status_is_string_enum(self) -> None:
        """Test that status values are strings for JSON serialization."""
        for status in ManifestStatus:
            assert isinstance(status.value, str)


class TestParseError:
    """Tests for ParseError dataclass."""

    def test_basic_error(self) -> None:
        """Test creating a basic parse error."""
        error = ParseError(message="Unexpected token")
        assert error.message == "Unexpected token"
        assert error.line is None
        assert error.column is None

    def test_error_with_location(self) -> None:
        """Test creating an error with line/column info."""
        error = ParseError(message="Expected ','", line=15, column=8)
        assert error.message == "Expected ','"
        assert error.line == 15
        assert error.column == 8

    def test_from_json_error(self) -> None:
        """Test creating ParseError from JSONDecodeError."""
        try:
            json.loads('{"key": "value",}')  # Trailing comma
        except json.JSONDecodeError as e:
            error = ParseError.from_json_error(e)
            assert error.message is not None
            assert error.line is not None
            # JSONDecodeError provides position info

    def test_format_with_full_location(self) -> None:
        """Test formatting error with line and column."""
        error = ParseError(message="Expected ',' but found '}'", line=15, column=8)
        formatted = error.format()
        assert formatted == "line 15, col 8: Expected ',' but found '}'"

    def test_format_with_line_only(self) -> None:
        """Test formatting error with line only."""
        error = ParseError(message="Unexpected EOF", line=42)
        formatted = error.format()
        assert formatted == "line 42: Unexpected EOF"

    def test_format_without_location(self) -> None:
        """Test formatting error without location info."""
        error = ParseError(message="Parse failed")
        formatted = error.format()
        assert formatted == "Parse failed"


class TestManifestResult:
    """Tests for ManifestResult dataclass."""

    def test_parsed_manifest(self) -> None:
        """Test a successfully parsed manifest."""
        content = {"mcpServers": {"test": {"command": "test"}}}
        result = ManifestResult(
            status=ManifestStatus.PARSED,
            path=Path(".mcp.json"),
            content=content,
        )
        assert result.status == ManifestStatus.PARSED
        assert result.content == content
        assert result.is_ok
        assert not result.has_problems

    def test_missing_manifest(self) -> None:
        """Test a missing manifest (clean state)."""
        result = ManifestResult(
            status=ManifestStatus.MISSING,
            path=Path(".mcp.json"),
        )
        assert result.status == ManifestStatus.MISSING
        assert result.content is None
        assert result.is_ok  # Missing is OK - plugin just doesn't have one
        assert not result.has_problems

    def test_unreadable_manifest(self) -> None:
        """Test an unreadable manifest (permission error)."""
        result = ManifestResult(
            status=ManifestStatus.UNREADABLE,
            path=Path(".mcp.json"),
            error_message="Permission denied",
        )
        assert result.status == ManifestStatus.UNREADABLE
        assert not result.is_ok
        assert result.has_problems

    def test_malformed_manifest(self) -> None:
        """Test a malformed manifest (parse error)."""
        error = ParseError(message="Unexpected token", line=5, column=12)
        result = ManifestResult(
            status=ManifestStatus.MALFORMED,
            path=Path(".mcp.json"),
            error=error,
        )
        assert result.status == ManifestStatus.MALFORMED
        assert result.error == error
        assert not result.is_ok
        assert result.has_problems


class TestMCPServerInfo:
    """Tests for MCPServerInfo dataclass."""

    def test_stdio_server(self) -> None:
        """Test a stdio-type MCP server."""
        server = MCPServerInfo(
            name="my-server",
            transport="stdio",
            command="bunx server",
            description="Test server",
        )
        assert server.name == "my-server"
        assert server.transport == "stdio"
        assert server.command == "bunx server"
        assert server.url is None
        assert server.description == "Test server"

    def test_http_server(self) -> None:
        """Test an HTTP-type MCP server."""
        server = MCPServerInfo(
            name="remote-server",
            transport="http",
            url="https://mcp.example.com",
        )
        assert server.transport == "http"
        assert server.url == "https://mcp.example.com"
        assert server.command is None


class TestHookInfo:
    """Tests for HookInfo dataclass."""

    def test_hook_with_matcher(self) -> None:
        """Test a hook with matcher pattern."""
        hook = HookInfo(
            event="PostToolUse",
            hook_type="command",
            matcher="Write|Edit",
        )
        assert hook.event == "PostToolUse"
        assert hook.hook_type == "command"
        assert hook.matcher == "Write|Edit"

    def test_hook_without_matcher(self) -> None:
        """Test a hook without matcher."""
        hook = HookInfo(event="SessionStart", hook_type="prompt")
        assert hook.matcher is None


class TestPluginManifests:
    """Tests for PluginManifests dataclass."""

    def test_clean_plugin(self) -> None:
        """Test a clean plugin with no declarations."""
        manifests = PluginManifests(
            mcp=ManifestResult(status=ManifestStatus.MISSING),
            hooks=ManifestResult(status=ManifestStatus.MISSING),
        )
        assert not manifests.has_declarations
        assert not manifests.has_problems
        assert manifests.mcp_servers == []
        assert manifests.hooks_info == []

    def test_plugin_with_mcp(self) -> None:
        """Test a plugin with MCP server declarations."""
        mcp_content = {
            "mcpServers": {
                "svelte": {"url": "https://mcp.svelte.dev", "transport": "http"},
                "sequential": {"command": "bunx server", "transport": "stdio"},
            }
        }
        manifests = PluginManifests(
            mcp=ManifestResult(
                status=ManifestStatus.PARSED,
                path=Path(".mcp.json"),
                content=mcp_content,
            ),
            hooks=ManifestResult(status=ManifestStatus.MISSING),
        )
        assert manifests.has_declarations
        assert not manifests.has_problems
        assert len(manifests.mcp_servers) == 2

        servers = {s.name: s for s in manifests.mcp_servers}
        assert "svelte" in servers
        assert servers["svelte"].transport == "http"
        assert servers["svelte"].url == "https://mcp.svelte.dev"
        assert "sequential" in servers
        assert servers["sequential"].transport == "stdio"
        assert servers["sequential"].command == "bunx server"

    def test_plugin_with_hooks(self) -> None:
        """Test a plugin with hook declarations."""
        hooks_content = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Write|Edit",
                        "hooks": [{"type": "command", "command": "./format.sh"}],
                    }
                ],
                "SessionStart": [{"hooks": [{"type": "prompt", "prompt": "Welcome"}]}],
            }
        }
        manifests = PluginManifests(
            mcp=ManifestResult(status=ManifestStatus.MISSING),
            hooks=ManifestResult(
                status=ManifestStatus.PARSED,
                path=Path("hooks/hooks.json"),
                content=hooks_content,
            ),
        )
        assert manifests.has_declarations
        assert len(manifests.hooks_info) == 2

        hooks = manifests.hooks_info
        post_tool = next(h for h in hooks if h.event == "PostToolUse")
        assert post_tool.hook_type == "command"
        assert post_tool.matcher == "Write|Edit"

        session_start = next(h for h in hooks if h.event == "SessionStart")
        assert session_start.hook_type == "prompt"
        assert session_start.matcher is None

    def test_plugin_with_malformed_mcp(self) -> None:
        """Test a plugin with malformed MCP manifest."""
        manifests = PluginManifests(
            mcp=ManifestResult(
                status=ManifestStatus.MALFORMED,
                path=Path(".mcp.json"),
                error=ParseError(message="Unexpected token", line=5, column=12),
            ),
            hooks=ManifestResult(status=ManifestStatus.MISSING),
        )
        assert manifests.has_problems
        assert manifests.mcp_servers == []  # Can't extract from malformed


class TestPluginAuditResult:
    """Tests for PluginAuditResult dataclass."""

    def test_installed_clean_plugin(self) -> None:
        """Test an installed plugin with no declarations."""
        result = PluginAuditResult(
            plugin_id="test-plugin@my-marketplace",
            plugin_name="test-plugin",
            marketplace="my-marketplace",
            version="1.0.0",
            install_path=Path.home() / ".claude/plugins/cache/my-marketplace/test-plugin/1.0.0",
            installed=True,
            manifests=PluginManifests(
                mcp=ManifestResult(status=ManifestStatus.MISSING),
                hooks=ManifestResult(status=ManifestStatus.MISSING),
            ),
        )
        assert result.status_summary == "clean"
        assert not result.has_ci_failures

    def test_installed_plugin_with_parsed_manifests(self) -> None:
        """Test an installed plugin with parsed manifests."""
        result = PluginAuditResult(
            plugin_id="mcp-plugin@marketplace",
            plugin_name="mcp-plugin",
            marketplace="marketplace",
            version="2.0.0",
            installed=True,
            manifests=PluginManifests(
                mcp=ManifestResult(
                    status=ManifestStatus.PARSED,
                    content={"mcpServers": {}},
                ),
                hooks=ManifestResult(status=ManifestStatus.MISSING),
            ),
        )
        assert result.status_summary == "parsed"
        assert not result.has_ci_failures

    def test_not_installed_plugin(self) -> None:
        """Test a plugin that is not installed."""
        result = PluginAuditResult(
            plugin_id="missing@marketplace",
            plugin_name="missing",
            marketplace="marketplace",
            version="1.0.0",
            installed=False,
        )
        assert result.status_summary == "not installed"
        assert not result.has_ci_failures

    def test_plugin_with_malformed_manifest(self) -> None:
        """Test a plugin with malformed manifest causes CI failure."""
        result = PluginAuditResult(
            plugin_id="broken@marketplace",
            plugin_name="broken",
            marketplace="marketplace",
            version="1.0.0",
            installed=True,
            manifests=PluginManifests(
                mcp=ManifestResult(
                    status=ManifestStatus.MALFORMED,
                    error=ParseError(message="error", line=1, column=1),
                ),
                hooks=ManifestResult(status=ManifestStatus.MISSING),
            ),
        )
        assert result.status_summary == "malformed"
        assert result.has_ci_failures

    def test_plugin_with_unreadable_manifest(self) -> None:
        """Test a plugin with unreadable manifest causes CI failure."""
        result = PluginAuditResult(
            plugin_id="locked@marketplace",
            plugin_name="locked",
            marketplace="marketplace",
            version="1.0.0",
            installed=True,
            manifests=PluginManifests(
                mcp=ManifestResult(
                    status=ManifestStatus.UNREADABLE,
                    error_message="Permission denied",
                ),
                hooks=ManifestResult(status=ManifestStatus.MISSING),
            ),
        )
        assert result.status_summary == "unreadable"
        assert result.has_ci_failures


class TestAuditOutput:
    """Tests for AuditOutput dataclass."""

    def test_empty_output(self) -> None:
        """Test empty audit output."""
        output = AuditOutput()
        assert output.schema_version == 1
        assert output.total_plugins == 0
        assert output.clean_count == 0
        assert output.parsed_count == 0
        assert output.problem_count == 0
        assert not output.has_ci_failures
        assert output.exit_code == 0

    def test_all_clean_plugins(self) -> None:
        """Test output with all clean plugins."""
        output = AuditOutput(
            plugins=[
                PluginAuditResult(
                    plugin_id="p1@m",
                    plugin_name="p1",
                    marketplace="m",
                    version="1.0.0",
                    installed=True,
                    manifests=PluginManifests(
                        mcp=ManifestResult(status=ManifestStatus.MISSING),
                        hooks=ManifestResult(status=ManifestStatus.MISSING),
                    ),
                ),
                PluginAuditResult(
                    plugin_id="p2@m",
                    plugin_name="p2",
                    marketplace="m",
                    version="1.0.0",
                    installed=True,
                    manifests=PluginManifests(
                        mcp=ManifestResult(status=ManifestStatus.MISSING),
                        hooks=ManifestResult(status=ManifestStatus.MISSING),
                    ),
                ),
            ]
        )
        assert output.total_plugins == 2
        assert output.clean_count == 2
        assert output.parsed_count == 0
        assert output.exit_code == 0

    def test_mixed_plugins(self) -> None:
        """Test output with mixed plugin states."""
        output = AuditOutput(
            plugins=[
                # Clean plugin
                PluginAuditResult(
                    plugin_id="clean@m",
                    plugin_name="clean",
                    marketplace="m",
                    version="1.0.0",
                    installed=True,
                    manifests=PluginManifests(
                        mcp=ManifestResult(status=ManifestStatus.MISSING),
                        hooks=ManifestResult(status=ManifestStatus.MISSING),
                    ),
                ),
                # Parsed plugin
                PluginAuditResult(
                    plugin_id="parsed@m",
                    plugin_name="parsed",
                    marketplace="m",
                    version="1.0.0",
                    installed=True,
                    manifests=PluginManifests(
                        mcp=ManifestResult(
                            status=ManifestStatus.PARSED,
                            content={"mcpServers": {}},
                        ),
                        hooks=ManifestResult(status=ManifestStatus.MISSING),
                    ),
                ),
                # Malformed plugin
                PluginAuditResult(
                    plugin_id="broken@m",
                    plugin_name="broken",
                    marketplace="m",
                    version="1.0.0",
                    installed=True,
                    manifests=PluginManifests(
                        mcp=ManifestResult(
                            status=ManifestStatus.MALFORMED,
                            error=ParseError(message="error"),
                        ),
                        hooks=ManifestResult(status=ManifestStatus.MISSING),
                    ),
                ),
            ]
        )
        assert output.total_plugins == 3
        assert output.clean_count == 1
        assert output.parsed_count == 1
        assert output.problem_count == 1
        assert output.has_ci_failures
        assert output.exit_code == 1

    def test_to_dict(self) -> None:
        """Test JSON serialization."""
        output = AuditOutput(
            plugins=[
                PluginAuditResult(
                    plugin_id="test@marketplace",
                    plugin_name="test",
                    marketplace="marketplace",
                    version="1.0.0",
                    install_path=Path.home() / ".claude/plugins/cache/marketplace/test/1.0.0",
                    installed=True,
                    manifests=PluginManifests(
                        mcp=ManifestResult(
                            status=ManifestStatus.PARSED,
                            path=Path(".mcp.json"),
                            content={
                                "mcpServers": {
                                    "server1": {
                                        "command": "test",
                                        "transport": "stdio",
                                        "description": "Test server",
                                    }
                                }
                            },
                        ),
                        hooks=ManifestResult(status=ManifestStatus.MISSING),
                    ),
                ),
            ],
            warnings=["Some warning"],
        )

        result = output.to_dict()

        assert result["schemaVersion"] == 1
        assert result["summary"]["total"] == 1
        assert result["summary"]["parsed"] == 1
        assert len(result["plugins"]) == 1
        assert result["warnings"] == ["Some warning"]

        plugin = result["plugins"][0]
        assert plugin["pluginId"] == "test@marketplace"
        assert plugin["name"] == "test"
        assert plugin["marketplace"] == "marketplace"
        assert plugin["version"] == "1.0.0"
        assert plugin["installed"] is True
        assert plugin["status"] == "parsed"
        # Path should be relative to home
        assert plugin["installPath"] == ".claude/plugins/cache/marketplace/test/1.0.0"
        assert plugin["manifests"]["mcp"]["status"] == "parsed"
        assert plugin["manifests"]["hooks"]["status"] == "missing"
        assert len(plugin["mcpServers"]) == 1
        assert plugin["mcpServers"][0]["name"] == "server1"
        assert plugin["mcpServers"][0]["transport"] == "stdio"

    def test_to_dict_with_malformed_error(self) -> None:
        """Test JSON serialization includes error details."""
        output = AuditOutput(
            plugins=[
                PluginAuditResult(
                    plugin_id="broken@m",
                    plugin_name="broken",
                    marketplace="m",
                    version="1.0.0",
                    installed=True,
                    manifests=PluginManifests(
                        mcp=ManifestResult(
                            status=ManifestStatus.MALFORMED,
                            path=Path(".mcp.json"),
                            error=ParseError(
                                message="Expected ',' but found '}'",
                                line=15,
                                column=8,
                            ),
                        ),
                        hooks=ManifestResult(status=ManifestStatus.MISSING),
                    ),
                ),
            ]
        )

        result = output.to_dict()
        mcp = result["plugins"][0]["manifests"]["mcp"]
        assert mcp["status"] == "malformed"
        assert mcp["path"] == ".mcp.json"
        assert mcp["error"] == "line 15, col 8: Expected ',' but found '}'"

    def test_json_serializable(self) -> None:
        """Test that to_dict output is JSON serializable."""
        output = AuditOutput(
            plugins=[
                PluginAuditResult(
                    plugin_id="test@m",
                    plugin_name="test",
                    marketplace="m",
                    version="1.0.0",
                    installed=True,
                    manifests=PluginManifests(
                        mcp=ManifestResult(status=ManifestStatus.MISSING),
                        hooks=ManifestResult(status=ManifestStatus.MISSING),
                    ),
                ),
            ]
        )

        # Should not raise
        json_str = json.dumps(output.to_dict(), indent=2)
        assert isinstance(json_str, str)

        # Should round-trip
        parsed = json.loads(json_str)
        assert parsed["schemaVersion"] == 1
