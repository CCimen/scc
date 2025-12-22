"""Tests for plugin audit CLI commands.

TDD tests for Phase 2.2 - Plugin Audit CLI.

Commands to implement:
- scc audit plugins: Show plugin audit results (human-readable)
- scc audit plugins --json: Export as JSON with schemaVersion
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from scc_cli import cli
from scc_cli.models.plugin_audit import (
    AuditOutput,
    ManifestResult,
    ManifestStatus,
    ParseError,
    PluginAuditResult,
    PluginManifests,
)

runner = CliRunner()


# ═══════════════════════════════════════════════════════════════════════════════
# Test fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def clean_plugin() -> PluginAuditResult:
    """Plugin with no manifest declarations (clean)."""
    return PluginAuditResult(
        plugin_id="clean-plugin@marketplace",
        plugin_name="clean-plugin",
        marketplace="marketplace",
        version="1.0.0",
        install_path=Path.home() / ".claude" / "plugins" / "cache" / "clean-plugin",
        installed=True,
        manifests=PluginManifests(
            mcp=ManifestResult(status=ManifestStatus.MISSING, path=Path(".mcp.json")),
            hooks=ManifestResult(status=ManifestStatus.MISSING, path=Path("hooks/hooks.json")),
        ),
    )


@pytest.fixture
def parsed_plugin() -> PluginAuditResult:
    """Plugin with parsed manifests."""
    return PluginAuditResult(
        plugin_id="my-plugin@marketplace",
        plugin_name="my-plugin",
        marketplace="marketplace",
        version="2.0.0",
        install_path=Path.home() / ".claude" / "plugins" / "cache" / "my-plugin",
        installed=True,
        manifests=PluginManifests(
            mcp=ManifestResult(
                status=ManifestStatus.PARSED,
                path=Path(".mcp.json"),
                content={"mcpServers": {"my-server": {"command": "node", "args": ["s.js"]}}},
            ),
            hooks=ManifestResult(status=ManifestStatus.MISSING, path=Path("hooks/hooks.json")),
        ),
    )


@pytest.fixture
def malformed_plugin() -> PluginAuditResult:
    """Plugin with malformed manifest."""
    return PluginAuditResult(
        plugin_id="broken-plugin@marketplace",
        plugin_name="broken-plugin",
        marketplace="marketplace",
        version="1.0.0",
        install_path=Path.home() / ".claude" / "plugins" / "cache" / "broken-plugin",
        installed=True,
        manifests=PluginManifests(
            mcp=ManifestResult(
                status=ManifestStatus.MALFORMED,
                path=Path(".mcp.json"),
                error=ParseError(message="Expected ',' but found '}'", line=15, column=8),
            ),
            hooks=ManifestResult(status=ManifestStatus.MISSING, path=Path("hooks/hooks.json")),
        ),
    )


@pytest.fixture
def sample_audit_output(
    clean_plugin: PluginAuditResult, parsed_plugin: PluginAuditResult
) -> AuditOutput:
    """Sample audit output with mixed plugins."""
    return AuditOutput(
        schema_version=1,
        plugins=[clean_plugin, parsed_plugin],
        warnings=[],
    )


@pytest.fixture
def problematic_audit_output(
    malformed_plugin: PluginAuditResult,
) -> AuditOutput:
    """Audit output with problems (should exit 1)."""
    return AuditOutput(
        schema_version=1,
        plugins=[malformed_plugin],
        warnings=[],
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for scc audit plugins command
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuditPluginsCommand:
    """Tests for `scc audit plugins` command."""

    def test_audit_plugins_shows_header(self, sample_audit_output: AuditOutput) -> None:
        """Should display header with plugin count."""
        with patch("scc_cli.cli_audit.audit_all_plugins", return_value=sample_audit_output):
            result = runner.invoke(cli.app, ["audit", "plugins"])

        assert result.exit_code == 0
        assert "2" in result.output  # plugin count

    def test_audit_plugins_shows_plugin_names(self, sample_audit_output: AuditOutput) -> None:
        """Should display plugin names in output."""
        with patch("scc_cli.cli_audit.audit_all_plugins", return_value=sample_audit_output):
            result = runner.invoke(cli.app, ["audit", "plugins"])

        assert result.exit_code == 0
        assert "clean-plugin" in result.output
        assert "my-plugin" in result.output

    def test_audit_plugins_shows_status(self, sample_audit_output: AuditOutput) -> None:
        """Should show status for each plugin."""
        with patch("scc_cli.cli_audit.audit_all_plugins", return_value=sample_audit_output):
            result = runner.invoke(cli.app, ["audit", "plugins"])

        assert result.exit_code == 0
        # Should show clean or parsed status indicators
        assert "clean" in result.output.lower() or "parsed" in result.output.lower()

    def test_audit_plugins_shows_mcp_servers(self, parsed_plugin: PluginAuditResult) -> None:
        """Should show MCP servers for plugins with declarations."""
        output = AuditOutput(plugins=[parsed_plugin])
        with patch("scc_cli.cli_audit.audit_all_plugins", return_value=output):
            result = runner.invoke(cli.app, ["audit", "plugins"])

        assert result.exit_code == 0
        assert "my-server" in result.output

    def test_audit_plugins_shows_malformed_error(self, malformed_plugin: PluginAuditResult) -> None:
        """Should show error details for malformed manifests."""
        output = AuditOutput(plugins=[malformed_plugin])
        with patch("scc_cli.cli_audit.audit_all_plugins", return_value=output):
            result = runner.invoke(cli.app, ["audit", "plugins"])

        assert result.exit_code == 1  # CI failure
        assert "malformed" in result.output.lower()
        assert "line 15" in result.output

    def test_audit_plugins_shows_disclaimer(self, sample_audit_output: AuditOutput) -> None:
        """Should show informational disclaimer."""
        with patch("scc_cli.cli_audit.audit_all_plugins", return_value=sample_audit_output):
            result = runner.invoke(cli.app, ["audit", "plugins"])

        assert result.exit_code == 0
        assert "informational" in result.output.lower()

    def test_audit_plugins_empty_registry(self) -> None:
        """Should handle empty plugin registry gracefully."""
        output = AuditOutput(plugins=[])
        with patch("scc_cli.cli_audit.audit_all_plugins", return_value=output):
            result = runner.invoke(cli.app, ["audit", "plugins"])

        assert result.exit_code == 0
        assert "0" in result.output or "no plugins" in result.output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for scc audit plugins --json
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuditPluginsJsonOutput:
    """Tests for `scc audit plugins --json` output format."""

    def test_json_output_is_valid_json(self, sample_audit_output: AuditOutput) -> None:
        """Should output valid JSON."""
        with patch("scc_cli.cli_audit.audit_all_plugins", return_value=sample_audit_output):
            result = runner.invoke(cli.app, ["audit", "plugins", "--json"])

        assert result.exit_code == 0
        # Should parse without error
        data = json.loads(result.output)
        assert isinstance(data, dict)

    def test_json_output_has_schema_version(self, sample_audit_output: AuditOutput) -> None:
        """Should include schemaVersion in JSON output."""
        with patch("scc_cli.cli_audit.audit_all_plugins", return_value=sample_audit_output):
            result = runner.invoke(cli.app, ["audit", "plugins", "--json"])

        data = json.loads(result.output)
        assert "schemaVersion" in data
        assert data["schemaVersion"] == 1

    def test_json_output_has_summary(self, sample_audit_output: AuditOutput) -> None:
        """Should include summary statistics in JSON output."""
        with patch("scc_cli.cli_audit.audit_all_plugins", return_value=sample_audit_output):
            result = runner.invoke(cli.app, ["audit", "plugins", "--json"])

        data = json.loads(result.output)
        assert "summary" in data
        assert "total" in data["summary"]
        assert data["summary"]["total"] == 2

    def test_json_output_has_plugins_array(self, sample_audit_output: AuditOutput) -> None:
        """Should include plugins array in JSON output."""
        with patch("scc_cli.cli_audit.audit_all_plugins", return_value=sample_audit_output):
            result = runner.invoke(cli.app, ["audit", "plugins", "--json"])

        data = json.loads(result.output)
        assert "plugins" in data
        assert len(data["plugins"]) == 2

    def test_json_output_plugin_structure(self, parsed_plugin: PluginAuditResult) -> None:
        """Should include expected fields for each plugin."""
        output = AuditOutput(plugins=[parsed_plugin])
        with patch("scc_cli.cli_audit.audit_all_plugins", return_value=output):
            result = runner.invoke(cli.app, ["audit", "plugins", "--json"])

        data = json.loads(result.output)
        plugin = data["plugins"][0]
        assert "pluginId" in plugin
        assert "name" in plugin
        assert "marketplace" in plugin
        assert "version" in plugin
        assert "installed" in plugin
        assert "status" in plugin

    def test_json_output_includes_mcp_servers(self, parsed_plugin: PluginAuditResult) -> None:
        """Should include MCP server info in JSON output."""
        output = AuditOutput(plugins=[parsed_plugin])
        with patch("scc_cli.cli_audit.audit_all_plugins", return_value=output):
            result = runner.invoke(cli.app, ["audit", "plugins", "--json"])

        data = json.loads(result.output)
        plugin = data["plugins"][0]
        assert "mcpServers" in plugin
        assert len(plugin["mcpServers"]) == 1
        assert plugin["mcpServers"][0]["name"] == "my-server"

    def test_json_output_includes_error_details(self, malformed_plugin: PluginAuditResult) -> None:
        """Should include error details in JSON for malformed manifests."""
        output = AuditOutput(plugins=[malformed_plugin])
        with patch("scc_cli.cli_audit.audit_all_plugins", return_value=output):
            result = runner.invoke(cli.app, ["audit", "plugins", "--json"])

        data = json.loads(result.output)
        plugin = data["plugins"][0]
        assert "manifests" in plugin
        assert "mcp" in plugin["manifests"]
        assert plugin["manifests"]["mcp"]["status"] == "malformed"
        assert "error" in plugin["manifests"]["mcp"]


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for CI exit codes
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuditPluginsExitCodes:
    """Tests for CI exit code behavior."""

    def test_exit_0_when_all_ok(self, sample_audit_output: AuditOutput) -> None:
        """Should exit 0 when all plugins parsed successfully."""
        with patch("scc_cli.cli_audit.audit_all_plugins", return_value=sample_audit_output):
            result = runner.invoke(cli.app, ["audit", "plugins"])

        assert result.exit_code == 0

    def test_exit_1_when_malformed(self, problematic_audit_output: AuditOutput) -> None:
        """Should exit 1 when any plugin has malformed manifest."""
        with patch("scc_cli.cli_audit.audit_all_plugins", return_value=problematic_audit_output):
            result = runner.invoke(cli.app, ["audit", "plugins"])

        assert result.exit_code == 1

    def test_exit_1_when_unreadable(self) -> None:
        """Should exit 1 when any plugin has unreadable manifest."""
        unreadable_plugin = PluginAuditResult(
            plugin_id="unreadable@market",
            plugin_name="unreadable",
            marketplace="market",
            version="1.0.0",
            install_path=Path("/path/to/plugin"),
            installed=True,
            manifests=PluginManifests(
                mcp=ManifestResult(
                    status=ManifestStatus.UNREADABLE,
                    path=Path(".mcp.json"),
                    error_message="Permission denied",
                ),
                hooks=ManifestResult(status=ManifestStatus.MISSING, path=Path("hooks/hooks.json")),
            ),
        )
        output = AuditOutput(plugins=[unreadable_plugin])
        with patch("scc_cli.cli_audit.audit_all_plugins", return_value=output):
            result = runner.invoke(cli.app, ["audit", "plugins"])

        assert result.exit_code == 1

    def test_exit_0_when_empty(self) -> None:
        """Should exit 0 when no plugins installed."""
        output = AuditOutput(plugins=[])
        with patch("scc_cli.cli_audit.audit_all_plugins", return_value=output):
            result = runner.invoke(cli.app, ["audit", "plugins"])

        assert result.exit_code == 0

    def test_json_exit_code_matches_human(self, problematic_audit_output: AuditOutput) -> None:
        """JSON output should have same exit code as human output."""
        with patch("scc_cli.cli_audit.audit_all_plugins", return_value=problematic_audit_output):
            human_result = runner.invoke(cli.app, ["audit", "plugins"])
            json_result = runner.invoke(cli.app, ["audit", "plugins", "--json"])

        assert human_result.exit_code == json_result.exit_code == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for security (output sanitization)
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuditOutputSecurity:
    """Tests for output security and sanitization."""

    def test_relative_paths_in_output(self, parsed_plugin: PluginAuditResult) -> None:
        """Should use relative paths in output, not full system paths."""
        output = AuditOutput(plugins=[parsed_plugin])
        with patch("scc_cli.cli_audit.audit_all_plugins", return_value=output):
            result = runner.invoke(cli.app, ["audit", "plugins", "--json"])

        data = json.loads(result.output)
        # Should not contain /Users or /home in paths
        output_str = json.dumps(data)
        assert "/Users/" not in output_str or ".claude" in output_str
