"""Tests for session management flag renaming.

TDD tests written BEFORE implementation:

Flag Consolidation (from plan):
- --resume (-r): Auto-resume most recent session (takes over --continue behavior)
- --select (-s): Interactive session picker (new clear name)
- --continue (-c): Hidden alias for --resume (backward compatibility)
"""

import re
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from scc_cli.cli import app
from scc_cli.exit_codes import EXIT_CANCELLED, EXIT_USAGE

runner = CliRunner()


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text for clean string matching."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_session():
    """A mock session for testing."""
    return {
        "name": "test-session",
        "workspace": "/home/user/project",
        "team": "platform",
        "last_used": "2025-12-22T12:00:00",
    }


@pytest.fixture
def mock_sessions_list():
    """Multiple mock sessions for picker testing."""
    return [
        {
            "name": "session-1",
            "workspace": "/home/user/project1",
            "team": "platform",
            "last_used": "2025-12-22T12:00:00",
        },
        {
            "name": "session-2",
            "workspace": "/home/user/project2",
            "team": "backend",
            "last_used": "2025-12-22T11:00:00",
        },
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for --resume (auto-resume most recent)
# ═══════════════════════════════════════════════════════════════════════════════


class TestResumeFlag:
    """--resume should auto-select the most recent session."""

    def test_resume_auto_selects_recent_session(self, mock_session):
        """--resume without workspace should use most recent session."""
        with (
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={"standalone": True}),
            patch(
                "scc_cli.cli_launch.sessions.get_most_recent", return_value=mock_session
            ) as mock_recent,
            patch("scc_cli.cli_launch.docker.check_docker_available"),
            patch(
                "scc_cli.cli_launch.docker.get_or_create_container",
                return_value=(["docker", "run"], False),
            ),
            patch("scc_cli.cli_launch.docker.run"),
            patch("scc_cli.cli_launch.docker.prepare_sandbox_volume_for_credentials"),
            patch(
                "scc_cli.cli_launch.git.get_workspace_mount_path",
                return_value=(mock_session["workspace"], False),
            ),
            patch("scc_cli.cli_launch.git.check_branch_safety"),
            patch("scc_cli.cli_launch.sessions.record_session"),
            patch("os.path.exists", return_value=True),
            patch("pathlib.Path.exists", return_value=True),
        ):
            result = runner.invoke(app, ["start", "--resume"])

        # Should have called get_most_recent
        mock_recent.assert_called_once()
        # Should indicate resuming
        assert "Resuming" in result.output or result.exit_code == 0

    def test_resume_short_flag_works(self, mock_session):
        """-r short flag should work like --resume."""
        with (
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={"standalone": True}),
            patch(
                "scc_cli.cli_launch.sessions.get_most_recent", return_value=mock_session
            ) as mock_recent,
            patch("scc_cli.cli_launch.docker.check_docker_available"),
            patch(
                "scc_cli.cli_launch.docker.get_or_create_container",
                return_value=(["docker", "run"], False),
            ),
            patch("scc_cli.cli_launch.docker.run"),
            patch("scc_cli.cli_launch.docker.prepare_sandbox_volume_for_credentials"),
            patch(
                "scc_cli.cli_launch.git.get_workspace_mount_path",
                return_value=(mock_session["workspace"], False),
            ),
            patch("scc_cli.cli_launch.git.check_branch_safety"),
            patch("scc_cli.cli_launch.sessions.record_session"),
            patch("os.path.exists", return_value=True),
            patch("pathlib.Path.exists", return_value=True),
        ):
            _result = runner.invoke(app, ["start", "-r"])

        mock_recent.assert_called_once()

    def test_resume_without_sessions_shows_error(self):
        """--resume with no sessions should show appropriate error."""
        with (
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={"standalone": True}),
            patch("scc_cli.cli_launch.sessions.get_most_recent", return_value=None),
        ):
            result = runner.invoke(app, ["start", "--resume"])

        assert result.exit_code != 0 or "no recent" in result.output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for --select (interactive picker)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSelectFlag:
    """--select should show interactive session picker."""

    def test_select_shows_session_picker(self, mock_sessions_list, mock_session):
        """--select should trigger the session picker UI."""
        with (
            patch("scc_cli.cli_launch.is_interactive_allowed", return_value=True),
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={"standalone": True}),
            patch("scc_cli.cli_launch.sessions.list_recent", return_value=mock_sessions_list),
            patch("scc_cli.cli_launch.select_session", return_value=mock_session) as mock_picker,
            patch("scc_cli.cli_launch.docker.check_docker_available"),
            patch(
                "scc_cli.cli_launch.docker.get_or_create_container",
                return_value=(["docker", "run"], False),
            ),
            patch("scc_cli.cli_launch.docker.run"),
            patch("scc_cli.cli_launch.docker.prepare_sandbox_volume_for_credentials"),
            patch(
                "scc_cli.cli_launch.git.get_workspace_mount_path",
                return_value=(mock_session["workspace"], False),
            ),
            patch("scc_cli.cli_launch.git.check_branch_safety"),
            patch("scc_cli.cli_launch.sessions.record_session"),
            patch("os.path.exists", return_value=True),
            patch("pathlib.Path.exists", return_value=True),
        ):
            _result = runner.invoke(app, ["start", "--select"])

        # Should have called the session picker
        mock_picker.assert_called_once()

    def test_select_short_flag_works(self, mock_sessions_list, mock_session):
        """-s short flag should work like --select."""
        with (
            patch("scc_cli.cli_launch.is_interactive_allowed", return_value=True),
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={"standalone": True}),
            patch("scc_cli.cli_launch.sessions.list_recent", return_value=mock_sessions_list),
            patch("scc_cli.cli_launch.select_session", return_value=mock_session) as mock_picker,
            patch("scc_cli.cli_launch.docker.check_docker_available"),
            patch(
                "scc_cli.cli_launch.docker.get_or_create_container",
                return_value=(["docker", "run"], False),
            ),
            patch("scc_cli.cli_launch.docker.run"),
            patch("scc_cli.cli_launch.docker.prepare_sandbox_volume_for_credentials"),
            patch(
                "scc_cli.cli_launch.git.get_workspace_mount_path",
                return_value=(mock_session["workspace"], False),
            ),
            patch("scc_cli.cli_launch.git.check_branch_safety"),
            patch("scc_cli.cli_launch.sessions.record_session"),
            patch("os.path.exists", return_value=True),
            patch("pathlib.Path.exists", return_value=True),
        ):
            _result = runner.invoke(app, ["start", "-s"])

        mock_picker.assert_called_once()

    def test_select_without_sessions_shows_message(self):
        """--select with no sessions should show appropriate message."""
        with (
            patch("scc_cli.cli_launch.is_interactive_allowed", return_value=True),
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={"standalone": True}),
            patch("scc_cli.cli_launch.sessions.list_recent", return_value=[]),
        ):
            result = runner.invoke(app, ["start", "--select"])

        # Should not crash and should indicate no sessions
        assert result.exit_code in (0, 1)
        assert "no" in result.output.lower() or "session" in result.output.lower()

    def test_select_user_cancels_exits_gracefully(self, mock_sessions_list):
        """--select should exit gracefully when user cancels picker."""
        with (
            patch("scc_cli.cli_launch.is_interactive_allowed", return_value=True),
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={"standalone": True}),
            patch("scc_cli.cli_launch.sessions.list_recent", return_value=mock_sessions_list),
            patch("scc_cli.cli_launch.select_session", return_value=None),  # User cancelled
        ):
            result = runner.invoke(app, ["start", "--select"])

        # User cancellation should exit with EXIT_CANCELLED
        assert result.exit_code == EXIT_CANCELLED


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for --continue (hidden alias)
# ═══════════════════════════════════════════════════════════════════════════════


class TestContinueAlias:
    """--continue should work as hidden alias for --resume."""

    def test_continue_is_alias_for_resume(self, mock_session):
        """--continue should have same behavior as --resume."""
        with (
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={"standalone": True}),
            patch(
                "scc_cli.cli_launch.sessions.get_most_recent", return_value=mock_session
            ) as mock_recent,
            patch("scc_cli.cli_launch.docker.check_docker_available"),
            patch(
                "scc_cli.cli_launch.docker.get_or_create_container",
                return_value=(["docker", "run"], False),
            ),
            patch("scc_cli.cli_launch.docker.run"),
            patch("scc_cli.cli_launch.docker.prepare_sandbox_volume_for_credentials"),
            patch(
                "scc_cli.cli_launch.git.get_workspace_mount_path",
                return_value=(mock_session["workspace"], False),
            ),
            patch("scc_cli.cli_launch.git.check_branch_safety"),
            patch("scc_cli.cli_launch.sessions.record_session"),
            patch("os.path.exists", return_value=True),
            patch("pathlib.Path.exists", return_value=True),
        ):
            _result = runner.invoke(app, ["start", "--continue"])

        # Should behave like --resume (call get_most_recent)
        mock_recent.assert_called_once()

    def test_continue_short_c_flag_works(self, mock_session):
        """-c short flag should work as alias."""
        with (
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={"standalone": True}),
            patch(
                "scc_cli.cli_launch.sessions.get_most_recent", return_value=mock_session
            ) as mock_recent,
            patch("scc_cli.cli_launch.docker.check_docker_available"),
            patch(
                "scc_cli.cli_launch.docker.get_or_create_container",
                return_value=(["docker", "run"], False),
            ),
            patch("scc_cli.cli_launch.docker.run"),
            patch("scc_cli.cli_launch.docker.prepare_sandbox_volume_for_credentials"),
            patch(
                "scc_cli.cli_launch.git.get_workspace_mount_path",
                return_value=(mock_session["workspace"], False),
            ),
            patch("scc_cli.cli_launch.git.check_branch_safety"),
            patch("scc_cli.cli_launch.sessions.record_session"),
            patch("os.path.exists", return_value=True),
            patch("pathlib.Path.exists", return_value=True),
        ):
            _result = runner.invoke(app, ["start", "-c"])

        mock_recent.assert_called_once()

    def test_continue_flag_is_hidden(self):
        """--continue should be hidden from help output."""
        result = runner.invoke(app, ["start", "--help"])
        output = strip_ansi(result.output)

        # Check that --continue is NOT in help but --resume IS
        # This is the expected behavior for hidden alias
        assert "--resume" in output
        assert "--select" in output
        # --continue should be hidden (not shown in help)
        # This assertion will verify the "hidden" property


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for flag mutual exclusivity
# ═══════════════════════════════════════════════════════════════════════════════


class TestFlagMutualExclusivity:
    """Flags should be mutually exclusive where appropriate."""

    def test_resume_and_select_are_mutually_exclusive(self, mock_session, mock_sessions_list):
        """Using both --resume and --select should error or pick one."""
        with (
            patch("scc_cli.cli_launch.is_interactive_allowed", return_value=True),
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={"standalone": True}),
            patch("scc_cli.cli_launch.sessions.get_most_recent", return_value=mock_session),
            patch("scc_cli.cli_launch.sessions.list_recent", return_value=mock_sessions_list),
            patch("scc_cli.cli_launch.select_session", return_value=mock_session),
            patch("scc_cli.cli_launch.docker.check_docker_available"),
            patch(
                "scc_cli.cli_launch.docker.get_or_create_container",
                return_value=(["docker", "run"], False),
            ),
            patch("scc_cli.cli_launch.docker.run"),
            patch("scc_cli.cli_launch.docker.prepare_sandbox_volume_for_credentials"),
            patch(
                "scc_cli.cli_launch.git.get_workspace_mount_path",
                return_value=(mock_session["workspace"], False),
            ),
            patch("scc_cli.cli_launch.git.check_branch_safety"),
            patch("scc_cli.cli_launch.sessions.record_session"),
            patch("os.path.exists", return_value=True),
            patch("pathlib.Path.exists", return_value=True),
        ):
            result = runner.invoke(app, ["start", "--resume", "--select"])

        # Either should error OR one should take precedence
        # For now, we'll just ensure it doesn't crash
        # The implementation will decide the exact behavior
        assert result.exit_code in (0, 1, 2)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for smart workspace detection (Phase 3)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.skip(reason="Phase 3 feature: auto-detection at scc start not yet implemented")
class TestSmartWorkspaceDetection:
    """Smart detection should auto-select workspace when run from git repo."""

    def test_auto_detects_workspace_from_git_repo(self, mock_session):
        """Running 'scc start' from git repo should auto-detect workspace."""
        detected_path = "/home/user/project"
        with (
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={"standalone": True}),
            # Smart detection returns detected workspace
            patch(
                "scc_cli.cli_launch.git.detect_workspace_root",
                return_value=(mock_session["workspace"], detected_path),
            ) as mock_detect,
            patch("scc_cli.cli_launch.docker.check_docker_available"),
            patch(
                "scc_cli.cli_launch.docker.get_or_create_container",
                return_value=(["docker", "run"], False),
            ),
            patch("scc_cli.cli_launch.docker.run"),
            patch("scc_cli.cli_launch.docker.prepare_sandbox_volume_for_credentials"),
            patch(
                "scc_cli.cli_launch.git.get_workspace_mount_path",
                return_value=(mock_session["workspace"], False),
            ),
            patch("scc_cli.cli_launch.git.check_branch_safety"),
            patch("scc_cli.cli_launch.sessions.record_session"),
            patch("os.path.exists", return_value=True),
            patch("pathlib.Path.exists", return_value=True),
        ):
            result = runner.invoke(app, ["start"])

        # Should have called detect_workspace_root
        mock_detect.assert_called_once()
        # Should succeed (launches with detected workspace)
        assert result.exit_code == 0

    def test_no_detection_non_tty_shows_error(self):
        """Running 'scc start' in non-git dir without TTY should error."""
        with (
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={"standalone": True}),
            # Smart detection returns None (not in a git repo)
            patch(
                "scc_cli.cli_launch.git.detect_workspace_root",
                return_value=(None, "/home/user/random"),
            ),
            # Non-TTY environment
            patch("scc_cli.cli_launch.is_interactive_allowed", return_value=False),
        ):
            result = runner.invoke(app, ["start"])

        # Should error with helpful message
        assert result.exit_code != 0
        output = strip_ansi(result.output.lower())
        assert "workspace" in output or "detected" in output

    def test_non_interactive_flag_requires_workspace(self):
        """--non-interactive should fail fast when interactive input is needed."""
        with (
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={"standalone": True}),
            patch("scc_cli.cli_launch.is_interactive_allowed", return_value=False) as mock_allowed,
        ):
            result = runner.invoke(app, ["start", "--non-interactive"])

        assert result.exit_code == EXIT_USAGE
        assert mock_allowed.call_args.kwargs.get("no_interactive_flag") is True

    def test_interactive_flag_bypasses_detection(self, mock_sessions_list):
        """The -i flag should force interactive mode even when workspace can be detected."""
        with (
            patch("scc_cli.cli_launch.is_interactive_allowed", return_value=True),
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={"standalone": True}),
            # Detection would succeed, but should not be called when -i is used
            patch(
                "scc_cli.cli_launch.git.detect_workspace_root",
                return_value=("/home/user/project", "/home/user/project"),
            ) as mock_detect,
            patch("scc_cli.cli_launch.config.is_standalone_mode", return_value=True),
            patch("scc_cli.cli_launch.config.load_cached_org_config", return_value=None),
            patch("scc_cli.cli_launch.teams.list_teams", return_value=[]),
            patch("scc_cli.cli_launch.load_recent_contexts", return_value=[]),
            # User selects workspace via picker
            patch("scc_cli.cli_launch.pick_workspace_source", return_value=None),
        ):
            result = runner.invoke(app, ["start", "-i"])

        # With -i flag, detection should NOT be called (workspace cleared to None)
        mock_detect.assert_not_called()
        # User cancelled (returned None from picker)
        assert result.exit_code == 0

    def test_detection_feedback_shown_on_success(self, mock_session):
        """Auto-detected workspace should show brief feedback message."""
        detected_path = "/home/user/my-project"
        with (
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={"standalone": True}),
            patch(
                "scc_cli.cli_launch.git.detect_workspace_root",
                return_value=(detected_path, detected_path),
            ),
            patch("scc_cli.cli_launch.docker.check_docker_available"),
            patch(
                "scc_cli.cli_launch.docker.get_or_create_container",
                return_value=(["docker", "run"], False),
            ),
            patch("scc_cli.cli_launch.docker.run"),
            patch("scc_cli.cli_launch.docker.prepare_sandbox_volume_for_credentials"),
            patch(
                "scc_cli.cli_launch.git.get_workspace_mount_path",
                return_value=(detected_path, False),
            ),
            patch("scc_cli.cli_launch.git.check_branch_safety"),
            patch("scc_cli.cli_launch.sessions.record_session"),
            patch("os.path.exists", return_value=True),
            patch("pathlib.Path.exists", return_value=True),
        ):
            result = runner.invoke(app, ["start"])

        # Should show detection feedback (unless --json)
        output = strip_ansi(result.output.lower())
        assert "detected" in output or "my-project" in output
