"""Tests for plugin manifest reader (I/O layer).

These tests define the expected behavior for reading plugin manifests
from the file system, including error handling for various failure modes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from scc_cli.models.plugin_audit import (
    ManifestStatus,
    PluginAuditResult,
)

if TYPE_CHECKING:
    pass


class TestReadPluginManifests:
    """Tests for reading manifests from a plugin directory."""

    def test_read_mcp_manifest_success(self, tmp_path: Path) -> None:
        """Should successfully read .mcp.json from plugin directory."""
        from scc_cli.audit.reader import read_plugin_manifests

        # Create a valid .mcp.json file
        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()
        mcp_file = plugin_dir / ".mcp.json"
        mcp_file.write_text(
            json.dumps({"mcpServers": {"my-server": {"command": "node", "args": ["server.js"]}}})
        )

        manifests = read_plugin_manifests(plugin_dir)

        assert manifests.mcp.status == ManifestStatus.PARSED
        assert manifests.mcp.path == Path(".mcp.json")
        assert manifests.mcp.content is not None
        assert "mcpServers" in manifests.mcp.content

    def test_read_hooks_manifest_success(self, tmp_path: Path) -> None:
        """Should successfully read hooks/hooks.json from plugin directory."""
        from scc_cli.audit.reader import read_plugin_manifests

        # Create a valid hooks.json file
        plugin_dir = tmp_path / "my-plugin"
        hooks_dir = plugin_dir / "hooks"
        hooks_dir.mkdir(parents=True)
        hooks_file = hooks_dir / "hooks.json"
        hooks_file.write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreToolUse": [{"hooks": [{"type": "command", "command": "validate.sh"}]}]
                    }
                }
            )
        )

        manifests = read_plugin_manifests(plugin_dir)

        assert manifests.hooks.status == ManifestStatus.PARSED
        assert manifests.hooks.path == Path("hooks/hooks.json")

    def test_missing_mcp_manifest(self, tmp_path: Path) -> None:
        """Should return MISSING status when .mcp.json doesn't exist."""
        from scc_cli.audit.reader import read_plugin_manifests

        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()

        manifests = read_plugin_manifests(plugin_dir)

        assert manifests.mcp.status == ManifestStatus.MISSING
        assert manifests.mcp.path == Path(".mcp.json")

    def test_missing_hooks_manifest(self, tmp_path: Path) -> None:
        """Should return MISSING status when hooks/hooks.json doesn't exist."""
        from scc_cli.audit.reader import read_plugin_manifests

        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()

        manifests = read_plugin_manifests(plugin_dir)

        assert manifests.hooks.status == ManifestStatus.MISSING
        assert manifests.hooks.path == Path("hooks/hooks.json")

    def test_malformed_mcp_manifest(self, tmp_path: Path) -> None:
        """Should return MALFORMED status with error details for invalid JSON."""
        from scc_cli.audit.reader import read_plugin_manifests

        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()
        mcp_file = plugin_dir / ".mcp.json"
        mcp_file.write_text('{"invalid": json}')  # Invalid JSON

        manifests = read_plugin_manifests(plugin_dir)

        assert manifests.mcp.status == ManifestStatus.MALFORMED
        assert manifests.mcp.error is not None
        assert manifests.mcp.error.line is not None

    def test_malformed_hooks_manifest(self, tmp_path: Path) -> None:
        """Should return MALFORMED status for invalid hooks.json."""
        from scc_cli.audit.reader import read_plugin_manifests

        plugin_dir = tmp_path / "my-plugin"
        hooks_dir = plugin_dir / "hooks"
        hooks_dir.mkdir(parents=True)
        hooks_file = hooks_dir / "hooks.json"
        hooks_file.write_text('{"unclosed": [')

        manifests = read_plugin_manifests(plugin_dir)

        assert manifests.hooks.status == ManifestStatus.MALFORMED
        assert manifests.hooks.error is not None

    def test_unreadable_mcp_manifest(self, tmp_path: Path) -> None:
        """Should return UNREADABLE status for permission errors."""
        from scc_cli.audit.reader import read_plugin_manifests

        # Create file and remove read permissions
        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()
        mcp_file = plugin_dir / ".mcp.json"
        mcp_file.write_text('{"key": "value"}')
        mcp_file.chmod(0o000)

        try:
            manifests = read_plugin_manifests(plugin_dir)
            assert manifests.mcp.status == ManifestStatus.UNREADABLE
            assert manifests.mcp.error_message is not None
        finally:
            # Restore permissions for cleanup
            mcp_file.chmod(0o644)

    def test_both_manifests_present(self, tmp_path: Path) -> None:
        """Should read both .mcp.json and hooks.json when present."""
        from scc_cli.audit.reader import read_plugin_manifests

        plugin_dir = tmp_path / "my-plugin"
        hooks_dir = plugin_dir / "hooks"
        hooks_dir.mkdir(parents=True)

        # Create both manifest files
        (plugin_dir / ".mcp.json").write_text('{"mcpServers": {}}')
        (hooks_dir / "hooks.json").write_text('{"hooks": {}}')

        manifests = read_plugin_manifests(plugin_dir)

        assert manifests.mcp.status == ManifestStatus.PARSED
        assert manifests.hooks.status == ManifestStatus.PARSED
        assert manifests.has_declarations

    def test_clean_plugin_no_manifests(self, tmp_path: Path) -> None:
        """Plugin with no manifest files should be marked as clean."""
        from scc_cli.audit.reader import read_plugin_manifests

        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()

        manifests = read_plugin_manifests(plugin_dir)

        assert manifests.mcp.status == ManifestStatus.MISSING
        assert manifests.hooks.status == ManifestStatus.MISSING
        assert not manifests.has_declarations
        assert not manifests.has_problems


class TestDiscoverInstalledPlugins:
    """Tests for discovering plugins from installed_plugins.json."""

    def test_discover_plugins_from_registry(self, tmp_path: Path) -> None:
        """Should discover plugins from installed_plugins.json."""
        from scc_cli.audit.reader import discover_installed_plugins

        # Create mock Claude directory structure
        claude_dir = tmp_path / ".claude"
        plugins_dir = claude_dir / "plugins"
        plugins_dir.mkdir(parents=True)

        # Create installed_plugins.json
        registry = {
            "items": [
                {
                    "name": "my-plugin",
                    "marketplace": "my-marketplace",
                    "version": "1.0.0",
                    "installPath": str(tmp_path / "cache" / "my-plugin"),
                }
            ]
        }
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(registry))

        plugins = discover_installed_plugins(claude_dir)

        assert len(plugins) == 1
        assert plugins[0]["name"] == "my-plugin"
        assert plugins[0]["marketplace"] == "my-marketplace"
        assert plugins[0]["version"] == "1.0.0"

    def test_discover_multiple_plugins(self, tmp_path: Path) -> None:
        """Should discover all plugins from registry."""
        from scc_cli.audit.reader import discover_installed_plugins

        claude_dir = tmp_path / ".claude"
        plugins_dir = claude_dir / "plugins"
        plugins_dir.mkdir(parents=True)

        registry = {
            "items": [
                {
                    "name": "plugin-a",
                    "marketplace": "market-1",
                    "version": "1.0.0",
                    "installPath": "/path/a",
                },
                {
                    "name": "plugin-b",
                    "marketplace": "market-2",
                    "version": "2.0.0",
                    "installPath": "/path/b",
                },
            ]
        }
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(registry))

        plugins = discover_installed_plugins(claude_dir)

        assert len(plugins) == 2
        names = {p["name"] for p in plugins}
        assert names == {"plugin-a", "plugin-b"}

    def test_discover_empty_registry(self, tmp_path: Path) -> None:
        """Should return empty list when no plugins installed."""
        from scc_cli.audit.reader import discover_installed_plugins

        claude_dir = tmp_path / ".claude"
        plugins_dir = claude_dir / "plugins"
        plugins_dir.mkdir(parents=True)

        registry = {"items": []}
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(registry))

        plugins = discover_installed_plugins(claude_dir)

        assert plugins == []

    def test_discover_missing_registry(self, tmp_path: Path) -> None:
        """Should return empty list when installed_plugins.json doesn't exist."""
        from scc_cli.audit.reader import discover_installed_plugins

        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()

        plugins = discover_installed_plugins(claude_dir)

        assert plugins == []

    def test_discover_malformed_registry(self, tmp_path: Path) -> None:
        """Should return empty list and log warning for malformed registry."""
        from scc_cli.audit.reader import discover_installed_plugins

        claude_dir = tmp_path / ".claude"
        plugins_dir = claude_dir / "plugins"
        plugins_dir.mkdir(parents=True)

        (plugins_dir / "installed_plugins.json").write_text("{invalid json}")

        plugins = discover_installed_plugins(claude_dir)

        assert plugins == []


class TestAuditPlugin:
    """Tests for auditing a single plugin."""

    def test_audit_installed_plugin(self, tmp_path: Path) -> None:
        """Should create full audit result for installed plugin."""
        from scc_cli.audit.reader import audit_plugin

        # Create plugin directory with MCP manifest
        plugin_dir = tmp_path / "my-plugin"
        plugin_dir.mkdir()
        (plugin_dir / ".mcp.json").write_text('{"mcpServers": {"s": {"command": "n"}}}')

        plugin_info = {
            "name": "my-plugin",
            "marketplace": "my-market",
            "version": "1.0.0",
            "installPath": str(plugin_dir),
        }

        result = audit_plugin(plugin_info)

        assert isinstance(result, PluginAuditResult)
        assert result.plugin_id == "my-plugin@my-market"
        assert result.plugin_name == "my-plugin"
        assert result.marketplace == "my-market"
        assert result.version == "1.0.0"
        assert result.installed is True
        assert result.install_path == plugin_dir
        assert result.manifests is not None
        assert result.manifests.mcp.status == ManifestStatus.PARSED

    def test_audit_missing_plugin_directory(self, tmp_path: Path) -> None:
        """Should mark plugin as not installed when directory doesn't exist."""
        from scc_cli.audit.reader import audit_plugin

        plugin_info = {
            "name": "missing-plugin",
            "marketplace": "market",
            "version": "1.0.0",
            "installPath": str(tmp_path / "nonexistent"),
        }

        result = audit_plugin(plugin_info)

        assert result.installed is False
        assert result.manifests is None
        assert result.status_summary == "not installed"

    def test_audit_clean_plugin(self, tmp_path: Path) -> None:
        """Should correctly identify clean plugin (no manifests)."""
        from scc_cli.audit.reader import audit_plugin

        plugin_dir = tmp_path / "clean-plugin"
        plugin_dir.mkdir()

        plugin_info = {
            "name": "clean-plugin",
            "marketplace": "market",
            "version": "1.0.0",
            "installPath": str(plugin_dir),
        }

        result = audit_plugin(plugin_info)

        assert result.installed is True
        assert result.status_summary == "clean"
        assert not result.has_ci_failures

    def test_audit_malformed_plugin(self, tmp_path: Path) -> None:
        """Should correctly identify plugin with malformed manifest."""
        from scc_cli.audit.reader import audit_plugin

        plugin_dir = tmp_path / "broken-plugin"
        plugin_dir.mkdir()
        (plugin_dir / ".mcp.json").write_text("{broken}")

        plugin_info = {
            "name": "broken-plugin",
            "marketplace": "market",
            "version": "1.0.0",
            "installPath": str(plugin_dir),
        }

        result = audit_plugin(plugin_info)

        assert result.status_summary == "malformed"
        assert result.has_ci_failures


class TestAuditAllPlugins:
    """Tests for auditing all installed plugins."""

    def test_audit_all_returns_audit_output(self, tmp_path: Path) -> None:
        """Should return AuditOutput with all plugin results."""
        from scc_cli.audit.reader import audit_all_plugins

        # Create Claude directory with one plugin
        claude_dir = tmp_path / ".claude"
        plugins_dir = claude_dir / "plugins"
        cache_dir = plugins_dir / "cache"
        cache_dir.mkdir(parents=True)

        # Create plugin
        plugin_dir = cache_dir / "my-plugin"
        plugin_dir.mkdir()
        (plugin_dir / ".mcp.json").write_text('{"mcpServers": {}}')

        # Create registry
        registry = {
            "items": [
                {
                    "name": "my-plugin",
                    "marketplace": "market",
                    "version": "1.0.0",
                    "installPath": str(plugin_dir),
                }
            ]
        }
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(registry))

        output = audit_all_plugins(claude_dir)

        assert output.total_plugins == 1
        assert output.exit_code == 0

    def test_audit_all_with_problems(self, tmp_path: Path) -> None:
        """Should detect CI failures in audit output."""
        from scc_cli.audit.reader import audit_all_plugins

        claude_dir = tmp_path / ".claude"
        plugins_dir = claude_dir / "plugins"
        cache_dir = plugins_dir / "cache"
        cache_dir.mkdir(parents=True)

        # Create plugin with malformed manifest
        plugin_dir = cache_dir / "broken-plugin"
        plugin_dir.mkdir()
        (plugin_dir / ".mcp.json").write_text("{broken}")

        registry = {
            "items": [
                {
                    "name": "broken-plugin",
                    "marketplace": "market",
                    "version": "1.0.0",
                    "installPath": str(plugin_dir),
                }
            ]
        }
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(registry))

        output = audit_all_plugins(claude_dir)

        assert output.problem_count == 1
        assert output.exit_code == 1
        assert output.has_ci_failures

    def test_audit_all_empty(self, tmp_path: Path) -> None:
        """Should handle empty plugin registry."""
        from scc_cli.audit.reader import audit_all_plugins

        claude_dir = tmp_path / ".claude"
        plugins_dir = claude_dir / "plugins"
        plugins_dir.mkdir(parents=True)

        registry = {"items": []}
        (plugins_dir / "installed_plugins.json").write_text(json.dumps(registry))

        output = audit_all_plugins(claude_dir)

        assert output.total_plugins == 0
        assert output.exit_code == 0
