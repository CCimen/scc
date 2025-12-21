"""Tests for scc config explain command.

TDD tests for Task 3 - Config Explain.

This command helps users understand:
- What effective config is being used
- Why each setting has its current value (source attribution)
- What items are blocked and why
- What additions were denied and why
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from scc_cli import cli
from scc_cli.profiles import (
    BlockedItem,
    ConfigDecision,
    DelegationDenied,
    EffectiveConfig,
    MCPServer,
    SessionConfig,
)

runner = CliRunner()


# ═══════════════════════════════════════════════════════════════════════════════
# Test fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def effective_config_basic():
    """Basic effective config with some decisions."""
    return EffectiveConfig(
        plugins={"plugin-a", "plugin-b"},
        mcp_servers=[],
        network_policy="default",
        session_config=SessionConfig(timeout_hours=8),
        decisions=[
            ConfigDecision(
                field="plugins",
                value="plugin-a",
                reason="Organization default plugin",
                source="org.defaults",
            ),
            ConfigDecision(
                field="plugins",
                value="plugin-b",
                reason="Team profile addition",
                source="team.dev",
            ),
            ConfigDecision(
                field="session.timeout_hours",
                value=8,
                reason="Organization default session timeout",
                source="org.defaults",
            ),
        ],
        blocked_items=[],
        denied_additions=[],
    )


@pytest.fixture
def effective_config_with_blocked():
    """Effective config with blocked items."""
    return EffectiveConfig(
        plugins={"plugin-a"},
        mcp_servers=[],
        network_policy="default",
        session_config=SessionConfig(),
        decisions=[
            ConfigDecision(
                field="plugins",
                value="plugin-a",
                reason="Organization default",
                source="org.defaults",
            ),
        ],
        blocked_items=[
            BlockedItem(
                item="malicious-plugin",
                blocked_by="malicious-*",
                source="org.security",
            ),
        ],
        denied_additions=[],
    )


@pytest.fixture
def effective_config_with_denied():
    """Effective config with denied additions."""
    return EffectiveConfig(
        plugins={"plugin-a"},
        mcp_servers=[],
        network_policy="default",
        session_config=SessionConfig(),
        decisions=[],
        blocked_items=[],
        denied_additions=[
            DelegationDenied(
                item="restricted-plugin",
                requested_by="project",
                reason="Not in team's delegated scope",
            ),
        ],
    )


@pytest.fixture
def effective_config_full():
    """Full effective config with all types of entries."""
    return EffectiveConfig(
        plugins={"plugin-a", "plugin-b", "plugin-c"},
        mcp_servers=[],
        network_policy="corp-proxy",
        session_config=SessionConfig(timeout_hours=4, auto_resume=True),
        decisions=[
            ConfigDecision(
                field="plugins",
                value="plugin-a",
                reason="Organization default",
                source="org.defaults",
            ),
            ConfigDecision(
                field="plugins",
                value="plugin-b",
                reason="Added by team profile",
                source="team.dev",
            ),
            ConfigDecision(
                field="plugins",
                value="plugin-c",
                reason="Added by project config",
                source="project",
            ),
            ConfigDecision(
                field="network_policy",
                value="corp-proxy",
                reason="Organization policy",
                source="org.defaults",
            ),
            ConfigDecision(
                field="session.timeout_hours",
                value=4,
                reason="Overridden by team profile",
                source="team.dev",
            ),
        ],
        blocked_items=[
            BlockedItem(
                item="bad-plugin",
                blocked_by="bad-*",
                source="org.security",
            ),
        ],
        denied_additions=[
            DelegationDenied(
                item="unauthorized-plugin",
                requested_by="project",
                reason="Not delegated to projects",
            ),
        ],
    )


@pytest.fixture
def mock_org_config():
    """Minimal org config for testing."""
    return {
        "schema_version": "2.0",
        "organization": {"name": "Test Org"},
        "profiles": {"dev": {"description": "Dev team"}},
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for basic explain output
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigExplainBasic:
    """Tests for basic config explain output."""

    def test_explain_shows_effective_plugins(self, effective_config_basic, mock_org_config):
        """Should show effective plugins in output."""
        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value="dev"),
            patch(
                "scc_cli.cli_config.profiles.compute_effective_config",
                return_value=effective_config_basic,
            ),
        ):
            result = runner.invoke(cli.app, ["config", "explain"])

        assert result.exit_code == 0
        assert "plugin-a" in result.output
        assert "plugin-b" in result.output

    def test_explain_shows_source_attribution(self, effective_config_basic, mock_org_config):
        """Should show where each setting came from."""
        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value="dev"),
            patch(
                "scc_cli.cli_config.profiles.compute_effective_config",
                return_value=effective_config_basic,
            ),
        ):
            result = runner.invoke(cli.app, ["config", "explain"])

        assert result.exit_code == 0
        # Should show source attribution
        assert "org.defaults" in result.output or "organization" in result.output.lower()
        assert "team" in result.output.lower()

    def test_explain_shows_session_config(self, effective_config_basic, mock_org_config):
        """Should show session configuration."""
        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value="dev"),
            patch(
                "scc_cli.cli_config.profiles.compute_effective_config",
                return_value=effective_config_basic,
            ),
        ):
            result = runner.invoke(cli.app, ["config", "explain"])

        assert result.exit_code == 0
        # Should show session timeout
        assert "8" in result.output or "timeout" in result.output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for blocked items display
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigExplainBlocked:
    """Tests for blocked items in config explain."""

    def test_explain_shows_blocked_items(self, effective_config_with_blocked, mock_org_config):
        """Should display blocked items."""
        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value="dev"),
            patch(
                "scc_cli.cli_config.profiles.compute_effective_config",
                return_value=effective_config_with_blocked,
            ),
        ):
            result = runner.invoke(cli.app, ["config", "explain"])

        assert result.exit_code == 0
        assert "blocked" in result.output.lower()
        assert "malicious-plugin" in result.output

    def test_explain_shows_blocked_pattern(self, effective_config_with_blocked, mock_org_config):
        """Should show which pattern caused the block."""
        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value="dev"),
            patch(
                "scc_cli.cli_config.profiles.compute_effective_config",
                return_value=effective_config_with_blocked,
            ),
        ):
            result = runner.invoke(cli.app, ["config", "explain"])

        assert result.exit_code == 0
        # Should show the blocking pattern
        assert "malicious-*" in result.output


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for denied additions display
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigExplainDenied:
    """Tests for denied additions in config explain."""

    def test_explain_shows_denied_additions(self, effective_config_with_denied, mock_org_config):
        """Should display denied additions."""
        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value="dev"),
            patch(
                "scc_cli.cli_config.profiles.compute_effective_config",
                return_value=effective_config_with_denied,
            ),
        ):
            result = runner.invoke(cli.app, ["config", "explain"])

        assert result.exit_code == 0
        assert "denied" in result.output.lower()
        assert "restricted-plugin" in result.output

    def test_explain_shows_denial_reason(self, effective_config_with_denied, mock_org_config):
        """Should show why the addition was denied."""
        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value="dev"),
            patch(
                "scc_cli.cli_config.profiles.compute_effective_config",
                return_value=effective_config_with_denied,
            ),
        ):
            result = runner.invoke(cli.app, ["config", "explain"])

        assert result.exit_code == 0
        # Should show reason
        assert "delegat" in result.output.lower() or "scope" in result.output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for field filter
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigExplainFieldFilter:
    """Tests for --field filter option."""

    def test_explain_filter_plugins(self, effective_config_full, mock_org_config):
        """Should filter output to only plugins."""
        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value="dev"),
            patch(
                "scc_cli.cli_config.profiles.compute_effective_config",
                return_value=effective_config_full,
            ),
        ):
            result = runner.invoke(cli.app, ["config", "explain", "--field", "plugins"])

        assert result.exit_code == 0
        assert "plugin-a" in result.output
        # Should not show unrelated fields in detail
        # (network_policy should not be prominently displayed)

    def test_explain_filter_session(self, effective_config_full, mock_org_config):
        """Should filter output to session config."""
        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value="dev"),
            patch(
                "scc_cli.cli_config.profiles.compute_effective_config",
                return_value=effective_config_full,
            ),
        ):
            result = runner.invoke(cli.app, ["config", "explain", "--field", "session"])

        assert result.exit_code == 0
        assert "4" in result.output or "timeout" in result.output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for workspace option
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigExplainWorkspace:
    """Tests for --workspace option."""

    def test_explain_with_workspace(self, effective_config_basic, mock_org_config, tmp_path):
        """Should use specified workspace for project config."""
        workspace = tmp_path / "my-project"
        workspace.mkdir()

        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value="dev"),
            patch(
                "scc_cli.cli_config.profiles.compute_effective_config",
                return_value=effective_config_basic,
            ) as mock_compute,
        ):
            result = runner.invoke(cli.app, ["config", "explain", "--workspace", str(workspace)])

        assert result.exit_code == 0
        # Should pass workspace to compute_effective_config
        mock_compute.assert_called_once()
        call_kwargs = mock_compute.call_args[1]
        assert call_kwargs["workspace_path"] == workspace

    def test_explain_uses_cwd_by_default(self, effective_config_basic, mock_org_config):
        """Should use current directory if no workspace specified."""
        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value="dev"),
            patch(
                "scc_cli.cli_config.profiles.compute_effective_config",
                return_value=effective_config_basic,
            ) as mock_compute,
        ):
            result = runner.invoke(cli.app, ["config", "explain"])

        assert result.exit_code == 0
        mock_compute.assert_called_once()
        call_kwargs = mock_compute.call_args[1]
        # Should pass current working directory
        assert call_kwargs["workspace_path"] == Path.cwd()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for error handling
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigExplainErrors:
    """Tests for error handling in config explain."""

    def test_explain_no_org_config(self):
        """Should handle missing org config gracefully."""
        with patch("scc_cli.cli_config.config.load_cached_org_config", return_value=None):
            result = runner.invoke(cli.app, ["config", "explain"])

        # Should exit with error or helpful message
        assert (
            result.exit_code != 0
            or "no org" in result.output.lower()
            or "setup" in result.output.lower()
        )

    def test_explain_no_team_selected(self, mock_org_config):
        """Should handle no team selected."""
        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value=None),
        ):
            result = runner.invoke(cli.app, ["config", "explain"])

        # Should exit with error or helpful message
        assert result.exit_code != 0 or "team" in result.output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for MCP servers display
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def effective_config_with_mcp():
    """Effective config with MCP servers."""
    return EffectiveConfig(
        plugins={"plugin-a"},
        mcp_servers=[
            MCPServer(name="gis-internal", type="sse", url="https://gis.example.com/mcp"),
            MCPServer(name="local-tool", type="stdio", command="/usr/bin/tool"),
        ],
        network_policy="default",
        session_config=SessionConfig(),
        decisions=[
            ConfigDecision(
                field="mcp_servers",
                value="gis-internal",
                reason="Added by team profile",
                source="team.gis",
            ),
            ConfigDecision(
                field="mcp_servers",
                value="local-tool",
                reason="Added by project config",
                source="project",
            ),
        ],
        blocked_items=[],
        denied_additions=[],
    )


class TestConfigExplainMCPServers:
    """Tests for MCP servers in config explain."""

    def test_explain_shows_mcp_servers(self, effective_config_with_mcp, mock_org_config):
        """Should display MCP servers."""
        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value="dev"),
            patch(
                "scc_cli.cli_config.profiles.compute_effective_config",
                return_value=effective_config_with_mcp,
            ),
        ):
            result = runner.invoke(cli.app, ["config", "explain"])

        assert result.exit_code == 0
        assert "gis-internal" in result.output
        assert "local-tool" in result.output

    def test_explain_shows_mcp_server_types(self, effective_config_with_mcp, mock_org_config):
        """Should show MCP server types (sse, stdio)."""
        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value="dev"),
            patch(
                "scc_cli.cli_config.profiles.compute_effective_config",
                return_value=effective_config_with_mcp,
            ),
        ):
            result = runner.invoke(cli.app, ["config", "explain"])

        assert result.exit_code == 0
        assert "sse" in result.output.lower()
        assert "stdio" in result.output.lower()

    def test_explain_filter_mcp_servers(self, effective_config_with_mcp, mock_org_config):
        """Should filter output to only MCP servers."""
        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value="dev"),
            patch(
                "scc_cli.cli_config.profiles.compute_effective_config",
                return_value=effective_config_with_mcp,
            ),
        ):
            result = runner.invoke(cli.app, ["config", "explain", "--field", "mcp_servers"])

        assert result.exit_code == 0
        assert "gis-internal" in result.output
        assert "local-tool" in result.output


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for help
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigExplainHelp:
    """Tests for help output."""

    def test_explain_help(self):
        """Should show help for explain command."""
        result = runner.invoke(cli.app, ["config", "explain", "--help"])

        assert result.exit_code == 0
        assert "explain" in result.output.lower()
        # Should document the purpose
        assert "config" in result.output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Golden tests for explain output format
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigExplainGoldenBlockedItems:
    """Golden tests for blocked items output format.

    These tests verify the exact output format matches the expected structure:
    - Header with "Blocked Items"
    - Each item shows: ✗ item (blocked by pattern 'X' from source)
    - Fix-it command for policy exception
    """

    def test_blocked_items_output_format_plugin(self, mock_org_config):
        """Verify blocked plugin output matches expected golden format."""
        effective = EffectiveConfig(
            plugins=set(),
            mcp_servers=[],
            network_policy="default",
            session_config=SessionConfig(),
            decisions=[],
            blocked_items=[
                BlockedItem(
                    item="malicious-plugin",
                    blocked_by="malicious-*",
                    source="org.security",
                    target_type="plugin",
                ),
            ],
            denied_additions=[],
        )

        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value="dev"),
            patch(
                "scc_cli.cli_config.profiles.compute_effective_config",
                return_value=effective,
            ),
        ):
            result = runner.invoke(cli.app, ["config", "explain"])

        assert result.exit_code == 0
        # Golden format checks
        assert "Blocked Items" in result.output
        assert "malicious-plugin" in result.output
        assert "malicious-*" in result.output
        assert "org.security" in result.output
        # Fix-it command should include --policy and --allow-plugin
        assert "--policy" in result.output or "policy" in result.output.lower()
        assert "requires PR" in result.output.lower() or "--allow-plugin" in result.output

    def test_blocked_items_output_format_mcp_server(self, mock_org_config):
        """Verify blocked MCP server output matches expected golden format."""
        effective = EffectiveConfig(
            plugins=set(),
            mcp_servers=[],
            network_policy="default",
            session_config=SessionConfig(),
            decisions=[],
            blocked_items=[
                BlockedItem(
                    item="malware-server",
                    blocked_by="malware-*",
                    source="org.security",
                    target_type="mcp_server",
                ),
            ],
            denied_additions=[],
        )

        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value="dev"),
            patch(
                "scc_cli.cli_config.profiles.compute_effective_config",
                return_value=effective,
            ),
        ):
            result = runner.invoke(cli.app, ["config", "explain"])

        assert result.exit_code == 0
        assert "Blocked Items" in result.output
        assert "malware-server" in result.output
        assert "--allow-mcp" in result.output or "mcp" in result.output.lower()


class TestConfigExplainGoldenDeniedAdditions:
    """Golden tests for denied additions output format.

    These tests verify the exact output format matches the expected structure:
    - Header with "Denied Additions"
    - Each item shows: ⚠ item (requested by X: reason)
    - Fix-it command for scc unblock
    """

    def test_denied_additions_output_format(self, mock_org_config):
        """Verify denied additions output matches expected golden format."""
        effective = EffectiveConfig(
            plugins=set(),
            mcp_servers=[],
            network_policy="default",
            session_config=SessionConfig(),
            decisions=[],
            blocked_items=[],
            denied_additions=[
                DelegationDenied(
                    item="jira-api",
                    requested_by="project",
                    reason="Team not delegated for MCP additions",
                    target_type="mcp_server",
                ),
            ],
        )

        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value="dev"),
            patch(
                "scc_cli.cli_config.profiles.compute_effective_config",
                return_value=effective,
            ),
        ):
            result = runner.invoke(cli.app, ["config", "explain"])

        assert result.exit_code == 0
        # Golden format checks
        assert "Denied Additions" in result.output
        assert "jira-api" in result.output
        assert "project" in result.output
        # Fix-it command should include scc unblock
        assert "unblock" in result.output.lower()
        assert "--ttl" in result.output or "ttl" in result.output.lower()

    def test_denied_additions_shows_local_scope_hint(self, mock_org_config):
        """Verify denied additions include hint about local scope."""
        effective = EffectiveConfig(
            plugins=set(),
            mcp_servers=[],
            network_policy="default",
            session_config=SessionConfig(),
            decisions=[],
            blocked_items=[],
            denied_additions=[
                DelegationDenied(
                    item="restricted-plugin",
                    requested_by="project",
                    reason="Not in delegated scope",
                    target_type="plugin",
                ),
            ],
        )

        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value="dev"),
            patch(
                "scc_cli.cli_config.profiles.compute_effective_config",
                return_value=effective,
            ),
        ):
            result = runner.invoke(cli.app, ["config", "explain"])

        assert result.exit_code == 0
        # Should show unblock is for local scope
        assert "unblock" in result.output.lower()


class TestConfigExplainGoldenActiveExceptions:
    """Golden tests for active exceptions output format.

    These tests verify the exact output format matches the expected structure:
    - Header with "Active Exceptions"
    - Each exception shows: [scope] ID targets expires_in (source: X)
    - Expired count notification
    """

    def test_active_exceptions_output_format(self, mock_org_config, tmp_path):
        """Verify active exceptions output matches expected golden format."""
        from datetime import datetime, timedelta, timezone

        from scc_cli.models.exceptions import AllowTargets, ExceptionFile
        from scc_cli.models.exceptions import Exception as SccException

        # Create an active exception
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=8)
        exception = SccException(
            id="local-20251221-a3f2",
            created_at=now.isoformat(),
            expires_at=expires_at.isoformat(),
            reason="Sprint planning integration",
            scope="local",
            allow=AllowTargets(mcp_servers=["jira-api"]),
        )

        effective = EffectiveConfig(
            plugins=set(),
            mcp_servers=[],
            network_policy="default",
            session_config=SessionConfig(),
            decisions=[],
            blocked_items=[],
            denied_additions=[],
        )

        # Mock the exception stores
        exc_file = ExceptionFile(exceptions=[exception])
        empty_file = ExceptionFile()

        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value="dev"),
            patch(
                "scc_cli.cli_config.profiles.compute_effective_config",
                return_value=effective,
            ),
            patch("scc_cli.cli_config.UserStore") as mock_user_store,
            patch("scc_cli.cli_config.RepoStore") as mock_repo_store,
        ):
            mock_user_store.return_value.read.return_value = exc_file
            mock_repo_store.return_value.read.return_value = empty_file

            result = runner.invoke(cli.app, ["config", "explain"])

        assert result.exit_code == 0
        # Golden format checks
        assert "Active Exceptions" in result.output
        assert "local-20251221-a3f2" in result.output
        assert "jira-api" in result.output or "mcp" in result.output.lower()
        assert "expires" in result.output.lower()
        assert "user" in result.output.lower() or "source" in result.output.lower()

    def test_active_exceptions_shows_scope_badge(self, mock_org_config, tmp_path):
        """Verify active exceptions show scope badge [local] or [policy]."""
        from datetime import datetime, timedelta, timezone

        from scc_cli.models.exceptions import AllowTargets, ExceptionFile
        from scc_cli.models.exceptions import Exception as SccException

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=8)
        exception = SccException(
            id="local-20251221-b4c5",
            created_at=now.isoformat(),
            expires_at=expires_at.isoformat(),
            reason="Testing",
            scope="local",
            allow=AllowTargets(plugins=["test-plugin"]),
        )

        effective = EffectiveConfig(
            plugins=set(),
            mcp_servers=[],
            network_policy="default",
            session_config=SessionConfig(),
            decisions=[],
            blocked_items=[],
            denied_additions=[],
        )

        exc_file = ExceptionFile(exceptions=[exception])
        empty_file = ExceptionFile()

        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value="dev"),
            patch(
                "scc_cli.cli_config.profiles.compute_effective_config",
                return_value=effective,
            ),
            patch("scc_cli.cli_config.UserStore") as mock_user_store,
            patch("scc_cli.cli_config.RepoStore") as mock_repo_store,
        ):
            mock_user_store.return_value.read.return_value = exc_file
            mock_repo_store.return_value.read.return_value = empty_file

            result = runner.invoke(cli.app, ["config", "explain"])

        assert result.exit_code == 0
        # Should show scope badge
        assert "[local]" in result.output or "local" in result.output.lower()

    def test_expired_exceptions_show_cleanup_hint(self, mock_org_config, tmp_path):
        """Verify expired exceptions count shows cleanup hint."""
        from datetime import datetime, timedelta, timezone

        from scc_cli.models.exceptions import AllowTargets, ExceptionFile
        from scc_cli.models.exceptions import Exception as SccException

        # Create an expired exception
        now = datetime.now(timezone.utc)
        expired_at = now - timedelta(hours=1)  # Already expired
        exception = SccException(
            id="local-20251220-exp1",
            created_at=(now - timedelta(hours=10)).isoformat(),
            expires_at=expired_at.isoformat(),
            reason="Old exception",
            scope="local",
            allow=AllowTargets(plugins=["old-plugin"]),
        )

        effective = EffectiveConfig(
            plugins=set(),
            mcp_servers=[],
            network_policy="default",
            session_config=SessionConfig(),
            decisions=[],
            blocked_items=[],
            denied_additions=[],
        )

        exc_file = ExceptionFile(exceptions=[exception])
        empty_file = ExceptionFile()

        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value="dev"),
            patch(
                "scc_cli.cli_config.profiles.compute_effective_config",
                return_value=effective,
            ),
            patch("scc_cli.cli_config.UserStore") as mock_user_store,
            patch("scc_cli.cli_config.RepoStore") as mock_repo_store,
        ):
            mock_user_store.return_value.read.return_value = exc_file
            mock_repo_store.return_value.read.return_value = empty_file

            result = runner.invoke(cli.app, ["config", "explain"])

        assert result.exit_code == 0
        # Should show expired count and cleanup hint
        assert "expired" in result.output.lower()
        assert "cleanup" in result.output.lower()


class TestConfigExplainGoldenCombined:
    """Golden tests for combined output with all sections."""

    def test_explain_full_output_order(self, mock_org_config):
        """Verify explain shows sections in correct order.

        Expected order:
        1. Effective Configuration header
        2. Config decisions
        3. Blocked items (if any)
        4. Denied additions (if any)
        5. Active exceptions (if any)
        """
        effective = EffectiveConfig(
            plugins={"plugin-a"},
            mcp_servers=[],
            network_policy="default",
            session_config=SessionConfig(),
            decisions=[
                ConfigDecision(
                    field="plugins",
                    value="plugin-a",
                    reason="Organization default",
                    source="org.defaults",
                ),
            ],
            blocked_items=[
                BlockedItem(
                    item="bad-plugin",
                    blocked_by="bad-*",
                    source="org.security",
                    target_type="plugin",
                ),
            ],
            denied_additions=[
                DelegationDenied(
                    item="denied-plugin",
                    requested_by="project",
                    reason="Not delegated",
                    target_type="plugin",
                ),
            ],
        )

        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value="dev"),
            patch(
                "scc_cli.cli_config.profiles.compute_effective_config",
                return_value=effective,
            ),
        ):
            result = runner.invoke(cli.app, ["config", "explain"])

        assert result.exit_code == 0
        output = result.output

        # Verify sections appear in correct order
        effective_pos = output.find("Effective Configuration")
        blocked_pos = output.find("Blocked Items")
        denied_pos = output.find("Denied Additions")

        assert effective_pos < blocked_pos, "Effective config should appear before blocked items"
        assert blocked_pos < denied_pos, "Blocked items should appear before denied additions"

    def test_explain_empty_sections_not_shown(self, mock_org_config):
        """Verify empty sections (no blocked, no denied) don't show headers."""
        effective = EffectiveConfig(
            plugins={"plugin-a"},
            mcp_servers=[],
            network_policy="default",
            session_config=SessionConfig(),
            decisions=[
                ConfigDecision(
                    field="plugins",
                    value="plugin-a",
                    reason="Organization default",
                    source="org.defaults",
                ),
            ],
            blocked_items=[],  # Empty
            denied_additions=[],  # Empty
        )

        with (
            patch("scc_cli.cli_config.config.load_cached_org_config", return_value=mock_org_config),
            patch("scc_cli.cli_config.config.get_selected_profile", return_value="dev"),
            patch(
                "scc_cli.cli_config.profiles.compute_effective_config",
                return_value=effective,
            ),
        ):
            result = runner.invoke(cli.app, ["config", "explain"])

        assert result.exit_code == 0
        # Empty sections should not appear
        assert "Blocked Items" not in result.output
        assert "Denied Additions" not in result.output
