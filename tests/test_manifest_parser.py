"""Tests for manifest parsing logic (TDD red phase).

These tests define the expected behavior for parsing plugin manifests:
- .mcp.json files for MCP server definitions
- hooks/hooks.json files for hook definitions
- Error handling for malformed JSON
"""

from __future__ import annotations

from pathlib import Path

from scc_cli.models.plugin_audit import (
    ManifestResult,
    ManifestStatus,
    ParseError,
)

# Import will fail until we implement the parser
# from scc_cli.audit.parser import parse_json_content


class TestParseJsonContent:
    """Tests for parse_json_content function."""

    def test_valid_json_returns_parsed_status(self) -> None:
        """Valid JSON content should return PARSED status with content."""
        from scc_cli.audit.parser import parse_json_content

        content = '{"key": "value", "number": 42}'
        result = parse_json_content(content)

        assert result.status == ManifestStatus.PARSED
        assert result.content == {"key": "value", "number": 42}
        assert result.error is None

    def test_empty_object_is_valid(self) -> None:
        """Empty JSON object should return PARSED status."""
        from scc_cli.audit.parser import parse_json_content

        result = parse_json_content("{}")

        assert result.status == ManifestStatus.PARSED
        assert result.content == {}

    def test_malformed_json_returns_malformed_status(self) -> None:
        """Invalid JSON should return MALFORMED status with error details."""
        from scc_cli.audit.parser import parse_json_content

        content = '{"key": value}'  # Missing quotes around value
        result = parse_json_content(content)

        assert result.status == ManifestStatus.MALFORMED
        assert result.content is None
        assert result.error is not None
        assert result.error.line is not None
        assert result.error.column is not None

    def test_malformed_json_preserves_error_message(self) -> None:
        """Error message should contain useful information."""
        from scc_cli.audit.parser import parse_json_content

        content = '{"unclosed": ['
        result = parse_json_content(content)

        assert result.status == ManifestStatus.MALFORMED
        assert result.error is not None
        # Error message should be non-empty
        assert len(result.error.message) > 0

    def test_trailing_comma_is_malformed(self) -> None:
        """Trailing commas are invalid JSON."""
        from scc_cli.audit.parser import parse_json_content

        content = '{"key": "value",}'
        result = parse_json_content(content)

        assert result.status == ManifestStatus.MALFORMED

    def test_parse_error_includes_location(self) -> None:
        """Parse errors should include line and column information."""
        from scc_cli.audit.parser import parse_json_content

        # Multi-line JSON with error on line 3
        content = '{\n  "key1": "value1",\n  "key2": invalid\n}'
        result = parse_json_content(content)

        assert result.status == ManifestStatus.MALFORMED
        assert result.error is not None
        assert result.error.line == 3
        # Column should point to 'invalid'
        assert result.error.column is not None


class TestParseMcpManifest:
    """Tests for parsing .mcp.json content structure."""

    def test_extract_stdio_mcp_server(self) -> None:
        """Should extract stdio MCP server details."""
        from scc_cli.audit.parser import parse_mcp_content

        content = {
            "mcpServers": {
                "my-server": {
                    "command": "node",
                    "args": ["server.js"],
                    "description": "My custom server",
                }
            }
        }
        servers = parse_mcp_content(content)

        assert len(servers) == 1
        assert servers[0].name == "my-server"
        assert servers[0].transport == "stdio"
        assert servers[0].command == "node"
        assert servers[0].description == "My custom server"

    def test_extract_http_mcp_server(self) -> None:
        """Should extract HTTP MCP server with URL."""
        from scc_cli.audit.parser import parse_mcp_content

        content = {
            "mcpServers": {
                "api-server": {
                    "transport": "http",
                    "url": "https://api.example.com/mcp",
                }
            }
        }
        servers = parse_mcp_content(content)

        assert len(servers) == 1
        assert servers[0].name == "api-server"
        assert servers[0].transport == "http"
        assert servers[0].url == "https://api.example.com/mcp"

    def test_extract_sse_mcp_server(self) -> None:
        """Should extract SSE MCP server with URL."""
        from scc_cli.audit.parser import parse_mcp_content

        content = {
            "mcpServers": {
                "stream-server": {
                    "transport": "sse",
                    "url": "https://stream.example.com/events",
                }
            }
        }
        servers = parse_mcp_content(content)

        assert len(servers) == 1
        assert servers[0].transport == "sse"
        assert servers[0].url == "https://stream.example.com/events"

    def test_extract_multiple_servers(self) -> None:
        """Should extract all MCP servers from manifest."""
        from scc_cli.audit.parser import parse_mcp_content

        content = {
            "mcpServers": {
                "server-a": {"command": "node", "args": ["a.js"]},
                "server-b": {"command": "python", "args": ["b.py"]},
                "server-c": {"transport": "http", "url": "https://c.example.com"},
            }
        }
        servers = parse_mcp_content(content)

        assert len(servers) == 3
        names = {s.name for s in servers}
        assert names == {"server-a", "server-b", "server-c"}

    def test_empty_mcp_servers_returns_empty_list(self) -> None:
        """Empty mcpServers object should return empty list."""
        from scc_cli.audit.parser import parse_mcp_content

        content = {"mcpServers": {}}
        servers = parse_mcp_content(content)

        assert servers == []

    def test_missing_mcp_servers_key_returns_empty_list(self) -> None:
        """Missing mcpServers key should return empty list."""
        from scc_cli.audit.parser import parse_mcp_content

        content = {"otherKey": "value"}
        servers = parse_mcp_content(content)

        assert servers == []

    def test_default_transport_is_stdio(self) -> None:
        """Default transport should be 'stdio' when not specified."""
        from scc_cli.audit.parser import parse_mcp_content

        content = {"mcpServers": {"my-server": {"command": "node", "args": ["server.js"]}}}
        servers = parse_mcp_content(content)

        assert servers[0].transport == "stdio"


class TestParseHooksManifest:
    """Tests for parsing hooks/hooks.json content structure."""

    def test_extract_pre_tool_use_hook(self) -> None:
        """Should extract PreToolUse hook details."""
        from scc_cli.audit.parser import parse_hooks_content

        content = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [{"type": "command", "command": "validate.sh"}],
                    }
                ]
            }
        }
        hooks = parse_hooks_content(content)

        assert len(hooks) == 1
        assert hooks[0].event == "PreToolUse"
        assert hooks[0].hook_type == "command"
        assert hooks[0].matcher == "Bash"

    def test_extract_post_tool_use_hook(self) -> None:
        """Should extract PostToolUse hook details."""
        from scc_cli.audit.parser import parse_hooks_content

        content = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Write",
                        "hooks": [{"type": "prompt", "prompt": "Review changes"}],
                    }
                ]
            }
        }
        hooks = parse_hooks_content(content)

        assert len(hooks) == 1
        assert hooks[0].event == "PostToolUse"
        assert hooks[0].hook_type == "prompt"

    def test_extract_multiple_hooks_same_event(self) -> None:
        """Should extract all hooks for the same event."""
        from scc_cli.audit.parser import parse_hooks_content

        content = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {"type": "command", "command": "validate.sh"},
                            {"type": "prompt", "prompt": "Check safety"},
                        ],
                    }
                ]
            }
        }
        hooks = parse_hooks_content(content)

        assert len(hooks) == 2
        types = {h.hook_type for h in hooks}
        assert types == {"command", "prompt"}

    def test_extract_hooks_from_multiple_events(self) -> None:
        """Should extract hooks from multiple event types."""
        from scc_cli.audit.parser import parse_hooks_content

        content = {
            "hooks": {
                "PreToolUse": [{"hooks": [{"type": "command", "command": "pre.sh"}]}],
                "PostToolUse": [{"hooks": [{"type": "command", "command": "post.sh"}]}],
                "Stop": [{"hooks": [{"type": "prompt", "prompt": "Final check"}]}],
            }
        }
        hooks = parse_hooks_content(content)

        assert len(hooks) == 3
        events = {h.event for h in hooks}
        assert events == {"PreToolUse", "PostToolUse", "Stop"}

    def test_empty_hooks_returns_empty_list(self) -> None:
        """Empty hooks object should return empty list."""
        from scc_cli.audit.parser import parse_hooks_content

        content = {"hooks": {}}
        hooks = parse_hooks_content(content)

        assert hooks == []

    def test_missing_hooks_key_returns_empty_list(self) -> None:
        """Missing hooks key should return empty list."""
        from scc_cli.audit.parser import parse_hooks_content

        content = {"otherKey": "value"}
        hooks = parse_hooks_content(content)

        assert hooks == []

    def test_hook_without_matcher_has_none(self) -> None:
        """Hooks without matcher should have None matcher."""
        from scc_cli.audit.parser import parse_hooks_content

        content = {
            "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "init.sh"}]}]}
        }
        hooks = parse_hooks_content(content)

        assert len(hooks) == 1
        assert hooks[0].matcher is None

    def test_handles_unknown_hook_type(self) -> None:
        """Should handle unknown hook types gracefully."""
        from scc_cli.audit.parser import parse_hooks_content

        content = {
            "hooks": {"PreToolUse": [{"hooks": [{"type": "unknown_type", "data": "value"}]}]}
        }
        hooks = parse_hooks_content(content)

        assert len(hooks) == 1
        assert hooks[0].hook_type == "unknown_type"


class TestCreateManifestResult:
    """Tests for creating ManifestResult from various states."""

    def test_create_missing_manifest_result(self) -> None:
        """Should create MISSING status result correctly."""
        from scc_cli.audit.parser import create_missing_result

        result = create_missing_result(Path(".mcp.json"))

        assert result.status == ManifestStatus.MISSING
        assert result.path == Path(".mcp.json")
        assert result.content is None
        assert result.error is None

    def test_create_unreadable_manifest_result(self) -> None:
        """Should create UNREADABLE status result with error message."""
        from scc_cli.audit.parser import create_unreadable_result

        result = create_unreadable_result(
            Path(".mcp.json"), "Permission denied: /path/to/.mcp.json"
        )

        assert result.status == ManifestStatus.UNREADABLE
        assert result.path == Path(".mcp.json")
        assert result.error_message == "Permission denied: /path/to/.mcp.json"

    def test_create_parsed_manifest_result(self) -> None:
        """Should create PARSED status result with content."""
        from scc_cli.audit.parser import create_parsed_result

        content = {"mcpServers": {"server": {"command": "node"}}}
        result = create_parsed_result(Path(".mcp.json"), content)

        assert result.status == ManifestStatus.PARSED
        assert result.path == Path(".mcp.json")
        assert result.content == content


class TestParsePluginManifests:
    """Tests for the complete manifest parsing workflow."""

    def test_create_plugin_manifests_all_parsed(self) -> None:
        """Should create PluginManifests with all parsed manifests."""
        from scc_cli.audit.parser import create_plugin_manifests

        mcp_result = ManifestResult(
            status=ManifestStatus.PARSED,
            path=Path(".mcp.json"),
            content={"mcpServers": {}},
        )
        hooks_result = ManifestResult(
            status=ManifestStatus.PARSED,
            path=Path("hooks/hooks.json"),
            content={"hooks": {}},
        )

        manifests = create_plugin_manifests(mcp_result, hooks_result)

        assert manifests.mcp.status == ManifestStatus.PARSED
        assert manifests.hooks.status == ManifestStatus.PARSED
        assert manifests.has_declarations

    def test_create_plugin_manifests_both_missing(self) -> None:
        """Should create PluginManifests with missing manifests (clean plugin)."""
        from scc_cli.audit.parser import create_plugin_manifests

        mcp_result = ManifestResult(
            status=ManifestStatus.MISSING,
            path=Path(".mcp.json"),
        )
        hooks_result = ManifestResult(
            status=ManifestStatus.MISSING,
            path=Path("hooks/hooks.json"),
        )

        manifests = create_plugin_manifests(mcp_result, hooks_result)

        assert not manifests.has_declarations
        assert not manifests.has_problems

    def test_create_plugin_manifests_with_problems(self) -> None:
        """Should correctly detect problems in manifests."""
        from scc_cli.audit.parser import create_plugin_manifests

        mcp_result = ManifestResult(
            status=ManifestStatus.MALFORMED,
            path=Path(".mcp.json"),
            error=ParseError(message="Invalid JSON", line=1, column=5),
        )
        hooks_result = ManifestResult(
            status=ManifestStatus.MISSING,
            path=Path("hooks/hooks.json"),
        )

        manifests = create_plugin_manifests(mcp_result, hooks_result)

        assert manifests.has_problems
        assert manifests.mcp.status == ManifestStatus.MALFORMED
