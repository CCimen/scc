"""Tests for MCP Server configuration.

TDD tests for Task 4 - MCP Server Config.

This module tests:
- MCP server schema validation (sse, stdio types)
- MCP server inheritance (org → team → project)
- MCP server translation to Claude Code format
- Blocked MCP servers
"""

from __future__ import annotations

from typing import Any

import pytest

from scc_cli import profiles, validate
from scc_cli.profiles import (
    EffectiveConfig,
    MCPServer,
    SessionConfig,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Test fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mcp_server_sse() -> dict[str, Any]:
    """SSE type MCP server config."""
    return {
        "name": "gis-internal",
        "type": "sse",
        "url": "https://gis.sundsvall.se/mcp",
    }


@pytest.fixture
def mcp_server_stdio() -> dict[str, Any]:
    """Stdio type MCP server config."""
    return {
        "name": "local-tool",
        "type": "stdio",
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem"],
    }


@pytest.fixture
def org_config_with_mcp() -> dict[str, Any]:
    """Org config with MCP servers in defaults and profiles."""
    return {
        "schema_version": "1.0.0",
        "organization": {"name": "Test Org", "id": "test-org"},
        "security": {
            "blocked_mcp_servers": ["*.untrusted.com", "malicious-*"],
            "allow_stdio_mcp": True,  # Enable stdio for tests
        },
        "defaults": {
            "allowed_plugins": ["test-plugin"],
            "allowed_mcp_servers": ["*.sundsvall.se", "internal-*"],
        },
        "delegation": {
            "teams": {
                "allow_additional_mcp_servers": ["gis-team", "finance-team"],
            },
        },
        "profiles": {
            "gis-team": {
                "description": "GIS team",
                "additional_mcp_servers": [
                    {
                        "name": "gis-internal",
                        "type": "sse",
                        "url": "https://gis.sundsvall.se/mcp",
                    }
                ],
            },
            "finance-team": {
                "description": "Finance team",
                "additional_mcp_servers": [
                    {
                        "name": "finance-api",
                        "type": "stdio",
                        "command": "/usr/local/bin/finance-mcp",  # Must be absolute path
                        "args": ["--config", "/etc/finance.json"],
                    }
                ],
            },
        },
    }


@pytest.fixture
def project_config_with_mcp() -> dict[str, Any]:
    """Project config with additional MCP servers."""
    return {
        "additional_mcp_servers": [
            {
                "name": "project-api",
                "type": "sse",
                "url": "https://api.internal.sundsvall.se/mcp",
            }
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for MCP server schema validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestMCPServerSchemaValidation:
    """Tests for MCP server schema validation."""

    def test_valid_sse_server(self, mcp_server_sse):
        """Should validate SSE type MCP server in profile."""
        org_config = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test", "id": "test"},
            "profiles": {
                "test-team": {
                    "description": "Test team",
                    "additional_mcp_servers": [mcp_server_sse],
                }
            },
        }
        # Should not raise - returns empty list on valid config
        result = validate.validate_org_config(org_config, schema_version="v1")
        assert result == [] or result is None

    def test_valid_stdio_server(self, mcp_server_stdio):
        """Should validate stdio type MCP server in profile."""
        org_config = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test", "id": "test"},
            "profiles": {
                "test-team": {
                    "description": "Test team",
                    "additional_mcp_servers": [mcp_server_stdio],
                }
            },
        }
        # Should not raise - returns empty list on valid config
        result = validate.validate_org_config(org_config, schema_version="v1")
        assert result == [] or result is None

    def test_sse_requires_url(self):
        """SSE type should require url field."""
        org_config = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test", "id": "test"},
            "profiles": {
                "test-team": {
                    "description": "Test team",
                    "additional_mcp_servers": [
                        {"name": "bad-sse", "type": "sse"}  # Missing url
                    ],
                }
            },
        }
        # Should return validation errors
        result = validate.validate_org_config(org_config, schema_version="v1")
        assert result and len(result) > 0

    def test_stdio_requires_command(self):
        """Stdio type should require command field."""
        org_config = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test", "id": "test"},
            "profiles": {
                "test-team": {
                    "description": "Test team",
                    "additional_mcp_servers": [
                        {"name": "bad-stdio", "type": "stdio"}  # Missing command
                    ],
                }
            },
        }
        # Should return validation errors
        result = validate.validate_org_config(org_config, schema_version="v1")
        assert result and len(result) > 0

    def test_invalid_type_rejected(self):
        """Should reject invalid MCP server types."""
        org_config = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test", "id": "test"},
            "profiles": {
                "test-team": {
                    "description": "Test team",
                    "additional_mcp_servers": [
                        {"name": "bad", "type": "invalid-type", "url": "http://x"}
                    ],
                }
            },
        }
        # Should return validation errors
        result = validate.validate_org_config(org_config, schema_version="v1")
        assert result and len(result) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for MCP server in profiles
# ═══════════════════════════════════════════════════════════════════════════════


class TestMCPServerInProfiles:
    """Tests for MCP servers in team profiles."""

    def test_profile_can_have_mcp_servers(self, org_config_with_mcp):
        """Profile should be able to define MCP servers."""
        result = validate.validate_org_config(org_config_with_mcp, schema_version="v1")
        assert result == [] or result is None

    def test_profile_mcp_servers_inherit_from_defaults(self, org_config_with_mcp, tmp_path):
        """Team should inherit allowed_mcp_servers patterns from defaults."""
        effective = profiles.compute_effective_config(
            org_config=org_config_with_mcp,
            team_name="gis-team",
            workspace_path=tmp_path,
        )
        # Should have the team's MCP server
        server_names = {s.name for s in effective.mcp_servers}
        assert "gis-internal" in server_names

    def test_multiple_profiles_have_different_mcp_servers(self, org_config_with_mcp, tmp_path):
        """Different teams should have their own MCP servers."""
        gis_effective = profiles.compute_effective_config(
            org_config=org_config_with_mcp,
            team_name="gis-team",
            workspace_path=tmp_path,
        )
        finance_effective = profiles.compute_effective_config(
            org_config=org_config_with_mcp,
            team_name="finance-team",
            workspace_path=tmp_path,
        )

        gis_servers = {s.name for s in gis_effective.mcp_servers}
        finance_servers = {s.name for s in finance_effective.mcp_servers}

        assert "gis-internal" in gis_servers
        assert "gis-internal" not in finance_servers
        assert "finance-api" in finance_servers
        assert "finance-api" not in gis_servers


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for MCP server inheritance
# ═══════════════════════════════════════════════════════════════════════════════


class TestMCPServerInheritance:
    """Tests for MCP server inheritance (org → team → project)."""

    def test_project_can_add_mcp_servers(self, org_config_with_mcp, tmp_path):
        """Project should be able to add MCP servers if delegated."""
        # Create project config
        project_config = tmp_path / ".scc.yaml"
        project_config.write_text("""
additional_mcp_servers:
  - name: project-api
    type: sse
    url: https://api.internal.sundsvall.se/mcp
""")

        # Enable project delegation
        org_config_with_mcp["delegation"]["projects"] = {"inherit_team_delegation": True}
        org_config_with_mcp["profiles"]["gis-team"]["delegation"] = {
            "allow_project_overrides": True
        }

        effective = profiles.compute_effective_config(
            org_config=org_config_with_mcp,
            team_name="gis-team",
            workspace_path=tmp_path,
        )

        server_names = {s.name for s in effective.mcp_servers}
        assert "project-api" in server_names

    def test_mcp_servers_merge_not_replace(self, org_config_with_mcp, tmp_path):
        """Project MCP servers should merge with team's, not replace."""
        project_config = tmp_path / ".scc.yaml"
        project_config.write_text("""
additional_mcp_servers:
  - name: project-api
    type: sse
    url: https://api.internal.sundsvall.se/mcp
""")

        org_config_with_mcp["delegation"]["projects"] = {"inherit_team_delegation": True}
        org_config_with_mcp["profiles"]["gis-team"]["delegation"] = {
            "allow_project_overrides": True
        }

        effective = profiles.compute_effective_config(
            org_config=org_config_with_mcp,
            team_name="gis-team",
            workspace_path=tmp_path,
        )

        server_names = {s.name for s in effective.mcp_servers}
        # Should have both team and project servers
        assert "gis-internal" in server_names
        assert "project-api" in server_names


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for blocked MCP servers
# ═══════════════════════════════════════════════════════════════════════════════


class TestBlockedMCPServers:
    """Tests for blocked MCP servers (security boundaries)."""

    def test_blocked_mcp_server_rejected(self, org_config_with_mcp, tmp_path):
        """MCP servers matching blocked patterns should be rejected."""
        project_config = tmp_path / ".scc.yaml"
        project_config.write_text("""
additional_mcp_servers:
  - name: malicious-tool
    type: sse
    url: https://malicious.untrusted.com/mcp
""")

        org_config_with_mcp["delegation"]["projects"] = {"inherit_team_delegation": True}
        org_config_with_mcp["profiles"]["gis-team"]["delegation"] = {
            "allow_project_overrides": True
        }

        effective = profiles.compute_effective_config(
            org_config=org_config_with_mcp,
            team_name="gis-team",
            workspace_path=tmp_path,
        )

        # Server should not be in effective config
        server_names = {s.name for s in effective.mcp_servers}
        assert "malicious-tool" not in server_names

        # Should be recorded as blocked
        blocked_items = [b.item for b in effective.blocked_items]
        assert "malicious-tool" in blocked_items

    def test_blocked_by_name_pattern(self, org_config_with_mcp, tmp_path):
        """Server names matching blocked patterns should be rejected."""
        project_config = tmp_path / ".scc.yaml"
        project_config.write_text("""
additional_mcp_servers:
  - name: malicious-server
    type: sse
    url: https://safe.sundsvall.se/mcp
""")

        org_config_with_mcp["delegation"]["projects"] = {"inherit_team_delegation": True}
        org_config_with_mcp["profiles"]["gis-team"]["delegation"] = {
            "allow_project_overrides": True
        }

        effective = profiles.compute_effective_config(
            org_config=org_config_with_mcp,
            team_name="gis-team",
            workspace_path=tmp_path,
        )

        server_names = {s.name for s in effective.mcp_servers}
        assert "malicious-server" not in server_names

    def test_blocked_by_url_pattern(self, org_config_with_mcp, tmp_path):
        """Server URLs matching blocked patterns should be rejected."""
        project_config = tmp_path / ".scc.yaml"
        project_config.write_text("""
additional_mcp_servers:
  - name: safe-name
    type: sse
    url: https://evil.untrusted.com/mcp
""")

        org_config_with_mcp["delegation"]["projects"] = {"inherit_team_delegation": True}
        org_config_with_mcp["profiles"]["gis-team"]["delegation"] = {
            "allow_project_overrides": True
        }

        effective = profiles.compute_effective_config(
            org_config=org_config_with_mcp,
            team_name="gis-team",
            workspace_path=tmp_path,
        )

        server_names = {s.name for s in effective.mcp_servers}
        assert "safe-name" not in server_names


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for MCP server translation to Claude Code format
# ═══════════════════════════════════════════════════════════════════════════════


class TestMCPServerTranslation:
    """Tests for MCP server translation to Claude Code format.

    Claude Code uses a dict format with server name as key:
    {
        "mcpServers": {
            "server-name": {"type": "sse", "url": "..."}
        }
    }
    """

    def test_sse_server_translation(self):
        """SSE server should translate to Claude Code format."""
        from scc_cli import claude_adapter

        server = MCPServer(
            name="gis-internal",
            type="sse",
            url="https://gis.sundsvall.se/mcp",
        )

        name, config = claude_adapter.translate_mcp_server(server)

        assert name == "gis-internal"
        assert config["type"] == "sse"
        assert config["url"] == "https://gis.sundsvall.se/mcp"

    def test_stdio_server_translation(self):
        """Stdio server should translate to Claude Code format."""
        from scc_cli import claude_adapter

        server = MCPServer(
            name="local-tool",
            type="stdio",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-filesystem"],
        )

        name, config = claude_adapter.translate_mcp_server(server)

        assert name == "local-tool"
        assert config["type"] == "stdio"
        assert config["command"] == "npx"
        assert config["args"] == ["-y", "@modelcontextprotocol/server-filesystem"]

    def test_stdio_server_with_env(self):
        """Stdio server with env vars should translate correctly."""
        from scc_cli import claude_adapter

        server = MCPServer(
            name="env-tool",
            type="stdio",
            command="my-tool",
            args=["--mode", "prod"],
            env={"API_KEY": "${SECRET_KEY}", "DEBUG": "false"},
        )

        name, config = claude_adapter.translate_mcp_server(server)

        assert config["env"]["API_KEY"] == "${SECRET_KEY}"
        assert config["env"]["DEBUG"] == "false"

    def test_sse_server_with_headers(self):
        """SSE server with headers should translate correctly."""
        from scc_cli import claude_adapter

        server = MCPServer(
            name="auth-server",
            type="sse",
            url="https://api.example.com/mcp",
            headers={"Authorization": "Bearer ${TOKEN}"},
        )

        name, config = claude_adapter.translate_mcp_server(server)

        assert config["headers"]["Authorization"] == "Bearer ${TOKEN}"

    def test_http_server_translation(self):
        """HTTP server should translate to Claude Code format."""
        from scc_cli import claude_adapter

        server = MCPServer(
            name="http-server",
            type="http",
            url="https://api.example.com/mcp",
        )

        name, config = claude_adapter.translate_mcp_server(server)

        assert name == "http-server"
        assert config["type"] == "http"
        assert config["url"] == "https://api.example.com/mcp"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for build_mcp_servers function
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildMCPServers:
    """Tests for build_mcp_servers() function.

    Returns dict format: {"server-name": {"type": "...", ...}}
    """

    def test_build_mcp_servers_from_effective_config(self):
        """Should build MCP servers dict from EffectiveConfig."""
        from scc_cli import claude_adapter

        effective = EffectiveConfig(
            plugins=set(),
            mcp_servers=[
                MCPServer(name="server1", type="sse", url="https://api.example.com/mcp"),
                MCPServer(name="server2", type="stdio", command="tool", args=["--flag"]),
            ],
            network_policy="default",
            session_config=SessionConfig(),
            decisions=[],
            blocked_items=[],
            denied_additions=[],
        )

        result = claude_adapter.build_mcp_servers(effective)

        assert len(result) == 2
        assert "server1" in result
        assert "server2" in result
        assert result["server1"]["type"] == "sse"
        assert result["server2"]["type"] == "stdio"

    def test_build_mcp_servers_empty_list(self):
        """Should handle empty MCP servers list."""
        from scc_cli import claude_adapter

        effective = EffectiveConfig(
            plugins=set(),
            mcp_servers=[],
            network_policy="default",
            session_config=SessionConfig(),
            decisions=[],
            blocked_items=[],
            denied_additions=[],
        )

        result = claude_adapter.build_mcp_servers(effective)

        assert result == {}


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for integration with build_claude_settings
# ═══════════════════════════════════════════════════════════════════════════════


class TestMCPServerIntegration:
    """Tests for MCP server integration with Claude Code settings."""

    def test_mcp_servers_in_claude_settings(self):
        """MCP servers should appear in Claude Code settings."""
        from scc_cli import claude_adapter

        effective = EffectiveConfig(
            plugins={"plugin-a"},
            mcp_servers=[
                MCPServer(name="my-server", type="sse", url="https://api.example.com"),
            ],
            network_policy="default",
            session_config=SessionConfig(),
            decisions=[],
            blocked_items=[],
            denied_additions=[],
        )

        settings = claude_adapter.build_settings_from_effective_config(effective)

        assert "mcpServers" in settings
        assert "my-server" in settings["mcpServers"]
        assert settings["mcpServers"]["my-server"]["type"] == "sse"

    def test_no_mcp_servers_key_when_empty(self):
        """Should not include mcpServers key when no servers configured."""
        from scc_cli import claude_adapter

        effective = EffectiveConfig(
            plugins={"plugin-a"},
            mcp_servers=[],
            network_policy="default",
            session_config=SessionConfig(),
            decisions=[],
            blocked_items=[],
            denied_additions=[],
        )

        settings = claude_adapter.build_settings_from_effective_config(effective)

        # Either no key or empty dict - implementation choice
        if "mcpServers" in settings:
            assert settings["mcpServers"] == {}
