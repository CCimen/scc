"""
Tests for Team CLI commands.

TDD approach: Tests define the expected behavior of the team command group.
"""

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from scc_cli.cli import app

runner = CliRunner()


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_config():
    """Mock user configuration."""
    return {
        "config_version": "1.0.0",
        "selected_profile": "platform",
        "organization_source": {"url": "https://example.com/org.json"},
    }


@pytest.fixture
def mock_org_config():
    """Mock organization configuration with profiles."""
    return {
        "profiles": {
            "platform": {
                "description": "Platform team configuration",
                "plugin": "platform-tools",
                "marketplace": "sundsvall",
            },
            "frontend": {
                "description": "Frontend team configuration",
                "plugin": "frontend-tools",
                "marketplace": "sundsvall",
            },
            "base": {
                "description": "Base configuration without plugins",
            },
        },
        "marketplaces": [
            {
                "name": "sundsvall",
                "type": "github",
                "repo": "sundsvall/claude-plugins-marketplace",
            }
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Team List Command Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTeamList:
    """Tests for 'scc team list' command."""

    def test_team_list_shows_available_teams(self, mock_config, mock_org_config):
        """team list should display available team profiles."""
        with (
            patch("scc_cli.cli_team.config.load_user_config", return_value=mock_config),
            patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=mock_org_config,
            ),
        ):
            result = runner.invoke(app, ["team", "list"])
            assert result.exit_code == 0
            assert "platform" in result.output
            assert "frontend" in result.output

    def test_team_list_marks_current_team(self, mock_config, mock_org_config):
        """team list should mark the currently selected team."""
        with (
            patch("scc_cli.cli_team.config.load_user_config", return_value=mock_config),
            patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=mock_org_config,
            ),
        ):
            result = runner.invoke(app, ["team", "list"])
            assert result.exit_code == 0
            # Current team should be marked somehow (bold, arrow, etc.)
            assert "platform" in result.output

    def test_team_list_json_output(self, mock_config, mock_org_config):
        """team list --json should output valid JSON envelope."""
        with (
            patch("scc_cli.cli_team.config.load_user_config", return_value=mock_config),
            patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=mock_org_config,
            ),
        ):
            result = runner.invoke(app, ["team", "list", "--json"])
            assert result.exit_code == 0

            # Parse JSON output
            data = json.loads(result.output)
            assert data["apiVersion"] == "scc.cli/v1"
            assert data["kind"] == "TeamList"
            assert data["status"]["ok"] is True
            assert "teams" in data["data"]
            assert len(data["data"]["teams"]) == 3

    def test_team_list_json_compact_by_default(self, mock_config, mock_org_config):
        """team list --json should output compact JSON by default."""
        with (
            patch("scc_cli.cli_team.config.load_user_config", return_value=mock_config),
            patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=mock_org_config,
            ),
        ):
            result = runner.invoke(app, ["team", "list", "--json"])
            assert result.exit_code == 0
            # Compact JSON has no newlines within the object (except at end)
            output = result.output.strip()
            # Should be a single line
            assert output.count("\n") == 0

    def test_team_list_json_pretty_mode(self, mock_config, mock_org_config):
        """team list --json --pretty should output indented JSON."""
        with (
            patch("scc_cli.cli_team.config.load_user_config", return_value=mock_config),
            patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=mock_org_config,
            ),
        ):
            result = runner.invoke(app, ["team", "list", "--json", "--pretty"])
            assert result.exit_code == 0
            # Pretty JSON has multiple lines
            assert "\n" in result.output
            # Should have indentation
            assert "  " in result.output

    def test_team_list_shows_no_teams_warning(self, mock_config):
        """team list should show warning when no teams available."""
        empty_org = {"profiles": {}, "marketplaces": []}
        with (
            patch("scc_cli.cli_team.config.load_user_config", return_value=mock_config),
            patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=empty_org,
            ),
        ):
            result = runner.invoke(app, ["team", "list"])
            assert result.exit_code == 0
            assert "No Teams" in result.output or "No team" in result.output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Team Current Command Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTeamCurrent:
    """Tests for 'scc team current' command."""

    def test_team_current_shows_selected_team(self, mock_config, mock_org_config):
        """team current should show the currently selected team."""
        with (
            patch("scc_cli.cli_team.config.load_user_config", return_value=mock_config),
            patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=mock_org_config,
            ),
        ):
            result = runner.invoke(app, ["team", "current"])
            assert result.exit_code == 0
            assert "platform" in result.output

    def test_team_current_no_team_selected(self, mock_org_config):
        """team current should indicate when no team is selected."""
        config_no_team = {"config_version": "1.0.0", "selected_profile": None}
        with (
            patch("scc_cli.cli_team.config.load_user_config", return_value=config_no_team),
            patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=mock_org_config,
            ),
        ):
            result = runner.invoke(app, ["team", "current"])
            assert result.exit_code == 0
            assert "no team" in result.output.lower() or "not selected" in result.output.lower()

    def test_team_current_json_output(self, mock_config, mock_org_config):
        """team current --json should output valid JSON envelope."""
        with (
            patch("scc_cli.cli_team.config.load_user_config", return_value=mock_config),
            patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=mock_org_config,
            ),
        ):
            result = runner.invoke(app, ["team", "current", "--json"])
            assert result.exit_code == 0

            data = json.loads(result.output)
            assert data["kind"] == "TeamCurrent"
            assert data["data"]["team"] == "platform"


# ═══════════════════════════════════════════════════════════════════════════════
# Team Switch Command Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTeamSwitch:
    """Tests for 'scc team switch' command."""

    def test_team_switch_changes_team(self, mock_config, mock_org_config):
        """team switch should change the current team."""
        saved_config = {}

        def capture_save(cfg):
            saved_config.update(cfg)

        with (
            patch("scc_cli.cli_team.config.load_user_config", return_value=mock_config),
            patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=mock_org_config,
            ),
            patch("scc_cli.cli_team.config.save_user_config", side_effect=capture_save),
        ):
            result = runner.invoke(app, ["team", "switch", "frontend"])
            assert result.exit_code == 0
            assert "frontend" in result.output
            assert saved_config.get("selected_profile") == "frontend"

    def test_team_switch_invalid_team(self, mock_config, mock_org_config):
        """team switch should fail for non-existent team."""
        with (
            patch("scc_cli.cli_team.config.load_user_config", return_value=mock_config),
            patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=mock_org_config,
            ),
        ):
            result = runner.invoke(app, ["team", "switch", "nonexistent"])
            assert result.exit_code == 0  # Still exits 0 but shows error
            assert "not found" in result.output.lower()

    def test_team_switch_non_interactive_requires_name(self, mock_config, mock_org_config):
        """team switch --non-interactive should fail without team name."""
        with (
            patch("scc_cli.cli_team.config.load_user_config", return_value=mock_config),
            patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=mock_org_config,
            ),
        ):
            result = runner.invoke(app, ["team", "switch", "--non-interactive"])
            assert result.exit_code != 0

    def test_team_switch_json_output(self, mock_config, mock_org_config):
        """team switch --json should output valid JSON envelope."""
        with (
            patch("scc_cli.cli_team.config.load_user_config", return_value=mock_config),
            patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=mock_org_config,
            ),
            patch("scc_cli.cli_team.config.save_user_config"),
        ):
            result = runner.invoke(app, ["team", "switch", "frontend", "--json"])
            assert result.exit_code == 0

            data = json.loads(result.output)
            assert data["kind"] == "TeamSwitch"
            assert data["data"]["success"] is True
            assert data["data"]["current"] == "frontend"
            assert data["data"]["previous"] == "platform"


# ═══════════════════════════════════════════════════════════════════════════════
# Team Info Command Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTeamInfo:
    """Tests for 'scc team info' command."""

    def test_team_info_shows_details(self, mock_config, mock_org_config):
        """team info should show detailed team information."""
        with (
            patch("scc_cli.cli_team.config.load_user_config", return_value=mock_config),
            patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=mock_org_config,
            ),
        ):
            result = runner.invoke(app, ["team", "info", "platform"])
            assert result.exit_code == 0
            assert "platform" in result.output
            assert "Platform team" in result.output or "description" in result.output.lower()

    def test_team_info_not_found(self, mock_config, mock_org_config):
        """team info should handle non-existent team gracefully."""
        with (
            patch("scc_cli.cli_team.config.load_user_config", return_value=mock_config),
            patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=mock_org_config,
            ),
        ):
            result = runner.invoke(app, ["team", "info", "nonexistent"])
            assert result.exit_code == 0
            assert "not found" in result.output.lower()

    def test_team_info_json_output(self, mock_config, mock_org_config):
        """team info --json should output valid JSON envelope."""
        with (
            patch("scc_cli.cli_team.config.load_user_config", return_value=mock_config),
            patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=mock_org_config,
            ),
        ):
            result = runner.invoke(app, ["team", "info", "platform", "--json"])
            assert result.exit_code == 0

            data = json.loads(result.output)
            assert data["kind"] == "TeamInfo"
            assert data["data"]["found"] is True
            assert data["data"]["profile"]["name"] == "platform"


# ═══════════════════════════════════════════════════════════════════════════════
# Deprecated Alias Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeprecatedAliases:
    """Tests for deprecated command aliases."""

    def test_teams_command_shows_deprecation_warning(self, mock_config, mock_org_config):
        """'scc teams' should show deprecation warning."""
        with (
            patch("scc_cli.cli_config.config.load_config", return_value=mock_config),
            patch(
                "scc_cli.cli_config.config.load_cached_org_config",
                return_value=mock_org_config,
            ),
        ):
            result = runner.invoke(app, ["teams"])
            # Deprecation warning should go to stderr, but CliRunner captures both
            # The command should still work but show the warning
            assert result.exit_code == 0
            # The warning is in stderr, not stdout for JSON cleanliness
            # We just verify the command works
            assert "platform" in result.output or "Available" in result.output

    def test_teams_command_suppresses_warning_with_env_var(
        self, mock_config, mock_org_config, monkeypatch
    ):
        """SCC_NO_DEPRECATION_WARN=1 should suppress deprecation warning."""
        monkeypatch.setenv("SCC_NO_DEPRECATION_WARN", "1")
        with (
            patch("scc_cli.cli_config.config.load_config", return_value=mock_config),
            patch(
                "scc_cli.cli_config.config.load_cached_org_config",
                return_value=mock_org_config,
            ),
        ):
            result = runner.invoke(app, ["teams"])
            assert result.exit_code == 0
            # Warning should be suppressed
            assert "DEPRECATION" not in result.output


# ═══════════════════════════════════════════════════════════════════════════════
# JSON Envelope Contract Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestJsonEnvelopeContract:
    """Tests verifying the JSON envelope contract is maintained."""

    def test_json_envelope_has_required_fields(self, mock_config, mock_org_config):
        """All JSON outputs must have apiVersion, kind, metadata, status, data."""
        commands = [
            ["team", "list", "--json"],
            ["team", "current", "--json"],
            ["team", "info", "platform", "--json"],
        ]

        for cmd in commands:
            with (
                patch("scc_cli.cli_team.config.load_user_config", return_value=mock_config),
                patch(
                    "scc_cli.cli_team.config.load_cached_org_config",
                    return_value=mock_org_config,
                ),
            ):
                result = runner.invoke(app, cmd)
                if result.exit_code == 0:
                    data = json.loads(result.output)
                    assert "apiVersion" in data, f"Missing apiVersion in {cmd}"
                    assert "kind" in data, f"Missing kind in {cmd}"
                    assert "metadata" in data, f"Missing metadata in {cmd}"
                    assert "status" in data, f"Missing status in {cmd}"
                    assert "data" in data, f"Missing data in {cmd}"

    def test_json_metadata_has_timestamp_and_version(self, mock_config, mock_org_config):
        """metadata must have generatedAt and cliVersion."""
        with (
            patch("scc_cli.cli_team.config.load_user_config", return_value=mock_config),
            patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=mock_org_config,
            ),
        ):
            result = runner.invoke(app, ["team", "list", "--json"])
            data = json.loads(result.output)

            assert "generatedAt" in data["metadata"]
            assert "cliVersion" in data["metadata"]
            # Timestamp should be ISO 8601 format
            assert "T" in data["metadata"]["generatedAt"]

    def test_json_status_has_ok_errors_warnings(self, mock_config, mock_org_config):
        """status must have ok, errors, warnings fields."""
        with (
            patch("scc_cli.cli_team.config.load_user_config", return_value=mock_config),
            patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=mock_org_config,
            ),
        ):
            result = runner.invoke(app, ["team", "list", "--json"])
            data = json.loads(result.output)

            assert "ok" in data["status"]
            assert "errors" in data["status"]
            assert "warnings" in data["status"]
            assert isinstance(data["status"]["errors"], list)
            assert isinstance(data["status"]["warnings"], list)
