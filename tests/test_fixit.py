"""Tests for fix-it command generation utility.

TDD approach: Write tests first for the fix-it one-liners feature.

Fix-it commands should:
- Generate ready-to-copy commands for blocked/denied items
- Distinguish between security blocks (need policy exception) vs delegation denials (local override)
- Include proper quoting for shell safety
- Respect terminal width to avoid line wrapping
"""

from __future__ import annotations


class TestGenerateUnblockCommand:
    """Tests for generating unblock commands for delegation denials."""

    def test_generate_unblock_for_mcp_server(self):
        """Generate unblock command for a denied MCP server."""
        from scc_cli.utils.fixit import generate_unblock_command

        cmd = generate_unblock_command("jira-api", "mcp_server")

        assert "scc unblock jira-api" in cmd
        assert "--ttl 8h" in cmd
        assert '--reason "..."' in cmd

    def test_generate_unblock_for_plugin(self):
        """Generate unblock command for a denied plugin."""
        from scc_cli.utils.fixit import generate_unblock_command

        cmd = generate_unblock_command("vendor-tools", "plugin")

        assert "scc unblock vendor-tools" in cmd
        assert "--ttl 8h" in cmd

    def test_generate_unblock_for_base_image(self):
        """Generate unblock command for a denied base image."""
        from scc_cli.utils.fixit import generate_unblock_command

        cmd = generate_unblock_command("nginx:1.25", "base_image")

        assert "scc unblock nginx:1.25" in cmd
        assert "--ttl 8h" in cmd


class TestGeneratePolicyExceptionCommand:
    """Tests for generating policy exception commands for security blocks."""

    def test_generate_policy_exception_for_plugin(self):
        """Generate policy exception command for a blocked plugin."""
        from scc_cli.utils.fixit import generate_policy_exception_command

        cmd = generate_policy_exception_command("vendor-tools", "plugin")

        assert "scc exceptions create" in cmd
        assert "--policy" in cmd
        assert "--id INC-..." in cmd
        assert "--allow-plugin vendor-tools" in cmd
        assert "--ttl 8h" in cmd
        assert '--reason "..."' in cmd

    def test_generate_policy_exception_for_mcp_server(self):
        """Generate policy exception command for a blocked MCP server."""
        from scc_cli.utils.fixit import generate_policy_exception_command

        cmd = generate_policy_exception_command("internal-api", "mcp_server")

        assert "scc exceptions create" in cmd
        assert "--policy" in cmd
        assert "--allow-mcp internal-api" in cmd

    def test_generate_policy_exception_for_base_image(self):
        """Generate policy exception command for a blocked base image."""
        from scc_cli.utils.fixit import generate_policy_exception_command

        cmd = generate_policy_exception_command("custom:latest", "base_image")

        assert "--allow-image custom:latest" in cmd


class TestShellQuoting:
    """Tests for proper shell quoting in generated commands."""

    def test_target_with_spaces_is_quoted(self):
        """Target names with spaces should be properly quoted."""
        from scc_cli.utils.fixit import generate_unblock_command

        cmd = generate_unblock_command("my plugin", "plugin")

        # Should use shell-safe quoting
        assert "'my plugin'" in cmd or '"my plugin"' in cmd

    def test_target_with_special_chars_is_quoted(self):
        """Target names with special chars should be properly quoted."""
        from scc_cli.utils.fixit import generate_unblock_command

        cmd = generate_unblock_command("plugin$name", "plugin")

        # Should use single quotes for safety
        assert "'plugin$name'" in cmd

    def test_simple_target_no_quotes_needed(self):
        """Simple alphanumeric targets don't need quotes."""
        from scc_cli.utils.fixit import generate_unblock_command

        cmd = generate_unblock_command("jira-api", "mcp_server")

        # jira-api doesn't need quotes
        assert "jira-api" in cmd
        assert "'jira-api'" not in cmd


class TestFormatBlockMessage:
    """Tests for formatting complete block messages with fix-it commands."""

    def test_format_security_block_message(self):
        """Format a security block message with policy exception guidance."""
        from scc_cli.utils.fixit import format_block_message

        msg = format_block_message(
            target="vendor-tools",
            target_type="plugin",
            block_type="security",
            blocked_by="blocked_plugins pattern",
        )

        assert "✗" in msg or "blocked" in msg.lower()
        assert "vendor-tools" in msg
        assert "security policy" in msg.lower()
        assert "scc exceptions create" in msg
        assert "--policy" in msg

    def test_format_delegation_denial_message(self):
        """Format a delegation denial message with unblock guidance."""
        from scc_cli.utils.fixit import format_block_message

        msg = format_block_message(
            target="jira-api",
            target_type="mcp_server",
            block_type="delegation",
            reason="team not delegated for MCP additions",
        )

        assert "✗" in msg or "denied" in msg.lower()
        assert "jira-api" in msg
        assert "scc unblock" in msg
        assert "--ttl 8h" in msg


class TestTerminalWidth:
    """Tests for terminal width detection and formatting."""

    def test_get_terminal_width_returns_reasonable_value(self):
        """get_terminal_width should return a reasonable value."""
        from scc_cli.utils.fixit import get_terminal_width

        width = get_terminal_width()

        # Should be at least 40 (minimum usable) and at most 500 (sanity check)
        assert 40 <= width <= 500

    def test_default_width_when_no_terminal(self):
        """Should return default width when no terminal is attached."""
        from scc_cli.utils.fixit import get_terminal_width

        # In test environment, might not have a real terminal
        width = get_terminal_width()

        # Default is typically 80
        assert width >= 40

    def test_format_command_respects_max_width(self):
        """Long commands should be formatted to respect terminal width."""
        from scc_cli.utils.fixit import format_command_for_terminal

        long_cmd = "scc exceptions create --policy --id INC-2025-00001 --allow-plugin very-long-plugin-name --ttl 8h --reason 'A very long reason that explains why this exception is needed'"

        formatted = format_command_for_terminal(long_cmd, max_width=80)

        # Each line should not exceed max_width (with some tolerance for indentation)
        for line in formatted.split("\n"):
            # Allow some tolerance for indentation
            assert len(line.rstrip()) <= 85


class TestIntegrationScenarios:
    """Integration tests for real-world fix-it scenarios."""

    def test_mcp_server_delegation_denial_scenario(self):
        """Full scenario: MCP server denied by delegation."""
        from scc_cli.utils.fixit import format_block_message

        msg = format_block_message(
            target="jira-api",
            target_type="mcp_server",
            block_type="delegation",
            reason="team not delegated for MCP additions",
        )

        # User should see the denial
        assert "jira-api" in msg

        # User should see how to fix it
        assert "scc unblock jira-api" in msg

    def test_plugin_security_block_scenario(self):
        """Full scenario: Plugin blocked by security policy."""
        from scc_cli.utils.fixit import format_block_message

        msg = format_block_message(
            target="vendor-tools",
            target_type="plugin",
            block_type="security",
            blocked_by="blocked_plugins: vendor-*",
        )

        # User should see the block
        assert "vendor-tools" in msg
        assert "security" in msg.lower()

        # User should see how to request exception
        assert "scc exceptions create" in msg
        assert "--policy" in msg
        assert "--allow-plugin vendor-tools" in msg

    def test_base_image_denial_scenario(self):
        """Full scenario: Base image denied by delegation."""
        from scc_cli.utils.fixit import format_block_message

        msg = format_block_message(
            target="custom-image:v1",
            target_type="base_image",
            block_type="delegation",
            reason="team not delegated for base image additions",
        )

        assert "custom-image:v1" in msg
        assert "scc unblock" in msg
