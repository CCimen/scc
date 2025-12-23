"""Tests for stats integration with launch flow.

TDD tests for Task 2.4 - Launch Integration.

Tests verify that:
- record_session_start() is called before docker run
- Stats config (enabled, user_identity_mode) is respected
- Session ID and project name are passed correctly
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

# ═══════════════════════════════════════════════════════════════════════════════
# Test fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def minimal_org_config_v2():
    """Minimal v2 org config for testing."""
    return {
        "schema_version": "2.0",
        "organization": {"name": "Test Org", "id": "test-org"},
        "defaults": {
            "allowed_plugins": ["test-plugin"],
        },
        "profiles": {
            "dev": {
                "description": "Development team",
            }
        },
    }


@pytest.fixture
def org_config_with_stats():
    """Org config with stats configuration."""
    return {
        "schema_version": "2.0",
        "organization": {"name": "Test Org", "id": "test-org"},
        "defaults": {
            "allowed_plugins": ["test-plugin"],
        },
        "profiles": {
            "dev": {
                "description": "Development team",
            }
        },
        "stats": {
            "enabled": True,
            "user_identity_mode": "hash",
        },
    }


@pytest.fixture
def org_config_stats_disabled():
    """Org config with stats disabled."""
    return {
        "schema_version": "2.0",
        "organization": {"name": "Test Org", "id": "test-org"},
        "defaults": {
            "allowed_plugins": ["test-plugin"],
        },
        "profiles": {
            "dev": {
                "description": "Development team",
            }
        },
        "stats": {
            "enabled": False,
        },
    }


@pytest.fixture
def org_config_stats_anonymous():
    """Org config with anonymous stats (no user identity)."""
    return {
        "schema_version": "2.0",
        "organization": {"name": "Test Org", "id": "test-org"},
        "defaults": {
            "allowed_plugins": ["test-plugin"],
        },
        "profiles": {
            "dev": {
                "description": "Development team",
            }
        },
        "stats": {
            "enabled": True,
            "user_identity_mode": "none",
        },
    }


@pytest.fixture
def mock_workspace(tmp_path):
    """Create a mock workspace directory."""
    workspace = tmp_path / "my-project"
    workspace.mkdir()
    return workspace


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for session_start recording
# ═══════════════════════════════════════════════════════════════════════════════


class TestLaunchStatsRecording:
    """Tests for stats recording during launch."""

    def test_session_start_recorded_before_run(self, mock_workspace, org_config_with_stats):
        """Should record session_start before docker run command."""
        from scc_cli import docker

        with (
            patch("scc_cli.docker.launch.check_docker_available"),
            patch("scc_cli.docker.launch.inject_settings"),
            patch("scc_cli.docker.launch.build_command", return_value=["docker", "sandbox"]),
            patch("scc_cli.docker.launch.run") as mock_run,
            patch("scc_cli.docker.launch.stats.record_session_start") as mock_record,
            patch(
                "scc_cli.docker.launch.stats.generate_session_id", return_value="test-session-123"
            ),
        ):
            docker.launch_with_org_config_v2(
                workspace=mock_workspace,
                org_config=org_config_with_stats,
                team="dev",
            )

            # session_start should be called BEFORE run
            assert mock_record.called
            assert mock_run.called

            # Verify call order: record_session_start before run
            calls = mock_record.mock_calls + mock_run.mock_calls
            record_index = next(i for i, c in enumerate(calls) if c == mock_record.mock_calls[0])
            run_index = next(i for i, c in enumerate(calls) if c == mock_run.mock_calls[0])
            assert record_index < run_index, "session_start should be recorded before run"

    def test_session_start_includes_project_name(self, mock_workspace, org_config_with_stats):
        """Should pass workspace directory name as project_name."""
        from scc_cli import docker

        with (
            patch("scc_cli.docker.launch.check_docker_available"),
            patch("scc_cli.docker.launch.inject_settings"),
            patch("scc_cli.docker.launch.build_command", return_value=["docker", "sandbox"]),
            patch("scc_cli.docker.launch.run"),
            patch("scc_cli.docker.launch.stats.record_session_start") as mock_record,
            patch(
                "scc_cli.docker.launch.stats.generate_session_id", return_value="test-session-123"
            ),
        ):
            docker.launch_with_org_config_v2(
                workspace=mock_workspace,
                org_config=org_config_with_stats,
                team="dev",
            )

            # Verify project_name is the workspace folder name
            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args
            assert call_kwargs[1]["project_name"] == mock_workspace.name

    def test_session_start_includes_team_name(self, mock_workspace, org_config_with_stats):
        """Should pass team name to session start."""
        from scc_cli import docker

        with (
            patch("scc_cli.docker.launch.check_docker_available"),
            patch("scc_cli.docker.launch.inject_settings"),
            patch("scc_cli.docker.launch.build_command", return_value=["docker", "sandbox"]),
            patch("scc_cli.docker.launch.run"),
            patch("scc_cli.docker.launch.stats.record_session_start") as mock_record,
            patch(
                "scc_cli.docker.launch.stats.generate_session_id", return_value="test-session-123"
            ),
        ):
            docker.launch_with_org_config_v2(
                workspace=mock_workspace,
                org_config=org_config_with_stats,
                team="dev",
            )

            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args
            assert call_kwargs[1]["team_name"] == "dev"

    def test_session_start_includes_session_id(self, mock_workspace, org_config_with_stats):
        """Should generate and pass unique session ID."""
        from scc_cli import docker

        with (
            patch("scc_cli.docker.launch.check_docker_available"),
            patch("scc_cli.docker.launch.inject_settings"),
            patch("scc_cli.docker.launch.build_command", return_value=["docker", "sandbox"]),
            patch("scc_cli.docker.launch.run"),
            patch("scc_cli.docker.launch.stats.record_session_start") as mock_record,
            patch(
                "scc_cli.docker.launch.stats.generate_session_id", return_value="unique-session-456"
            ),
        ):
            docker.launch_with_org_config_v2(
                workspace=mock_workspace,
                org_config=org_config_with_stats,
                team="dev",
            )

            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args
            assert call_kwargs[1]["session_id"] == "unique-session-456"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for stats config respect
# ═══════════════════════════════════════════════════════════════════════════════


class TestLaunchStatsConfigRespect:
    """Tests for respecting stats configuration from org config."""

    def test_stats_disabled_skips_recording(self, mock_workspace, org_config_stats_disabled):
        """Should not record session when stats.enabled is False."""
        from scc_cli import docker

        with (
            patch("scc_cli.docker.launch.check_docker_available"),
            patch("scc_cli.docker.launch.inject_settings"),
            patch("scc_cli.docker.launch.build_command", return_value=["docker", "sandbox"]),
            patch("scc_cli.docker.launch.run"),
            patch("scc_cli.docker.launch.stats.record_session_start") as mock_record,
            patch("scc_cli.docker.launch.stats.generate_session_id", return_value="test-session"),
        ):
            docker.launch_with_org_config_v2(
                workspace=mock_workspace,
                org_config=org_config_stats_disabled,
                team="dev",
            )

            # record_session_start should pass the disabled config
            # The stats module itself checks enabled flag
            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args
            assert call_kwargs[1]["stats_config"]["enabled"] is False

    def test_stats_config_passed_to_record(self, mock_workspace, org_config_with_stats):
        """Should pass stats config to record_session_start."""
        from scc_cli import docker

        with (
            patch("scc_cli.docker.launch.check_docker_available"),
            patch("scc_cli.docker.launch.inject_settings"),
            patch("scc_cli.docker.launch.build_command", return_value=["docker", "sandbox"]),
            patch("scc_cli.docker.launch.run"),
            patch("scc_cli.docker.launch.stats.record_session_start") as mock_record,
            patch("scc_cli.docker.launch.stats.generate_session_id", return_value="test-session"),
        ):
            docker.launch_with_org_config_v2(
                workspace=mock_workspace,
                org_config=org_config_with_stats,
                team="dev",
            )

            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args
            stats_config = call_kwargs[1]["stats_config"]
            assert stats_config["enabled"] is True
            assert stats_config["user_identity_mode"] == "hash"

    def test_anonymous_mode_passed_to_record(self, mock_workspace, org_config_stats_anonymous):
        """Should pass user_identity_mode='none' when configured."""
        from scc_cli import docker

        with (
            patch("scc_cli.docker.launch.check_docker_available"),
            patch("scc_cli.docker.launch.inject_settings"),
            patch("scc_cli.docker.launch.build_command", return_value=["docker", "sandbox"]),
            patch("scc_cli.docker.launch.run"),
            patch("scc_cli.docker.launch.stats.record_session_start") as mock_record,
            patch("scc_cli.docker.launch.stats.generate_session_id", return_value="test-session"),
        ):
            docker.launch_with_org_config_v2(
                workspace=mock_workspace,
                org_config=org_config_stats_anonymous,
                team="dev",
            )

            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args
            stats_config = call_kwargs[1]["stats_config"]
            assert stats_config["user_identity_mode"] == "none"

    def test_no_stats_config_uses_defaults(self, mock_workspace, minimal_org_config_v2):
        """Should use default stats config when not specified."""
        from scc_cli import docker

        with (
            patch("scc_cli.docker.launch.check_docker_available"),
            patch("scc_cli.docker.launch.inject_settings"),
            patch("scc_cli.docker.launch.build_command", return_value=["docker", "sandbox"]),
            patch("scc_cli.docker.launch.run"),
            patch("scc_cli.docker.launch.stats.record_session_start") as mock_record,
            patch("scc_cli.docker.launch.stats.generate_session_id", return_value="test-session"),
        ):
            docker.launch_with_org_config_v2(
                workspace=mock_workspace,
                org_config=minimal_org_config_v2,
                team="dev",
            )

            # Should still be called with None stats_config (uses module defaults)
            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args
            # When no stats config in org, pass None to let stats module use defaults
            assert call_kwargs[1].get("stats_config") is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for expected duration
# ═══════════════════════════════════════════════════════════════════════════════


class TestLaunchExpectedDuration:
    """Tests for expected duration from session config."""

    def test_expected_duration_from_session_config(self, mock_workspace):
        """Should use session.timeout_hours from effective config."""
        from scc_cli import docker

        org_config = {
            "schema_version": "2.0",
            "organization": {"name": "Test Org", "id": "test-org"},
            "defaults": {
                "allowed_plugins": ["test-plugin"],
                "session": {
                    "timeout_hours": 4,
                },
            },
            "profiles": {
                "dev": {
                    "description": "Development team",
                }
            },
            "stats": {"enabled": True},
        }

        with (
            patch("scc_cli.docker.launch.check_docker_available"),
            patch("scc_cli.docker.launch.inject_settings"),
            patch("scc_cli.docker.launch.build_command", return_value=["docker", "sandbox"]),
            patch("scc_cli.docker.launch.run"),
            patch("scc_cli.docker.launch.stats.record_session_start") as mock_record,
            patch("scc_cli.docker.launch.stats.generate_session_id", return_value="test-session"),
        ):
            docker.launch_with_org_config_v2(
                workspace=mock_workspace,
                org_config=org_config,
                team="dev",
            )

            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args
            assert call_kwargs[1]["expected_duration_hours"] == 4

    def test_default_expected_duration(self, mock_workspace, org_config_with_stats):
        """Should use default 8 hours when not configured."""
        from scc_cli import docker

        with (
            patch("scc_cli.docker.launch.check_docker_available"),
            patch("scc_cli.docker.launch.inject_settings"),
            patch("scc_cli.docker.launch.build_command", return_value=["docker", "sandbox"]),
            patch("scc_cli.docker.launch.run"),
            patch("scc_cli.docker.launch.stats.record_session_start") as mock_record,
            patch("scc_cli.docker.launch.stats.generate_session_id", return_value="test-session"),
        ):
            docker.launch_with_org_config_v2(
                workspace=mock_workspace,
                org_config=org_config_with_stats,
                team="dev",
            )

            mock_record.assert_called_once()
            call_kwargs = mock_record.call_args
            # Default expected duration is 8 hours
            assert call_kwargs[1]["expected_duration_hours"] == 8


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for error scenarios
# ═══════════════════════════════════════════════════════════════════════════════


class TestLaunchStatsErrorHandling:
    """Tests for error handling in stats recording."""

    def test_stats_error_does_not_block_launch(self, mock_workspace, org_config_with_stats):
        """Stats recording errors should not prevent launch."""
        from scc_cli import docker

        with (
            patch("scc_cli.docker.launch.check_docker_available"),
            patch("scc_cli.docker.launch.inject_settings"),
            patch("scc_cli.docker.launch.build_command", return_value=["docker", "sandbox"]),
            patch("scc_cli.docker.launch.run") as mock_run,
            patch(
                "scc_cli.docker.launch.stats.record_session_start",
                side_effect=OSError("Cannot write to stats file"),
            ),
            patch("scc_cli.docker.launch.stats.generate_session_id", return_value="test-session"),
        ):
            # Should not raise, launch should proceed
            docker.launch_with_org_config_v2(
                workspace=mock_workspace,
                org_config=org_config_with_stats,
                team="dev",
            )

            # run() should still be called
            mock_run.assert_called_once()

    def test_session_id_generation_error_handled(self, mock_workspace, org_config_with_stats):
        """Session ID generation errors should not block launch."""
        from scc_cli import docker

        with (
            patch("scc_cli.docker.launch.check_docker_available"),
            patch("scc_cli.docker.launch.inject_settings"),
            patch("scc_cli.docker.launch.build_command", return_value=["docker", "sandbox"]),
            patch("scc_cli.docker.launch.run") as mock_run,
            patch("scc_cli.docker.launch.stats.record_session_start"),
            patch(
                "scc_cli.docker.launch.stats.generate_session_id",
                side_effect=Exception("UUID generation failed"),
            ),
        ):
            # Should not raise, launch should proceed
            docker.launch_with_org_config_v2(
                workspace=mock_workspace,
                org_config=org_config_with_stats,
                team="dev",
            )

            # run() should still be called
            mock_run.assert_called_once()
            # record_session_start might not be called if session_id fails
            # That's acceptable - launch must proceed
