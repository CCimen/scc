"""Tests for new CLI command options.

These tests verify the new architecture requirements:
- setup command: --org-url, --auth, --standalone for non-interactive mode
- config command: set <key> <value> functionality
- start command: --install-deps, --offline, --standalone options
- worktree command: --install-deps option
- sessions command: interactive picker

Additional tests per plan:
- Error handling and exit codes
- Doctor command health checks
- Start requires setup first
"""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from scc_cli.cli import app
from scc_cli.errors import (
    DockerNotFoundError,
    DockerVersionError,
    SandboxNotAvailableError,
)
from scc_cli.exit_codes import EXIT_USAGE

runner = CliRunner()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for setup command options
# ═══════════════════════════════════════════════════════════════════════════════


class TestSetupCommand:
    """Tests for setup command with new options."""

    def test_setup_with_org_url_and_team_runs_non_interactive(self):
        """Should run non-interactive setup when --org-url provided."""
        with patch("scc_cli.cli_config.setup.run_non_interactive_setup") as mock_setup:
            mock_setup.return_value = True
            result = runner.invoke(
                app,
                [
                    "setup",
                    "--org-url",
                    "https://example.org/config.json",
                    "--team",
                    "platform",
                ],
            )
        assert result.exit_code == 0
        mock_setup.assert_called_once()

    def test_setup_with_standalone_flag(self):
        """Should run standalone setup with --standalone flag."""
        with patch("scc_cli.cli_config.setup.run_non_interactive_setup") as mock_setup:
            mock_setup.return_value = True
            result = runner.invoke(app, ["setup", "--standalone"])
        assert result.exit_code == 0
        # Should call with standalone=True
        call_kwargs = mock_setup.call_args
        assert call_kwargs[1].get("standalone") is True or (
            len(call_kwargs[0]) >= 2 and call_kwargs[0][1] is True  # Positional
        )

    def test_setup_with_auth_option(self):
        """Should pass auth to non-interactive setup."""
        with patch("scc_cli.cli_config.setup.run_non_interactive_setup") as mock_setup:
            mock_setup.return_value = True
            result = runner.invoke(
                app,
                [
                    "setup",
                    "--org-url",
                    "https://example.org/config.json",
                    "--auth",
                    "env:GITLAB_TOKEN",
                ],
            )
        assert result.exit_code == 0

    def test_setup_non_interactive_requires_inputs(self):
        """--non-interactive should fail when org or standalone not provided."""
        result = runner.invoke(app, ["setup", "--non-interactive"])

        assert result.exit_code == EXIT_USAGE


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for config command options
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigCommand:
    """Tests for config command with set functionality."""

    def test_config_set_updates_value(self):
        """Should update config when set <key> <value> provided."""
        with (
            patch("scc_cli.cli_config.config.load_user_config") as mock_load,
            patch("scc_cli.cli_config.config.save_user_config") as mock_save,
        ):
            mock_load.return_value = {"existing": "value"}
            result = runner.invoke(app, ["config", "set", "hooks.enabled", "true"])
        assert result.exit_code == 0
        mock_save.assert_called_once()

    def test_config_get_reads_value(self):
        """Should display value when get <key> provided."""
        with patch("scc_cli.cli_config.config.load_user_config") as mock_load:
            mock_load.return_value = {"selected_profile": "platform"}
            result = runner.invoke(app, ["config", "get", "selected_profile"])
        assert result.exit_code == 0
        assert "platform" in result.output


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for start command options
# ═══════════════════════════════════════════════════════════════════════════════


class TestStartCommand:
    """Tests for start command with new options."""

    def test_start_with_install_deps_runs_dependency_install(self, tmp_path):
        """Should install dependencies when --install-deps flag set."""
        # Create a workspace with package.json
        (tmp_path / "package.json").write_text("{}")

        with (
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={}),
            patch("scc_cli.cli_launch.docker.check_docker_available"),
            patch("scc_cli.cli_launch.git.check_branch_safety"),
            patch("scc_cli.cli_launch.git.get_current_branch", return_value="main"),
            patch(
                "scc_cli.cli_launch.git.get_workspace_mount_path", return_value=(tmp_path, False)
            ),
            patch("scc_cli.cli_launch.docker.prepare_sandbox_volume_for_credentials"),
            patch(
                "scc_cli.cli_launch.docker.get_or_create_container",
                return_value=(["docker"], False),
            ),
            patch("scc_cli.cli_launch.docker.run"),
            patch("scc_cli.cli_launch.deps.auto_install_dependencies") as mock_deps,
        ):
            mock_deps.return_value = True
            runner.invoke(app, ["start", str(tmp_path), "--install-deps"])
        # Should have called auto_install_dependencies
        mock_deps.assert_called_once()

    def test_start_with_offline_uses_cache_only(self, tmp_path):
        """Should use cached config only when --offline flag set."""
        with (
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={}),
            patch("scc_cli.remote.load_org_config") as mock_remote,
            patch("scc_cli.cli_launch.docker.check_docker_available"),
            patch("scc_cli.cli_launch.git.check_branch_safety"),
            patch("scc_cli.cli_launch.git.get_current_branch", return_value="main"),
            patch(
                "scc_cli.cli_launch.git.get_workspace_mount_path", return_value=(tmp_path, False)
            ),
            patch("scc_cli.cli_launch.docker.prepare_sandbox_volume_for_credentials"),
            patch(
                "scc_cli.cli_launch.docker.get_or_create_container",
                return_value=(["docker"], False),
            ),
            patch("scc_cli.cli_launch.docker.run"),
        ):
            mock_remote.return_value = {"organization": {"name": "Test"}}
            runner.invoke(app, ["start", str(tmp_path), "--offline"])
        # Should have passed offline=True to load_org_config
        if mock_remote.called:
            call_kwargs = mock_remote.call_args[1]
            assert call_kwargs.get("offline") is True

    def test_start_with_standalone_skips_org_config(self, tmp_path):
        """Should skip org config when --standalone flag set."""
        with (
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={}),
            patch("scc_cli.cli_launch.docker.check_docker_available"),
            patch("scc_cli.cli_launch.git.check_branch_safety"),
            patch("scc_cli.cli_launch.git.get_current_branch", return_value="main"),
            patch(
                "scc_cli.cli_launch.git.get_workspace_mount_path", return_value=(tmp_path, False)
            ),
            patch("scc_cli.cli_launch.docker.prepare_sandbox_volume_for_credentials"),
            patch(
                "scc_cli.cli_launch.docker.get_or_create_container",
                return_value=(["docker"], False),
            ),
            patch("scc_cli.cli_launch.docker.run"),
            patch("scc_cli.remote.load_org_config") as mock_remote,
        ):
            runner.invoke(app, ["start", str(tmp_path), "--standalone"])
        # Should NOT have called load_org_config
        mock_remote.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for worktree command options
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorktreeCommand:
    """Tests for worktree command with new options."""

    def test_worktree_with_install_deps_installs_after_create(self, tmp_path):
        """Should install dependencies after worktree creation."""
        worktree_path = tmp_path / "worktree"
        worktree_path.mkdir()

        with (
            patch("scc_cli.cli_worktree.git.is_git_repo", return_value=True),
            patch("scc_cli.cli_worktree.git.create_worktree", return_value=worktree_path),
            patch("scc_cli.cli_worktree.deps.auto_install_dependencies") as mock_deps,
            patch("rich.prompt.Confirm.ask", return_value=False),  # Don't start claude
        ):
            mock_deps.return_value = True
            runner.invoke(
                app,
                ["worktree", "create", str(tmp_path), "feature-x", "--install-deps", "--no-start"],
            )
        mock_deps.assert_called_once_with(worktree_path)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for sessions command
# ═══════════════════════════════════════════════════════════════════════════════


class TestSessionsCommand:
    """Tests for sessions command with interactive picker."""

    def test_sessions_shows_recent_sessions(self):
        """Should list recent sessions."""
        mock_sessions = [
            {
                "name": "session1",
                "workspace": "/tmp/proj1",
                "last_used": "2025-01-01",
                "team": "dev",
            },
        ]
        with patch("scc_cli.cli_worktree.sessions.list_recent", return_value=mock_sessions):
            result = runner.invoke(app, ["sessions"])
        assert result.exit_code == 0
        assert "session1" in result.output

    def test_sessions_interactive_picker_when_select_flag(self):
        """Should show interactive picker with --select flag."""
        mock_sessions = [
            {"name": "session1", "workspace": "/tmp/proj1"},
            {"name": "session2", "workspace": "/tmp/proj2"},
        ]
        with (
            patch("scc_cli.cli_worktree.sessions.list_recent", return_value=mock_sessions),
            patch("scc_cli.cli_worktree.pick_session") as mock_select,
        ):
            mock_select.return_value = mock_sessions[0]
            runner.invoke(app, ["sessions", "--select"])
        # Should have called pick_session for interactive picker
        mock_select.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for start command error handling
# ═══════════════════════════════════════════════════════════════════════════════


class TestStartCommandErrors:
    """Tests for start command error handling and exit codes."""

    def test_start_requires_setup_first(self, tmp_path):
        """Should prompt for setup when not configured."""
        with (
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=True),
            patch("scc_cli.cli_launch.setup.maybe_run_setup", return_value=False),
        ):
            result = runner.invoke(app, ["start", str(tmp_path)])

        # Should exit with code 1 when setup fails/is declined
        assert result.exit_code == 1

    def test_start_shows_docker_not_found_error(self, tmp_path):
        """Should show helpful message when Docker not installed."""
        with (
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={}),
            patch("scc_cli.cli_launch.docker.check_docker_available") as mock_docker,
            patch(
                "scc_cli.cli_launch.git.get_workspace_mount_path", return_value=(tmp_path, False)
            ),
        ):
            mock_docker.side_effect = DockerNotFoundError()
            result = runner.invoke(app, ["start", str(tmp_path)])

        # Should show error message about Docker
        assert "docker" in result.output.lower() or result.exit_code != 0

    def test_start_shows_docker_version_error(self, tmp_path):
        """Should show helpful message when Docker version too old."""
        with (
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={}),
            patch("scc_cli.cli_launch.docker.check_docker_available") as mock_docker,
            patch(
                "scc_cli.cli_launch.git.get_workspace_mount_path", return_value=(tmp_path, False)
            ),
        ):
            mock_docker.side_effect = DockerVersionError(current_version="4.0.0")
            result = runner.invoke(app, ["start", str(tmp_path)])

        # Should indicate version issue
        assert result.exit_code != 0

    def test_start_shows_sandbox_not_available_error(self, tmp_path):
        """Should show helpful message when sandbox not available."""
        with (
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={}),
            patch("scc_cli.cli_launch.docker.check_docker_available") as mock_docker,
            patch(
                "scc_cli.cli_launch.git.get_workspace_mount_path", return_value=(tmp_path, False)
            ),
        ):
            mock_docker.side_effect = SandboxNotAvailableError()
            result = runner.invoke(app, ["start", str(tmp_path)])

        # Should indicate sandbox not available
        assert result.exit_code != 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for doctor command
# ═══════════════════════════════════════════════════════════════════════════════


class TestDoctorCommand:
    """Tests for doctor command health checks."""

    def test_doctor_shows_healthy_status(self):
        """Doctor should show healthy when all checks pass."""
        with (
            patch("scc_cli.cli_admin.doctor.run_doctor") as mock_checks,
            patch("scc_cli.cli_admin.doctor.render_doctor_results"),
        ):
            mock_result = MagicMock()
            mock_result.all_ok = True
            mock_checks.return_value = mock_result
            result = runner.invoke(app, ["doctor"])

        assert result.exit_code == 0

    def test_doctor_shows_fix_suggestions(self):
        """Doctor should show fix suggestions when issues found."""
        with (
            patch("scc_cli.cli_admin.doctor.run_doctor") as mock_checks,
            patch("scc_cli.cli_admin.doctor.render_doctor_results"),
        ):
            mock_result = MagicMock()
            mock_result.all_ok = False
            mock_checks.return_value = mock_result
            result = runner.invoke(app, ["doctor"])

        # Should exit with code 3 when issues found
        assert result.exit_code == 3


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for config command edge cases
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigCommandEdgeCases:
    """Tests for config command edge cases."""

    def test_config_get_missing_key_shows_error(self):
        """Should show helpful error when key doesn't exist."""
        with patch("scc_cli.cli_config.config.load_user_config") as mock_load:
            mock_load.return_value = {}
            result = runner.invoke(app, ["config", "get", "nonexistent.key"])

        # Should indicate key not found
        assert "not found" in result.output.lower() or "none" in result.output.lower()

    def test_config_set_nested_key(self):
        """Should support setting nested keys like hooks.enabled."""
        with (
            patch("scc_cli.cli_config.config.load_user_config") as mock_load,
            patch("scc_cli.cli_config.config.save_user_config") as mock_save,
        ):
            mock_load.return_value = {"hooks": {"enabled": False}}
            result = runner.invoke(app, ["config", "set", "hooks.enabled", "true"])

        assert result.exit_code == 0
        mock_save.assert_called_once()

    def test_config_show_displays_all(self):
        """Config without args should show all config."""
        with patch("scc_cli.cli_config.config.load_user_config") as mock_load:
            mock_load.return_value = {
                "selected_profile": "dev",
                "hooks": {"enabled": True},
            }
            result = runner.invoke(app, ["config"])

        assert result.exit_code == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for update command
# ═══════════════════════════════════════════════════════════════════════════════


class TestUpdateCommand:
    """Tests for update command."""

    def test_update_shows_current_version(self):
        """Update should show current version."""
        mock_result = MagicMock()
        mock_result.cli_update_available = False
        with (
            patch("scc_cli.cli_admin.config.load_config", return_value={}),
            patch("scc_cli.update.check_all_updates", return_value=mock_result),
            patch("scc_cli.update.render_update_status_panel"),
        ):
            result = runner.invoke(app, ["update"])

        assert result.exit_code == 0

    def test_update_check_shows_available_update(self):
        """Update should show when new version available."""
        mock_result = MagicMock()
        mock_result.cli_update_available = True
        with (
            patch("scc_cli.cli_admin.config.load_config", return_value={}),
            patch("scc_cli.update.check_all_updates", return_value=mock_result),
            patch("scc_cli.update.render_update_status_panel"),
        ):
            result = runner.invoke(app, ["update", "--force"])

        assert result.exit_code == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for list command
# ═══════════════════════════════════════════════════════════════════════════════


class TestListCommand:
    """Tests for list command (containers)."""

    def test_list_shows_running_containers(self):
        """List should show running scc containers."""
        mock_container = MagicMock()
        mock_container.name = "scc-project-xyz"
        mock_container.status = "Up 2 hours"
        mock_container.workspace = "/home/user/project"
        mock_container.profile = "dev"
        mock_container.branch = "main"

        with patch(
            "scc_cli.cli_worktree.docker.list_scc_containers", return_value=[mock_container]
        ):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0

    def test_list_shows_empty_message(self):
        """List should show message when no containers."""
        with patch("scc_cli.cli_worktree.docker.list_scc_containers", return_value=[]):
            result = runner.invoke(app, ["list"])

        assert result.exit_code == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for stop command
# ═══════════════════════════════════════════════════════════════════════════════


class TestStopCommand:
    """Tests for stop command."""

    def test_stop_stops_container(self):
        """Stop should stop specified container."""
        mock_container = MagicMock()
        mock_container.name = "scc-project-abc123"
        mock_container.id = "abc123def456"

        with (
            patch(
                "scc_cli.cli_worktree.docker.list_running_sandboxes", return_value=[mock_container]
            ),
            patch("scc_cli.cli_worktree.docker.stop_container", return_value=True) as mock_stop,
        ):
            result = runner.invoke(app, ["stop", "scc-project-abc123"])

        assert result.exit_code == 0
        mock_stop.assert_called_once_with("abc123def456")

    def test_stop_nonexistent_container_shows_error(self):
        """Stop should show error for nonexistent container."""
        # Return some containers but not the one we're looking for
        mock_container = MagicMock()
        mock_container.name = "other-container"
        mock_container.id = "other123"

        with patch(
            "scc_cli.cli_worktree.docker.list_running_sandboxes", return_value=[mock_container]
        ):
            result = runner.invoke(app, ["stop", "nonexistent"])

        # Should indicate container not found
        assert result.exit_code == 1

    def test_stop_all_when_no_containers(self):
        """Stop should show message when no containers running."""
        with patch("scc_cli.cli_worktree.docker.list_running_sandboxes", return_value=[]):
            result = runner.invoke(app, ["stop"])

        # Should indicate no containers running
        assert result.exit_code == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for worktree error handling
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorktreeCommandErrors:
    """Tests for worktree command error handling."""

    def test_worktree_not_git_repo_shows_error(self, tmp_path):
        """Should show error when not in a git repo."""
        with patch("scc_cli.cli_worktree.git.is_git_repo", return_value=False):
            result = runner.invoke(app, ["worktree", "create", str(tmp_path), "feature-x"])

        # Should indicate not a git repo
        assert result.exit_code != 0 or "git" in result.output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for main app callback
# ═══════════════════════════════════════════════════════════════════════════════


class TestMainCallback:
    """Tests for main CLI callback."""

    def test_version_flag_shows_version(self):
        """--version should show version info."""
        result = runner.invoke(app, ["--version"])

        # Should show version without error
        assert result.exit_code == 0 or "version" in result.output.lower()

    def test_help_shows_commands(self):
        """--help should show available commands."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "start" in result.output.lower()
        assert "setup" in result.output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for statusline command
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatuslineCommand:
    """Tests for statusline configuration command."""

    def test_statusline_show_with_configured(self):
        """Should show current statusline configuration."""
        mock_settings = {"statusLine": {"command": "/path/to/script"}}
        with patch("scc_cli.cli_admin.docker.get_sandbox_settings", return_value=mock_settings):
            result = runner.invoke(app, ["statusline", "--show"])

        assert result.exit_code == 0

    def test_statusline_show_not_configured(self):
        """Should indicate when statusline not configured."""
        mock_settings = {"otherSetting": True}
        with patch("scc_cli.cli_admin.docker.get_sandbox_settings", return_value=mock_settings):
            result = runner.invoke(app, ["statusline", "--show"])

        assert result.exit_code == 0

    def test_statusline_show_no_settings(self):
        """Should indicate when no settings exist."""
        with patch("scc_cli.cli_admin.docker.get_sandbox_settings", return_value=None):
            result = runner.invoke(app, ["statusline", "--show"])

        assert result.exit_code == 0

    def test_statusline_uninstall_removes_config(self):
        """Uninstall should remove statusline from settings."""
        mock_settings = {"statusLine": {"command": "/path/to/script"}, "other": True}
        with (
            patch("scc_cli.cli_admin.docker.get_sandbox_settings", return_value=mock_settings),
            patch("scc_cli.cli_admin.docker.inject_file_to_sandbox_volume", return_value=True),
        ):
            result = runner.invoke(app, ["statusline", "--uninstall"])

        assert result.exit_code == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for sessions command additional paths
# ═══════════════════════════════════════════════════════════════════════════════


class TestSessionsCommandDetails:
    """Additional tests for sessions command."""

    def test_sessions_empty_list(self):
        """Should show message when no sessions."""
        with patch("scc_cli.cli_worktree.sessions.list_recent", return_value=[]):
            result = runner.invoke(app, ["sessions"])

        assert result.exit_code == 0

    def test_sessions_with_limit(self):
        """Should respect limit option."""
        mock_sessions = [
            {"name": f"session-{i}", "workspace": f"/path/{i}", "timestamp": "2024-01-01"}
            for i in range(5)
        ]
        with patch(
            "scc_cli.cli_worktree.sessions.list_recent", return_value=mock_sessions
        ) as mock_list:
            result = runner.invoke(app, ["sessions", "-n", "5"])

        assert result.exit_code == 0
        mock_list.assert_called_once_with(5)
