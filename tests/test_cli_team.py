"""
Tests for scc team CLI commands.

TDD: Tests written before implementation validation.
Tests cover: team list, team current, team switch, team info commands.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

if TYPE_CHECKING:
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a Typer CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def sample_teams() -> list[dict]:
    """Sample list of teams for testing."""
    return [
        {"name": "backend", "description": "Backend development team", "plugin": "backend-tools"},
        {"name": "frontend", "description": "Frontend development team", "plugin": "frontend-kit"},
        {"name": "platform", "description": "Platform engineering", "plugin": None},
    ]


@pytest.fixture
def user_config_with_team() -> dict:
    """User config with a selected team."""
    return {
        "selected_profile": "backend",
        "organization_source": {
            "url": "https://example.com/org.json",
        },
    }


@pytest.fixture
def user_config_no_team() -> dict:
    """User config with no selected team."""
    return {
        "organization_source": {
            "url": "https://example.com/org.json",
        },
    }


@pytest.fixture
def org_config_with_profiles() -> dict:
    """Org config with team profiles."""
    return {
        "schema_version": "1.0.0",
        "organization": {
            "name": "acme-corp",
            "id": "acme-corp",
        },
        "profiles": {
            "backend": {"description": "Backend team"},
            "frontend": {"description": "Frontend team"},
            "platform": {"description": "Platform team"},
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Team List Command Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTeamList:
    """Tests for scc team list command."""

    def test_list_shows_available_teams(
        self, cli_runner: CliRunner, sample_teams: list[dict], user_config_with_team: dict
    ) -> None:
        """List command should display available teams."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.list_teams", return_value=sample_teams):
                    result = cli_runner.invoke(team_app, ["list"])

        assert result.exit_code == 0
        assert "backend" in result.stdout
        assert "frontend" in result.stdout
        assert "platform" in result.stdout

    def test_list_marks_current_team(
        self, cli_runner: CliRunner, sample_teams: list[dict], user_config_with_team: dict
    ) -> None:
        """Current team should be marked in the list."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.list_teams", return_value=sample_teams):
                    result = cli_runner.invoke(team_app, ["list"])

        assert result.exit_code == 0
        # Current team should have an indicator
        assert "←" in result.stdout or "current" in result.stdout.lower()

    def test_list_no_teams_shows_message(
        self, cli_runner: CliRunner, user_config_with_team: dict
    ) -> None:
        """Should show message when no teams available."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.list_teams", return_value=[]):
                    result = cli_runner.invoke(team_app, ["list"])

        assert result.exit_code == 0
        output_lower = result.stdout.lower()
        assert "no team" in output_lower or "none" in output_lower

    def test_list_json_output(
        self, cli_runner: CliRunner, sample_teams: list[dict], user_config_with_team: dict
    ) -> None:
        """--json should return proper JSON envelope."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.list_teams", return_value=sample_teams):
                    result = cli_runner.invoke(team_app, ["list", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"]["ok"] is True
        assert "teams" in data["data"]
        assert len(data["data"]["teams"]) == 3

    def test_list_json_includes_current_marker(
        self, cli_runner: CliRunner, sample_teams: list[dict], user_config_with_team: dict
    ) -> None:
        """JSON output should include is_current field for teams."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.list_teams", return_value=sample_teams):
                    result = cli_runner.invoke(team_app, ["list", "--json"])

        data = json.loads(result.stdout)
        teams = data["data"]["teams"]

        # Backend is current
        backend = next(t for t in teams if t["name"] == "backend")
        assert backend["is_current"] is True

        # Others are not current
        frontend = next(t for t in teams if t["name"] == "frontend")
        assert frontend["is_current"] is False

    def test_list_with_sync_fetches_fresh_config(
        self, cli_runner: CliRunner, sample_teams: list[dict], user_config_with_team: dict
    ) -> None:
        """--sync should fetch fresh config from organization."""
        from scc_cli.cli_team import team_app

        mock_fetch_return = ({"profiles": {}}, '"etag123"', 200)

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.list_teams", return_value=sample_teams):
                    with patch(
                        "scc_cli.cli_team.config.CACHE_DIR",
                        new=MagicMock(mkdir=MagicMock()),
                    ):
                        with patch(
                            "scc_cli.remote.fetch_org_config", return_value=mock_fetch_return
                        ) as mock_fetch:
                            result = cli_runner.invoke(team_app, ["list", "--sync"])

        # Should attempt to fetch
        mock_fetch.assert_called_once()
        assert result.exit_code == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Team Current Command Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTeamCurrent:
    """Tests for scc team current command."""

    def test_current_shows_selected_team(
        self, cli_runner: CliRunner, user_config_with_team: dict
    ) -> None:
        """Should display the currently selected team."""
        from scc_cli.cli_team import team_app

        team_details = {
            "name": "backend",
            "description": "Backend development team",
            "plugin": "backend-tools",
        }

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.get_team_details", return_value=team_details):
                    result = cli_runner.invoke(team_app, ["current"])

        assert result.exit_code == 0
        assert "backend" in result.stdout

    def test_current_no_team_selected(
        self, cli_runner: CliRunner, user_config_no_team: dict
    ) -> None:
        """Should show message when no team selected."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_no_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                result = cli_runner.invoke(team_app, ["current"])

        assert result.exit_code == 0
        output_lower = result.stdout.lower()
        assert "no team" in output_lower or "not selected" in output_lower

    def test_current_team_not_found(
        self, cli_runner: CliRunner, user_config_with_team: dict
    ) -> None:
        """Should handle case where selected team no longer exists."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.get_team_details", return_value=None):
                    result = cli_runner.invoke(team_app, ["current"])

        assert result.exit_code == 0
        output_lower = result.stdout.lower()
        assert "not found" in output_lower or "backend" in output_lower

    def test_current_json_output(self, cli_runner: CliRunner, user_config_with_team: dict) -> None:
        """--json should return proper JSON envelope with team info."""
        from scc_cli.cli_team import team_app

        team_details = {
            "name": "backend",
            "description": "Backend development team",
            "plugin": "backend-tools",
            "marketplace": "internal",
        }

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.get_team_details", return_value=team_details):
                    result = cli_runner.invoke(team_app, ["current", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"]["ok"] is True
        assert data["data"]["team"] == "backend"
        assert data["data"]["profile"]["plugin"] == "backend-tools"

    def test_current_json_no_team(self, cli_runner: CliRunner, user_config_no_team: dict) -> None:
        """--json with no team should return null team."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_no_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                result = cli_runner.invoke(team_app, ["current", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["data"]["team"] is None


# ═══════════════════════════════════════════════════════════════════════════════
# Team Switch Command Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTeamSwitch:
    """Tests for scc team switch command."""

    def test_switch_to_valid_team(
        self, cli_runner: CliRunner, sample_teams: list[dict], user_config_with_team: dict
    ) -> None:
        """Should successfully switch to a valid team."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.list_teams", return_value=sample_teams):
                    with patch("scc_cli.cli_team.config.save_user_config") as mock_save:
                        result = cli_runner.invoke(team_app, ["switch", "frontend"])

        assert result.exit_code == 0
        assert "frontend" in result.stdout.lower() or "switched" in result.stdout.lower()
        mock_save.assert_called_once()

        # Verify the saved config has the new team
        saved_config = mock_save.call_args[0][0]
        assert saved_config["selected_profile"] == "frontend"

    def test_switch_to_nonexistent_team(
        self, cli_runner: CliRunner, sample_teams: list[dict], user_config_with_team: dict
    ) -> None:
        """Should show error for non-existent team."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.list_teams", return_value=sample_teams):
                    with patch("scc_cli.cli_team.config.save_user_config") as mock_save:
                        result = cli_runner.invoke(team_app, ["switch", "nonexistent"])

        # Should not save config
        mock_save.assert_not_called()
        # Should show error
        output_lower = result.stdout.lower()
        assert "not found" in output_lower or "nonexistent" in output_lower

    def test_switch_no_teams_available(
        self, cli_runner: CliRunner, user_config_with_team: dict
    ) -> None:
        """Should show message when no teams available."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.list_teams", return_value=[]):
                    result = cli_runner.invoke(team_app, ["switch", "backend"])

        output_lower = result.stdout.lower()
        assert "no teams" in output_lower or "not available" in output_lower

    def test_switch_non_interactive_requires_team_name(
        self, cli_runner: CliRunner, sample_teams: list[dict], user_config_with_team: dict
    ) -> None:
        """--non-interactive should fail without team name."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.list_teams", return_value=sample_teams):
                    result = cli_runner.invoke(team_app, ["switch", "--non-interactive"])

        assert result.exit_code != 0

    def test_switch_json_output_success(
        self, cli_runner: CliRunner, sample_teams: list[dict], user_config_with_team: dict
    ) -> None:
        """--json should return success envelope on valid switch."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.list_teams", return_value=sample_teams):
                    with patch("scc_cli.cli_team.config.save_user_config"):
                        result = cli_runner.invoke(team_app, ["switch", "frontend", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"]["ok"] is True
        assert data["data"]["success"] is True
        assert data["data"]["previous"] == "backend"
        assert data["data"]["current"] == "frontend"

    def test_switch_json_output_failure(
        self, cli_runner: CliRunner, sample_teams: list[dict], user_config_with_team: dict
    ) -> None:
        """--json should return error info for invalid team."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.list_teams", return_value=sample_teams):
                    result = cli_runner.invoke(team_app, ["switch", "nonexistent", "--json"])

        assert result.exit_code == 0  # JSON mode returns 0 with error in payload
        data = json.loads(result.stdout)
        assert data["data"]["success"] is False
        assert data["data"]["error"] == "team_not_found"


# ═══════════════════════════════════════════════════════════════════════════════
# Team Info Command Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTeamInfo:
    """Tests for scc team info command."""

    def test_info_shows_team_details(
        self, cli_runner: CliRunner, user_config_with_team: dict
    ) -> None:
        """Should display detailed team information."""
        from scc_cli.cli_team import team_app

        team_details = {
            "name": "backend",
            "description": "Backend development team",
            "plugin": "backend-tools",
            "marketplace": "internal",
            "marketplace_repo": "https://github.com/acme/plugins",
        }
        validation = {"valid": True, "warnings": [], "errors": []}

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.get_team_details", return_value=team_details):
                    with patch(
                        "scc_cli.cli_team.teams.validate_team_profile", return_value=validation
                    ):
                        result = cli_runner.invoke(team_app, ["info", "backend"])

        assert result.exit_code == 0
        assert "backend" in result.stdout.lower()
        assert "backend-tools" in result.stdout or "plugin" in result.stdout.lower()

    def test_info_team_not_found(self, cli_runner: CliRunner, user_config_with_team: dict) -> None:
        """Should show not found for missing team."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.get_team_details", return_value=None):
                    result = cli_runner.invoke(team_app, ["info", "nonexistent"])

        assert result.exit_code == 0
        output_lower = result.stdout.lower()
        assert "not found" in output_lower or "no team" in output_lower

    def test_info_shows_validation_warnings(
        self, cli_runner: CliRunner, user_config_with_team: dict
    ) -> None:
        """Should display validation warnings."""
        from scc_cli.cli_team import team_app

        team_details = {
            "name": "backend",
            "description": "Backend team",
            "plugin": "missing-plugin",
        }
        validation = {
            "valid": True,
            "warnings": ["Plugin 'missing-plugin' not found in marketplace"],
            "errors": [],
        }

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.get_team_details", return_value=team_details):
                    with patch(
                        "scc_cli.cli_team.teams.validate_team_profile", return_value=validation
                    ):
                        result = cli_runner.invoke(team_app, ["info", "backend"])

        assert result.exit_code == 0
        output_lower = result.stdout.lower()
        assert "warning" in output_lower or "missing-plugin" in output_lower

    def test_info_json_output_found(
        self, cli_runner: CliRunner, user_config_with_team: dict
    ) -> None:
        """--json should return full team profile info."""
        from scc_cli.cli_team import team_app

        team_details = {
            "name": "backend",
            "description": "Backend development team",
            "plugin": "backend-tools",
            "marketplace": "internal",
            "marketplace_type": "github",
            "marketplace_repo": "https://github.com/acme/plugins",
        }
        validation = {"valid": True, "warnings": [], "errors": []}

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.get_team_details", return_value=team_details):
                    with patch(
                        "scc_cli.cli_team.teams.validate_team_profile", return_value=validation
                    ):
                        result = cli_runner.invoke(team_app, ["info", "backend", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["status"]["ok"] is True
        assert data["data"]["found"] is True
        assert data["data"]["profile"]["plugin"] == "backend-tools"
        assert data["data"]["validation"]["valid"] is True

    def test_info_json_output_not_found(
        self, cli_runner: CliRunner, user_config_with_team: dict
    ) -> None:
        """--json should return found=false for missing team."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.get_team_details", return_value=None):
                    result = cli_runner.invoke(team_app, ["info", "nonexistent", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["data"]["found"] is False
        assert data["data"]["profile"] is None

    def test_info_requires_team_name(self, cli_runner: CliRunner) -> None:
        """Info command should require team name argument."""
        from scc_cli.cli_team import team_app

        result = cli_runner.invoke(team_app, ["info"])

        assert result.exit_code != 0


# ═══════════════════════════════════════════════════════════════════════════════
# Edge Cases and Error Handling Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTeamCommandEdgeCases:
    """Edge case and error handling tests."""

    def test_list_truncates_long_descriptions(
        self, cli_runner: CliRunner, user_config_with_team: dict
    ) -> None:
        """Descriptions should be truncated without --verbose."""
        from scc_cli.cli_team import team_app

        long_desc_teams = [
            {
                "name": "test",
                "description": "A" * 100,  # Very long description
                "plugin": None,
            }
        ]

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.list_teams", return_value=long_desc_teams):
                    result = cli_runner.invoke(team_app, ["list"])

        assert result.exit_code == 0
        # Should be truncated (not all 100 A's)
        assert "..." in result.stdout

    def test_list_verbose_shows_full_descriptions(
        self, cli_runner: CliRunner, user_config_with_team: dict
    ) -> None:
        """--verbose should show full descriptions."""
        from scc_cli.cli_team import team_app

        long_desc_teams = [
            {
                "name": "test",
                "description": "A" * 100,  # Very long description
                "plugin": None,
            }
        ]

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.list_teams", return_value=long_desc_teams):
                    result = cli_runner.invoke(team_app, ["list", "--verbose"])

        assert result.exit_code == 0
        # Should contain many A's (not truncated)
        # In verbose mode, description is shown fully
        assert "A" * 50 in result.stdout  # At least 50 A's visible

    def test_switch_same_team_succeeds(
        self, cli_runner: CliRunner, sample_teams: list[dict], user_config_with_team: dict
    ) -> None:
        """Switching to the same team should succeed."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.list_teams", return_value=sample_teams):
                    with patch("scc_cli.cli_team.config.save_user_config"):
                        result = cli_runner.invoke(team_app, ["switch", "backend"])

        assert result.exit_code == 0

    def test_info_base_profile_no_plugin(
        self, cli_runner: CliRunner, user_config_with_team: dict
    ) -> None:
        """Info for profile with no plugin should show 'base profile'."""
        from scc_cli.cli_team import team_app

        team_details = {
            "name": "platform",
            "description": "Platform engineering",
            "plugin": None,  # No plugin
        }
        validation = {"valid": True, "warnings": [], "errors": []}

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch("scc_cli.cli_team.config.load_cached_org_config", return_value={}):
                with patch("scc_cli.cli_team.teams.get_team_details", return_value=team_details):
                    with patch(
                        "scc_cli.cli_team.teams.validate_team_profile", return_value=validation
                    ):
                        result = cli_runner.invoke(team_app, ["info", "platform"])

        assert result.exit_code == 0
        output_lower = result.stdout.lower()
        assert "base" in output_lower or "none" in output_lower


# ═══════════════════════════════════════════════════════════════════════════════
# Federated Team Switch Tests (Phase 2)
# ═══════════════════════════════════════════════════════════════════════════════


class TestTeamSwitchFederated:
    """Tests for scc team switch with federated team configurations."""

    @pytest.fixture
    def org_config_with_federated_team(self) -> dict:
        """Org config with a federated team (has config_source)."""
        return {
            "name": "acme-corp",
            "schema_version": "1.0.0",
            "organization": {
                "name": "acme-corp",
                "id": "acme-corp",
            },
            "profiles": {
                "backend": {
                    "name": "backend",
                    "description": "Backend team (inline)",
                    # No config_source = inline team
                },
                "frontend": {
                    "name": "frontend",
                    "description": "Frontend team (federated)",
                    "config_source": {
                        "github": {
                            "owner": "acme",
                            "repo": "frontend-config",
                        }
                    },
                    "trust": {
                        "inherit_org_marketplaces": True,
                        "allow_additional_marketplaces": True,
                    },
                },
            },
        }

    @pytest.fixture
    def sample_teams_with_federated(self) -> list[dict]:
        """Sample list of teams including federated team."""
        return [
            {"name": "backend", "description": "Backend team (inline)", "plugin": None},
            {"name": "frontend", "description": "Frontend team (federated)", "plugin": None},
        ]

    def test_switch_to_inline_team_does_not_fetch(
        self,
        cli_runner: CliRunner,
        sample_teams_with_federated: list[dict],
        user_config_with_team: dict,
        org_config_with_federated_team: dict,
    ) -> None:
        """Switching to inline team should NOT trigger fetch_team_config."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=org_config_with_federated_team,
            ):
                with patch(
                    "scc_cli.cli_team.teams.list_teams", return_value=sample_teams_with_federated
                ):
                    with patch("scc_cli.cli_team.config.save_user_config"):
                        with patch("scc_cli.cli_team.fetch_team_config") as mock_fetch:
                            result = cli_runner.invoke(team_app, ["switch", "backend"])

        assert result.exit_code == 0
        # Inline team should NOT trigger fetch
        mock_fetch.assert_not_called()

    def test_switch_to_federated_team_fetches_config(
        self,
        cli_runner: CliRunner,
        sample_teams_with_federated: list[dict],
        user_config_with_team: dict,
        org_config_with_federated_team: dict,
    ) -> None:
        """Switching to federated team should fetch team config to prime cache."""
        from scc_cli.cli_team import team_app
        from scc_cli.marketplace.team_fetch import TeamFetchResult

        mock_result = TeamFetchResult(
            success=True,
            source_type="github",
            source_url="github.com/acme/frontend-config",
            team_config={"enabled_plugins": ["react-tools@official"]},
            commit_sha="abc123",
        )

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=org_config_with_federated_team,
            ):
                with patch(
                    "scc_cli.cli_team.teams.list_teams", return_value=sample_teams_with_federated
                ):
                    with patch("scc_cli.cli_team.config.save_user_config"):
                        with patch(
                            "scc_cli.cli_team.fetch_team_config", return_value=mock_result
                        ) as mock_fetch:
                            result = cli_runner.invoke(team_app, ["switch", "frontend"])

        assert result.exit_code == 0
        assert "frontend" in result.stdout.lower()
        # Federated team should trigger fetch
        mock_fetch.assert_called_once()

    def test_switch_to_federated_team_shows_federation_status(
        self,
        cli_runner: CliRunner,
        sample_teams_with_federated: list[dict],
        user_config_with_team: dict,
        org_config_with_federated_team: dict,
    ) -> None:
        """Switching to federated team should display federation info."""
        from scc_cli.cli_team import team_app
        from scc_cli.marketplace.team_fetch import TeamFetchResult

        mock_result = TeamFetchResult(
            success=True,
            source_type="github",
            source_url="github.com/acme/frontend-config",
            team_config={"enabled_plugins": ["react-tools@official"]},
            commit_sha="abc123",
        )

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=org_config_with_federated_team,
            ):
                with patch(
                    "scc_cli.cli_team.teams.list_teams", return_value=sample_teams_with_federated
                ):
                    with patch("scc_cli.cli_team.config.save_user_config"):
                        with patch("scc_cli.cli_team.fetch_team_config", return_value=mock_result):
                            result = cli_runner.invoke(team_app, ["switch", "frontend"])

        assert result.exit_code == 0
        output_lower = result.stdout.lower()
        # Should show federated status
        assert "federated" in output_lower or "github" in output_lower

    def test_switch_to_federated_team_fetch_failure_warns_but_succeeds(
        self,
        cli_runner: CliRunner,
        sample_teams_with_federated: list[dict],
        user_config_with_team: dict,
        org_config_with_federated_team: dict,
    ) -> None:
        """Fetch failure should warn but not block team switch."""
        from scc_cli.cli_team import team_app
        from scc_cli.marketplace.team_fetch import TeamFetchResult

        mock_result = TeamFetchResult(
            success=False,
            source_type="github",
            source_url="github.com/acme/frontend-config",
            error="Network error: Connection refused",
        )

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=org_config_with_federated_team,
            ):
                with patch(
                    "scc_cli.cli_team.teams.list_teams", return_value=sample_teams_with_federated
                ):
                    with patch("scc_cli.cli_team.config.save_user_config") as mock_save:
                        with patch("scc_cli.cli_team.fetch_team_config", return_value=mock_result):
                            result = cli_runner.invoke(team_app, ["switch", "frontend"])

        # Switch should succeed despite fetch failure
        assert result.exit_code == 0
        mock_save.assert_called_once()
        # But should show warning
        output_lower = result.stdout.lower()
        assert "warning" in output_lower or "failed" in output_lower or "error" in output_lower

    def test_switch_to_federated_team_json_includes_federation_info(
        self,
        cli_runner: CliRunner,
        sample_teams_with_federated: list[dict],
        user_config_with_team: dict,
        org_config_with_federated_team: dict,
    ) -> None:
        """JSON output should include federation metadata."""
        from scc_cli.cli_team import team_app
        from scc_cli.marketplace.team_fetch import TeamFetchResult

        mock_result = TeamFetchResult(
            success=True,
            source_type="github",
            source_url="github.com/acme/frontend-config",
            team_config={"enabled_plugins": ["react-tools@official"]},
            commit_sha="abc123",
        )

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=org_config_with_federated_team,
            ):
                with patch(
                    "scc_cli.cli_team.teams.list_teams", return_value=sample_teams_with_federated
                ):
                    with patch("scc_cli.cli_team.config.save_user_config"):
                        with patch("scc_cli.cli_team.fetch_team_config", return_value=mock_result):
                            result = cli_runner.invoke(team_app, ["switch", "frontend", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["data"]["success"] is True
        # Should include federation info
        assert data["data"].get("is_federated") is True
        assert "config_source" in data["data"] or "source_type" in data["data"]


class TestTeamInfoFederated:
    """Tests for scc team info with federated team configurations."""

    @pytest.fixture
    def org_config_with_federated_team(self) -> dict:
        """Org config with a federated team (has config_source)."""
        return {
            "name": "acme-corp",
            "schema_version": "1.0.0",
            "organization": {"name": "acme-corp", "id": "acme-corp"},
            "profiles": {
                "backend": {
                    "name": "backend",
                    "description": "Backend team (inline)",
                    # No config_source = inline team
                },
                "frontend": {
                    "name": "frontend",
                    "description": "Frontend team (federated)",
                    "config_source": {"github": {"owner": "acme", "repo": "frontend-config"}},
                    "trust": {
                        "inherit_org_marketplaces": True,
                        "allow_additional_marketplaces": True,
                    },
                },
            },
        }

    @pytest.fixture
    def user_config_with_team(self) -> dict:
        """User config with a team selected."""
        return {
            "organization_source": {"url": "https://example.com/org.json"},
            "selected_profile": "frontend",
        }

    def test_info_inline_team_shows_inline_mode(
        self,
        cli_runner: CliRunner,
        user_config_with_team: dict,
        org_config_with_federated_team: dict,
    ) -> None:
        """Team info for inline team should show 'inline' mode."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=org_config_with_federated_team,
            ):
                with patch(
                    "scc_cli.cli_team.teams.get_team_details",
                    return_value={"name": "backend", "description": "Backend team (inline)"},
                ):
                    with patch(
                        "scc_cli.cli_team.teams.validate_team_profile",
                        return_value={"valid": True, "warnings": [], "errors": []},
                    ):
                        result = cli_runner.invoke(team_app, ["info", "backend"])

        assert result.exit_code == 0
        # Inline teams should show "inline" in output
        assert "inline" in result.stdout.lower() or "mode" in result.stdout.lower()

    def test_info_federated_team_shows_federated_mode(
        self,
        cli_runner: CliRunner,
        user_config_with_team: dict,
        org_config_with_federated_team: dict,
    ) -> None:
        """Team info for federated team should show 'federated' mode."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=org_config_with_federated_team,
            ):
                with patch(
                    "scc_cli.cli_team.teams.get_team_details",
                    return_value={"name": "frontend", "description": "Frontend team (federated)"},
                ):
                    with patch(
                        "scc_cli.cli_team.teams.validate_team_profile",
                        return_value={"valid": True, "warnings": [], "errors": []},
                    ):
                        result = cli_runner.invoke(team_app, ["info", "frontend"])

        assert result.exit_code == 0
        # Federated teams should show "federated" in output
        assert "federated" in result.stdout.lower()

    def test_info_federated_team_shows_config_source(
        self,
        cli_runner: CliRunner,
        user_config_with_team: dict,
        org_config_with_federated_team: dict,
    ) -> None:
        """Team info for federated team should show config source URL."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=org_config_with_federated_team,
            ):
                with patch(
                    "scc_cli.cli_team.teams.get_team_details",
                    return_value={"name": "frontend", "description": "Frontend team (federated)"},
                ):
                    with patch(
                        "scc_cli.cli_team.teams.validate_team_profile",
                        return_value={"valid": True, "warnings": [], "errors": []},
                    ):
                        result = cli_runner.invoke(team_app, ["info", "frontend"])

        assert result.exit_code == 0
        # Should show the GitHub source info
        assert "github" in result.stdout.lower() or "acme" in result.stdout.lower()

    def test_info_federated_team_shows_trust_grants(
        self,
        cli_runner: CliRunner,
        user_config_with_team: dict,
        org_config_with_federated_team: dict,
    ) -> None:
        """Team info for federated team should show trust grants."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=org_config_with_federated_team,
            ):
                with patch(
                    "scc_cli.cli_team.teams.get_team_details",
                    return_value={"name": "frontend", "description": "Frontend team (federated)"},
                ):
                    with patch(
                        "scc_cli.cli_team.teams.validate_team_profile",
                        return_value={"valid": True, "warnings": [], "errors": []},
                    ):
                        result = cli_runner.invoke(team_app, ["info", "frontend"])

        assert result.exit_code == 0
        # Should show trust grant information
        assert "trust" in result.stdout.lower() or "marketplace" in result.stdout.lower()

    def test_info_federated_team_json_includes_federation_metadata(
        self,
        cli_runner: CliRunner,
        user_config_with_team: dict,
        org_config_with_federated_team: dict,
    ) -> None:
        """JSON output for federated team should include federation metadata."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=org_config_with_federated_team,
            ):
                with patch(
                    "scc_cli.cli_team.teams.get_team_details",
                    return_value={"name": "frontend", "description": "Frontend team (federated)"},
                ):
                    with patch(
                        "scc_cli.cli_team.teams.validate_team_profile",
                        return_value={"valid": True, "warnings": [], "errors": []},
                    ):
                        result = cli_runner.invoke(team_app, ["info", "frontend", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["data"]["found"] is True
        # Should include federation info
        assert "federation" in data["data"] or "is_federated" in data["data"]

    def test_info_inline_team_json_shows_inline(
        self,
        cli_runner: CliRunner,
        user_config_with_team: dict,
        org_config_with_federated_team: dict,
    ) -> None:
        """JSON output for inline team should show inline status."""
        from scc_cli.cli_team import team_app

        with patch("scc_cli.cli_team.config.load_user_config", return_value=user_config_with_team):
            with patch(
                "scc_cli.cli_team.config.load_cached_org_config",
                return_value=org_config_with_federated_team,
            ):
                with patch(
                    "scc_cli.cli_team.teams.get_team_details",
                    return_value={"name": "backend", "description": "Backend team (inline)"},
                ):
                    with patch(
                        "scc_cli.cli_team.teams.validate_team_profile",
                        return_value={"valid": True, "warnings": [], "errors": []},
                    ):
                        result = cli_runner.invoke(team_app, ["info", "backend", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["data"]["found"] is True
        # Should show inline status
        if "is_federated" in data["data"]:
            assert data["data"]["is_federated"] is False
        if "federation" in data["data"]:
            assert data["data"]["federation"]["is_federated"] is False
