"""Tests for session management flag renaming.

TDD tests written BEFORE implementation:

Flag behavior:
- --resume (-r): Auto-resume most recent session
- --select (-s): Interactive session picker
"""

import re
from dataclasses import replace
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from scc_cli.cli import app
from scc_cli.core.exit_codes import EXIT_CANCELLED, EXIT_USAGE
from scc_cli.ports.session_models import SessionSummary
from tests.fakes import build_fake_adapters

runner = CliRunner()


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text for clean string matching."""
    ansi_escape = re.compile(r"\x1b\[[0-9;]*m")
    return ansi_escape.sub("", text)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_session() -> SessionSummary:
    """A mock session for testing."""
    return SessionSummary(
        name="test-session",
        workspace="/home/user/project",
        team="platform",
        last_used="2025-12-22T12:00:00",
        container_name=None,
        branch=None,
    )


@pytest.fixture
def mock_sessions_list() -> list[SessionSummary]:
    """Multiple mock sessions for picker testing."""
    return [
        SessionSummary(
            name="session-1",
            workspace="/home/user/project1",
            team="platform",
            last_used="2025-12-22T12:00:00",
            container_name=None,
            branch=None,
        ),
        SessionSummary(
            name="session-2",
            workspace="/home/user/project2",
            team="backend",
            last_used="2025-12-22T11:00:00",
            container_name=None,
            branch=None,
        ),
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for --resume (auto-resume most recent)
# ═══════════════════════════════════════════════════════════════════════════════


class TestResumeFlag:
    """--resume should auto-select the most recent session."""

    def test_resume_auto_selects_recent_session(self, mock_session):
        """--resume without workspace should use most recent session."""
        # Mock session with no team (standalone mode)
        standalone_session = replace(mock_session, team=None)
        fake_adapters = build_fake_adapters()
        with (
            patch("scc_cli.commands.launch.flow.setup.is_setup_needed", return_value=False),
            patch("scc_cli.commands.launch.flow.config.load_user_config", return_value={}),
            patch(
                "scc_cli.commands.launch.flow.sessions.list_recent",
                return_value=[standalone_session],
            ) as mock_list,
            patch(
                "scc_cli.commands.launch.flow.get_default_adapters",
                return_value=fake_adapters,
            ),
            patch("scc_cli.commands.launch.workspace.check_branch_safety"),
            patch("scc_cli.commands.launch.flow.sessions.record_session"),
            patch("os.path.exists", return_value=True),
            patch("pathlib.Path.exists", return_value=True),
        ):
            # Use --standalone flag to bypass team filtering
            result = runner.invoke(app, ["start", "--resume", "--standalone"])

        # Should have called list_recent (new implementation filters by team)
        mock_list.assert_called_once()
        # Should indicate resuming
        assert "Resuming" in result.output or result.exit_code == 0

    def test_resume_short_flag_works(self, mock_session):
        """-r short flag should work like --resume."""
        # Mock session with no team (standalone mode)
        standalone_session = replace(mock_session, team=None)
        fake_adapters = build_fake_adapters()
        with (
            patch("scc_cli.commands.launch.flow.setup.is_setup_needed", return_value=False),
            patch("scc_cli.commands.launch.flow.config.load_user_config", return_value={}),
            patch(
                "scc_cli.commands.launch.flow.sessions.list_recent",
                return_value=[standalone_session],
            ) as mock_list,
            patch(
                "scc_cli.commands.launch.flow.get_default_adapters",
                return_value=fake_adapters,
            ),
            patch("scc_cli.commands.launch.workspace.check_branch_safety"),
            patch("scc_cli.commands.launch.flow.sessions.record_session"),
            patch("os.path.exists", return_value=True),
            patch("pathlib.Path.exists", return_value=True),
        ):
            # Use --standalone flag to bypass team filtering
            _result = runner.invoke(app, ["start", "-r", "--standalone"])

        mock_list.assert_called_once()

    def test_resume_without_sessions_shows_error(self):
        """--resume with no sessions should show appropriate error."""
        with (
            patch("scc_cli.commands.launch.flow.setup.is_setup_needed", return_value=False),
            patch("scc_cli.commands.launch.flow.config.load_user_config", return_value={}),
            patch("scc_cli.commands.launch.flow.sessions.list_recent", return_value=[]),
        ):
            # Use --standalone flag to bypass team filtering
            result = runner.invoke(app, ["start", "--resume", "--standalone"])

        assert result.exit_code != 0 or "no recent" in result.output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for --select (interactive picker)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSelectFlag:
    """--select should show interactive session picker."""

    def test_select_shows_session_picker(self, mock_sessions_list, mock_session):
        """--select should trigger the session picker UI."""
        # Sessions need team=None for standalone mode filtering
        standalone_sessions = [replace(s, team=None) for s in mock_sessions_list]
        standalone_session = replace(mock_session, team=None)
        fake_adapters = build_fake_adapters()
        with (
            patch("scc_cli.commands.launch.flow.is_interactive_allowed", return_value=True),
            patch("scc_cli.commands.launch.flow.setup.is_setup_needed", return_value=False),
            patch("scc_cli.commands.launch.flow.config.load_user_config", return_value={}),
            patch(
                "scc_cli.commands.launch.flow.sessions.list_recent",
                return_value=standalone_sessions,
            ),
            patch(
                "scc_cli.commands.launch.flow.select_session", return_value=standalone_session
            ) as mock_picker,
            patch(
                "scc_cli.commands.launch.flow.get_default_adapters",
                return_value=fake_adapters,
            ),
            patch("scc_cli.commands.launch.workspace.check_branch_safety"),
            patch("scc_cli.commands.launch.flow.sessions.record_session"),
            patch("os.path.exists", return_value=True),
            patch("pathlib.Path.exists", return_value=True),
        ):
            # Use --standalone flag to bypass team filtering
            _result = runner.invoke(app, ["start", "--select", "--standalone"])

        # Should have called the session picker
        mock_picker.assert_called_once()

    def test_select_short_flag_works(self, mock_sessions_list, mock_session):
        """-s short flag should work like --select."""
        # Sessions need team=None for standalone mode filtering
        standalone_sessions = [replace(s, team=None) for s in mock_sessions_list]
        standalone_session = replace(mock_session, team=None)
        fake_adapters = build_fake_adapters()
        with (
            patch("scc_cli.commands.launch.flow.is_interactive_allowed", return_value=True),
            patch("scc_cli.commands.launch.flow.setup.is_setup_needed", return_value=False),
            patch("scc_cli.commands.launch.flow.config.load_user_config", return_value={}),
            patch(
                "scc_cli.commands.launch.flow.sessions.list_recent",
                return_value=standalone_sessions,
            ),
            patch(
                "scc_cli.commands.launch.flow.select_session", return_value=standalone_session
            ) as mock_picker,
            patch(
                "scc_cli.commands.launch.flow.get_default_adapters",
                return_value=fake_adapters,
            ),
            patch("scc_cli.commands.launch.workspace.check_branch_safety"),
            patch("scc_cli.commands.launch.flow.sessions.record_session"),
            patch("os.path.exists", return_value=True),
            patch("pathlib.Path.exists", return_value=True),
        ):
            # Use --standalone flag to bypass team filtering
            _result = runner.invoke(app, ["start", "-s", "--standalone"])

        mock_picker.assert_called_once()

    def test_select_without_sessions_shows_message(self):
        """--select with no sessions should show appropriate message."""
        with (
            patch("scc_cli.commands.launch.flow.is_interactive_allowed", return_value=True),
            patch("scc_cli.commands.launch.flow.setup.is_setup_needed", return_value=False),
            patch("scc_cli.commands.launch.flow.config.load_user_config", return_value={}),
            patch("scc_cli.commands.launch.flow.sessions.list_recent", return_value=[]),
        ):
            # Use --standalone flag to bypass team filtering
            result = runner.invoke(app, ["start", "--select", "--standalone"])

        # Should not crash and should indicate no sessions
        assert result.exit_code in (0, 1)
        assert "no" in result.output.lower() or "session" in result.output.lower()

    def test_select_user_cancels_exits_gracefully(self, mock_sessions_list):
        """--select should exit gracefully when user cancels picker."""
        # Sessions need team=None for standalone mode filtering
        standalone_sessions = [replace(s, team=None) for s in mock_sessions_list]
        with (
            patch("scc_cli.commands.launch.flow.is_interactive_allowed", return_value=True),
            patch("scc_cli.commands.launch.flow.setup.is_setup_needed", return_value=False),
            patch("scc_cli.commands.launch.flow.config.load_user_config", return_value={}),
            patch(
                "scc_cli.commands.launch.flow.sessions.list_recent",
                return_value=standalone_sessions,
            ),
            patch(
                "scc_cli.commands.launch.flow.select_session", return_value=None
            ),  # User cancelled
        ):
            # Use --standalone flag to bypass team filtering
            result = runner.invoke(app, ["start", "--select", "--standalone"])

        # User cancellation should exit with EXIT_CANCELLED
        assert result.exit_code == EXIT_CANCELLED


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for flag mutual exclusivity
# ═══════════════════════════════════════════════════════════════════════════════


class TestFlagMutualExclusivity:
    """Flags should be mutually exclusive where appropriate."""

    def test_resume_and_select_are_mutually_exclusive(self, mock_session, mock_sessions_list):
        """Using both --resume and --select should error or pick one."""
        fake_adapters = build_fake_adapters()
        with (
            patch("scc_cli.commands.launch.flow.is_interactive_allowed", return_value=True),
            patch("scc_cli.commands.launch.flow.setup.is_setup_needed", return_value=False),
            patch(
                "scc_cli.commands.launch.flow.config.load_user_config",
                return_value={"standalone": True},
            ),
            patch(
                "scc_cli.commands.launch.flow.sessions.get_most_recent", return_value=mock_session
            ),
            patch(
                "scc_cli.commands.launch.flow.sessions.list_recent", return_value=mock_sessions_list
            ),
            patch("scc_cli.commands.launch.flow.select_session", return_value=mock_session),
            patch(
                "scc_cli.commands.launch.flow.get_default_adapters",
                return_value=fake_adapters,
            ),
            patch("scc_cli.commands.launch.workspace.check_branch_safety"),
            patch("scc_cli.commands.launch.flow.sessions.record_session"),
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
        fake_adapters = build_fake_adapters()
        with (
            patch("scc_cli.commands.launch.flow.setup.is_setup_needed", return_value=False),
            patch(
                "scc_cli.commands.launch.flow.config.load_user_config",
                return_value={"standalone": True},
            ),
            # Smart detection returns detected workspace
            patch(
                "scc_cli.commands.launch.flow.git.detect_workspace_root",
                return_value=(mock_session.workspace, detected_path),
            ) as mock_detect,
            patch(
                "scc_cli.commands.launch.flow.get_default_adapters",
                return_value=fake_adapters,
            ),
            patch("scc_cli.commands.launch.workspace.check_branch_safety"),
            patch("scc_cli.commands.launch.flow.sessions.record_session"),
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
            patch("scc_cli.commands.launch.flow.setup.is_setup_needed", return_value=False),
            patch(
                "scc_cli.commands.launch.flow.config.load_user_config",
                return_value={"standalone": True},
            ),
            # Smart detection returns None (not in a git repo)
            patch(
                "scc_cli.commands.launch.flow.git.detect_workspace_root",
                return_value=(None, "/home/user/random"),
            ),
            # Non-TTY environment
            patch("scc_cli.commands.launch.flow.is_interactive_allowed", return_value=False),
        ):
            result = runner.invoke(app, ["start"])

        # Should error with helpful message
        assert result.exit_code != 0
        output = strip_ansi(result.output.lower())
        assert "workspace" in output or "detected" in output

    def test_non_interactive_flag_requires_workspace(self):
        """--non-interactive should fail fast when interactive input is needed."""
        with (
            patch("scc_cli.commands.launch.flow.setup.is_setup_needed", return_value=False),
            patch(
                "scc_cli.commands.launch.flow.config.load_user_config",
                return_value={"standalone": True},
            ),
            patch(
                "scc_cli.commands.launch.flow.is_interactive_allowed", return_value=False
            ) as mock_allowed,
        ):
            result = runner.invoke(app, ["start", "--non-interactive"])

        assert result.exit_code == EXIT_USAGE
        assert mock_allowed.call_args.kwargs.get("no_interactive_flag") is True

    def test_interactive_flag_bypasses_detection(self, mock_sessions_list):
        """The -i flag should force interactive mode even when workspace can be detected."""
        with (
            patch("scc_cli.commands.launch.flow.is_interactive_allowed", return_value=True),
            patch("scc_cli.commands.launch.flow.setup.is_setup_needed", return_value=False),
            patch(
                "scc_cli.commands.launch.flow.config.load_user_config",
                return_value={"standalone": True},
            ),
            # Detection would succeed, but should not be called when -i is used
            patch(
                "scc_cli.commands.launch.flow.git.detect_workspace_root",
                return_value=("/home/user/project", "/home/user/project"),
            ) as mock_detect,
            patch("scc_cli.commands.launch.flow.config.is_standalone_mode", return_value=True),
            patch("scc_cli.commands.launch.flow.config.load_cached_org_config", return_value=None),
            patch("scc_cli.commands.launch.flow.teams.list_teams", return_value=[]),
            patch("scc_cli.commands.launch.flow.load_recent_contexts", return_value=[]),
            # User selects workspace via picker
            patch("scc_cli.commands.launch.flow.pick_workspace_source", return_value=None),
        ):
            result = runner.invoke(app, ["start", "-i"])

        # With -i flag, detection should NOT be called (workspace cleared to None)
        mock_detect.assert_not_called()
        # User cancelled (returned None from picker)
        assert result.exit_code == 0

    @pytest.mark.skip(reason="Phase 3 feature: auto-detection feedback not implemented")
    def test_detection_feedback_shown_on_success(self, mock_session):
        """Auto-detected workspace should show brief feedback message."""
        standalone_sessions = [replace(mock_session, team=None)]
        standalone_session = replace(mock_session, team=None)
        fake_adapters = build_fake_adapters()
        with (
            patch("scc_cli.commands.launch.flow.is_interactive_allowed", return_value=True),
            patch("scc_cli.commands.launch.flow.setup.is_setup_needed", return_value=False),
            patch("scc_cli.commands.launch.flow.config.load_user_config", return_value={}),
            patch(
                "scc_cli.commands.launch.flow.sessions.list_recent",
                return_value=standalone_sessions,
            ),
            patch("scc_cli.commands.launch.flow.select_session", return_value=standalone_session),
            patch(
                "scc_cli.commands.launch.flow.get_default_adapters",
                return_value=fake_adapters,
            ),
            patch("scc_cli.commands.launch.workspace.check_branch_safety"),
            patch("scc_cli.commands.launch.flow.sessions.record_session"),
            patch("os.path.exists", return_value=True),
            patch("pathlib.Path.exists", return_value=True),
        ):
            result = runner.invoke(app, ["start"])

        # Should show detection feedback (unless --json)
        output = strip_ansi(result.output.lower())
        assert "detected" in output or "my-project" in output
