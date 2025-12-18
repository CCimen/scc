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
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from scc_cli import cli
from scc_cli.profiles import (
    BlockedItem,
    ConfigDecision,
    DelegationDenied,
    EffectiveConfig,
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
        "profiles": {
            "dev": {"description": "Dev team"}
        },
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
            patch("scc_cli.cli_config.profiles.compute_effective_config", return_value=effective_config_basic),
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
            patch("scc_cli.cli_config.profiles.compute_effective_config", return_value=effective_config_basic),
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
            patch("scc_cli.cli_config.profiles.compute_effective_config", return_value=effective_config_basic),
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
            patch("scc_cli.cli_config.profiles.compute_effective_config", return_value=effective_config_with_blocked),
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
            patch("scc_cli.cli_config.profiles.compute_effective_config", return_value=effective_config_with_blocked),
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
            patch("scc_cli.cli_config.profiles.compute_effective_config", return_value=effective_config_with_denied),
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
            patch("scc_cli.cli_config.profiles.compute_effective_config", return_value=effective_config_with_denied),
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
            patch("scc_cli.cli_config.profiles.compute_effective_config", return_value=effective_config_full),
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
            patch("scc_cli.cli_config.profiles.compute_effective_config", return_value=effective_config_full),
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
            patch("scc_cli.cli_config.profiles.compute_effective_config", return_value=effective_config_basic) as mock_compute,
        ):
            result = runner.invoke(
                cli.app, ["config", "explain", "--workspace", str(workspace)]
            )

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
            patch("scc_cli.cli_config.profiles.compute_effective_config", return_value=effective_config_basic) as mock_compute,
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
        assert result.exit_code != 0 or "no org" in result.output.lower() or "setup" in result.output.lower()

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
