"""Tests for scc org update command (T2a-21).

TDD tests for the org update command which refreshes organization config
and optionally federated team configs from their remote sources.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from scc_cli.cli import app

if TYPE_CHECKING:
    pass

runner = CliRunner()


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def mock_user_config_org_connected():
    """User config with organization source configured."""
    return {
        "standalone": False,
        "organization_source": {
            "url": "https://example.com/org-config.json",
            "auth": None,
        },
        "selected_profile": "developers",
    }


@pytest.fixture
def mock_user_config_standalone():
    """User config in standalone mode."""
    return {
        "standalone": True,
        "organization_source": None,
        "selected_profile": None,
    }


@pytest.fixture
def mock_org_config_inline_teams():
    """Org config with only inline teams (no federated)."""
    return {
        "schema_version": "v1",
        "organization": {
            "name": "Test Org",
            "id": "test-org",
        },
        "profiles": {
            "developers": {
                "name": "Developers",
                "description": "Developer team",
                "additional_plugins": ["code-review@shared"],
            },
            "qa": {
                "name": "QA Team",
                "description": "Quality assurance",
                "additional_plugins": [],
            },
        },
    }


@pytest.fixture
def mock_org_config_federated_teams():
    """Org config with federated teams."""
    return {
        "schema_version": "v1",
        "organization": {
            "name": "Test Org",
            "id": "test-org",
        },
        "profiles": {
            "developers": {
                "name": "Developers",
                "description": "Developer team - inline",
                "additional_plugins": ["code-review@shared"],
            },
            "external-team": {
                "name": "External Team",
                "description": "Federated team",
                "config_source": {
                    "github": {
                        "owner": "example",
                        "repo": "team-configs",
                        "path": "external-team.json",
                    }
                },
                "trust": {
                    "inherit_org_marketplaces": True,
                    "allow_additional_marketplaces": False,
                },
            },
            "partner-team": {
                "name": "Partner Team",
                "description": "Another federated team",
                "config_source": {
                    "url": {
                        "url": "https://partner.example.com/team-config.json",
                    }
                },
                "trust": {
                    "inherit_org_marketplaces": True,
                    "allow_additional_marketplaces": True,
                },
            },
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Test: Basic org update
# ─────────────────────────────────────────────────────────────────────────────


class TestOrgUpdateBasic:
    """Test basic org update command (refreshes org config only)."""

    def test_update_org_config_success(
        self, mock_user_config_org_connected, mock_org_config_inline_teams
    ):
        """org update should refresh org config from remote."""
        with (
            patch("scc_cli.cli_org.load_user_config") as mock_load_user,
            patch("scc_cli.cli_org.load_org_config") as mock_load_org,
        ):
            mock_load_user.return_value = mock_user_config_org_connected
            mock_load_org.return_value = mock_org_config_inline_teams

            result = runner.invoke(app, ["org", "update"])

            assert result.exit_code == 0
            # Should call load_org_config with force_refresh=True
            mock_load_org.assert_called_once()
            call_kwargs = mock_load_org.call_args[1]
            assert call_kwargs.get("force_refresh") is True

    def test_update_standalone_mode_error(self, mock_user_config_standalone):
        """org update should fail in standalone mode."""
        with patch("scc_cli.cli_org.load_user_config") as mock_load_user:
            mock_load_user.return_value = mock_user_config_standalone

            result = runner.invoke(app, ["org", "update"])

            assert result.exit_code != 0
            assert "standalone" in result.stdout.lower() or "organization" in result.stdout.lower()

    def test_update_no_source_configured_error(self):
        """org update should fail when no organization source is configured."""
        with patch("scc_cli.cli_org.load_user_config") as mock_load_user:
            mock_load_user.return_value = {
                "standalone": False,
                "organization_source": None,
            }

            result = runner.invoke(app, ["org", "update"])

            assert result.exit_code != 0

    def test_update_shows_success_message(
        self, mock_user_config_org_connected, mock_org_config_inline_teams
    ):
        """org update should show success message with org details."""
        with (
            patch("scc_cli.cli_org.load_user_config") as mock_load_user,
            patch("scc_cli.cli_org.load_org_config") as mock_load_org,
        ):
            mock_load_user.return_value = mock_user_config_org_connected
            mock_load_org.return_value = mock_org_config_inline_teams

            result = runner.invoke(app, ["org", "update"])

            assert result.exit_code == 0
            # Should mention success or updated
            output_lower = result.stdout.lower()
            assert (
                "update" in output_lower or "refresh" in output_lower or "success" in output_lower
            )


# ─────────────────────────────────────────────────────────────────────────────
# Test: Update with --team option
# ─────────────────────────────────────────────────────────────────────────────


class TestOrgUpdateTeam:
    """Test org update --team <name> for federated teams."""

    def test_update_team_federated_refreshes_team_config(
        self, mock_user_config_org_connected, mock_org_config_federated_teams
    ):
        """org update --team should refresh a federated team's config."""
        with (
            patch("scc_cli.cli_org.load_user_config") as mock_load_user,
            patch("scc_cli.cli_org.load_org_config") as mock_load_org,
            patch("scc_cli.cli_org.fetch_team_config") as mock_fetch_team,
        ):
            mock_load_user.return_value = mock_user_config_org_connected
            mock_load_org.return_value = mock_org_config_federated_teams
            mock_fetch_team.return_value = MagicMock(
                success=True,
                team_config={"enabled_plugins": ["plugin1"]},
            )

            result = runner.invoke(app, ["org", "update", "--team", "external-team"])

            assert result.exit_code == 0
            # Should have fetched team config
            mock_fetch_team.assert_called_once()

    def test_update_team_inline_shows_warning(
        self, mock_user_config_org_connected, mock_org_config_federated_teams
    ):
        """org update --team on inline team should show warning (not federated)."""
        with (
            patch("scc_cli.cli_org.load_user_config") as mock_load_user,
            patch("scc_cli.cli_org.load_org_config") as mock_load_org,
        ):
            mock_load_user.return_value = mock_user_config_org_connected
            mock_load_org.return_value = mock_org_config_federated_teams

            result = runner.invoke(app, ["org", "update", "--team", "developers"])

            # Should succeed but indicate team is inline (not federated)
            output_lower = result.stdout.lower()
            assert "inline" in output_lower or "not federated" in output_lower

    def test_update_team_not_found_error(
        self, mock_user_config_org_connected, mock_org_config_federated_teams
    ):
        """org update --team with unknown team should error."""
        with (
            patch("scc_cli.cli_org.load_user_config") as mock_load_user,
            patch("scc_cli.cli_org.load_org_config") as mock_load_org,
        ):
            mock_load_user.return_value = mock_user_config_org_connected
            mock_load_org.return_value = mock_org_config_federated_teams

            result = runner.invoke(app, ["org", "update", "--team", "nonexistent"])

            assert result.exit_code != 0
            assert "not found" in result.stdout.lower() or "nonexistent" in result.stdout.lower()

    def test_update_team_fetch_failure_shows_error(
        self, mock_user_config_org_connected, mock_org_config_federated_teams
    ):
        """org update --team should show error when team config fetch fails."""
        with (
            patch("scc_cli.cli_org.load_user_config") as mock_load_user,
            patch("scc_cli.cli_org.load_org_config") as mock_load_org,
            patch("scc_cli.cli_org.fetch_team_config") as mock_fetch_team,
        ):
            mock_load_user.return_value = mock_user_config_org_connected
            mock_load_org.return_value = mock_org_config_federated_teams
            mock_fetch_team.return_value = MagicMock(
                success=False,
                error="Network timeout",
            )

            result = runner.invoke(app, ["org", "update", "--team", "external-team"])

            assert result.exit_code != 0
            output_lower = result.stdout.lower()
            assert "fail" in output_lower or "error" in output_lower


# ─────────────────────────────────────────────────────────────────────────────
# Test: Update with --all-teams option
# ─────────────────────────────────────────────────────────────────────────────


class TestOrgUpdateAllTeams:
    """Test org update --all-teams for refreshing all federated teams."""

    def test_update_all_teams_refreshes_all_federated(
        self, mock_user_config_org_connected, mock_org_config_federated_teams
    ):
        """org update --all-teams should refresh all federated team configs."""
        with (
            patch("scc_cli.cli_org.load_user_config") as mock_load_user,
            patch("scc_cli.cli_org.load_org_config") as mock_load_org,
            patch("scc_cli.cli_org.fetch_team_config") as mock_fetch_team,
        ):
            mock_load_user.return_value = mock_user_config_org_connected
            mock_load_org.return_value = mock_org_config_federated_teams
            mock_fetch_team.return_value = MagicMock(
                success=True,
                team_config={"enabled_plugins": []},
            )

            result = runner.invoke(app, ["org", "update", "--all-teams"])

            assert result.exit_code == 0
            # Should have fetched both federated teams (external-team, partner-team)
            # but not inline team (developers)
            assert mock_fetch_team.call_count == 2

    def test_update_all_teams_no_federated_shows_message(
        self, mock_user_config_org_connected, mock_org_config_inline_teams
    ):
        """org update --all-teams with no federated teams should indicate that."""
        with (
            patch("scc_cli.cli_org.load_user_config") as mock_load_user,
            patch("scc_cli.cli_org.load_org_config") as mock_load_org,
        ):
            mock_load_user.return_value = mock_user_config_org_connected
            mock_load_org.return_value = mock_org_config_inline_teams

            result = runner.invoke(app, ["org", "update", "--all-teams"])

            assert result.exit_code == 0
            # Should indicate no federated teams exist
            output_lower = result.stdout.lower()
            assert "no federated" in output_lower or "inline" in output_lower

    def test_update_all_teams_partial_failure_shows_summary(
        self, mock_user_config_org_connected, mock_org_config_federated_teams
    ):
        """org update --all-teams should show summary when some fetches fail."""
        fetch_count = 0

        def mock_fetch(*args, **kwargs):
            nonlocal fetch_count
            fetch_count += 1
            if fetch_count == 1:
                return MagicMock(success=True, team_config={"enabled_plugins": []})
            else:
                return MagicMock(success=False, error="Network error")

        with (
            patch("scc_cli.cli_org.load_user_config") as mock_load_user,
            patch("scc_cli.cli_org.load_org_config") as mock_load_org,
            patch("scc_cli.cli_org.fetch_team_config", side_effect=mock_fetch),
        ):
            mock_load_user.return_value = mock_user_config_org_connected
            mock_load_org.return_value = mock_org_config_federated_teams

            result = runner.invoke(app, ["org", "update", "--all-teams"])

            # Should complete with partial success message
            # Should show count of successes/failures
            assert "1" in result.stdout  # at least show count


# ─────────────────────────────────────────────────────────────────────────────
# Test: JSON output mode
# ─────────────────────────────────────────────────────────────────────────────


class TestOrgUpdateJson:
    """Test org update command JSON output."""

    def test_update_json_output_has_envelope(
        self, mock_user_config_org_connected, mock_org_config_inline_teams
    ):
        """org update --json should return proper JSON envelope."""
        with (
            patch("scc_cli.cli_org.load_user_config") as mock_load_user,
            patch("scc_cli.cli_org.load_org_config") as mock_load_org,
        ):
            mock_load_user.return_value = mock_user_config_org_connected
            mock_load_org.return_value = mock_org_config_inline_teams

            result = runner.invoke(app, ["org", "update", "--json"])

            assert result.exit_code == 0
            data = json.loads(result.stdout)
            # Standard envelope structure
            assert "apiVersion" in data
            assert "kind" in data
            assert "data" in data

    def test_update_json_includes_org_info(
        self, mock_user_config_org_connected, mock_org_config_inline_teams
    ):
        """org update --json should include org info in response."""
        with (
            patch("scc_cli.cli_org.load_user_config") as mock_load_user,
            patch("scc_cli.cli_org.load_org_config") as mock_load_org,
        ):
            mock_load_user.return_value = mock_user_config_org_connected
            mock_load_org.return_value = mock_org_config_inline_teams

            result = runner.invoke(app, ["org", "update", "--json"])

            assert result.exit_code == 0
            data = json.loads(result.stdout)
            # Should have org name in response
            assert "organization" in data["data"] or "org_name" in data["data"]

    def test_update_team_json_includes_team_info(
        self, mock_user_config_org_connected, mock_org_config_federated_teams
    ):
        """org update --team <name> --json should include team update info."""
        with (
            patch("scc_cli.cli_org.load_user_config") as mock_load_user,
            patch("scc_cli.cli_org.load_org_config") as mock_load_org,
            patch("scc_cli.cli_org.fetch_team_config") as mock_fetch_team,
        ):
            mock_load_user.return_value = mock_user_config_org_connected
            mock_load_org.return_value = mock_org_config_federated_teams
            mock_fetch_team.return_value = MagicMock(
                success=True,
                team_config={"enabled_plugins": []},
                commit_sha="abc123",
            )

            result = runner.invoke(app, ["org", "update", "--team", "external-team", "--json"])

            assert result.exit_code == 0
            data = json.loads(result.stdout)
            # Should include team update result
            assert "team" in data["data"] or "teams_updated" in data["data"]

    def test_update_all_teams_json_includes_summary(
        self, mock_user_config_org_connected, mock_org_config_federated_teams
    ):
        """org update --all-teams --json should include summary of all team updates."""
        with (
            patch("scc_cli.cli_org.load_user_config") as mock_load_user,
            patch("scc_cli.cli_org.load_org_config") as mock_load_org,
            patch("scc_cli.cli_org.fetch_team_config") as mock_fetch_team,
        ):
            mock_load_user.return_value = mock_user_config_org_connected
            mock_load_org.return_value = mock_org_config_federated_teams
            mock_fetch_team.return_value = MagicMock(
                success=True,
                team_config={"enabled_plugins": []},
                commit_sha="abc123",
            )

            result = runner.invoke(app, ["org", "update", "--all-teams", "--json"])

            assert result.exit_code == 0
            data = json.loads(result.stdout)
            # Should include list of team results
            assert "teams" in data["data"] or "teams_updated" in data["data"]


# ─────────────────────────────────────────────────────────────────────────────
# Test: Error handling in JSON mode
# ─────────────────────────────────────────────────────────────────────────────


class TestOrgUpdateJsonErrors:
    """Test error handling in JSON output mode."""

    def test_update_standalone_json_error(self, mock_user_config_standalone):
        """org update --json in standalone mode should return JSON error."""
        with patch("scc_cli.cli_org.load_user_config") as mock_load_user:
            mock_load_user.return_value = mock_user_config_standalone

            result = runner.invoke(app, ["org", "update", "--json"])

            assert result.exit_code != 0
            data = json.loads(result.stdout)
            assert data.get("ok") is False or "error" in str(data).lower()

    def test_update_team_not_found_json_error(
        self, mock_user_config_org_connected, mock_org_config_federated_teams
    ):
        """org update --team with unknown team should return JSON error."""
        with (
            patch("scc_cli.cli_org.load_user_config") as mock_load_user,
            patch("scc_cli.cli_org.load_org_config") as mock_load_org,
        ):
            mock_load_user.return_value = mock_user_config_org_connected
            mock_load_org.return_value = mock_org_config_federated_teams

            result = runner.invoke(app, ["org", "update", "--team", "nonexistent", "--json"])

            assert result.exit_code != 0
            envelope = json.loads(result.stdout)
            # ok is in status field of envelope structure
            assert envelope.get("status", {}).get("ok") is False

    def test_update_network_failure_json_error(self, mock_user_config_org_connected):
        """org update --json should return JSON error on network failure."""
        with (
            patch("scc_cli.cli_org.load_user_config") as mock_load_user,
            patch("scc_cli.cli_org.load_org_config") as mock_load_org,
        ):
            mock_load_user.return_value = mock_user_config_org_connected
            mock_load_org.return_value = None  # Simulate fetch failure

            result = runner.invoke(app, ["org", "update", "--json"])

            assert result.exit_code != 0
            envelope = json.loads(result.stdout)
            # ok is in status field of envelope structure
            assert envelope.get("status", {}).get("ok") is False
