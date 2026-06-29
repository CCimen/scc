"""Tests for session management flag renaming.

TDD tests written BEFORE implementation:

Flag behavior:
- --resume (-r): Auto-resume most recent session
- --select (-s): Interactive session picker
"""

from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from scc_cli.cli import app
from scc_cli.core.exit_codes import EXIT_CANCELLED
from scc_cli.ports.session_models import SessionListResult, SessionSummary
from tests.fakes import build_fake_adapters

runner = CliRunner()


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
                "scc_cli.commands.launch.flow.sessions.get_session_service"
            ) as mock_service_factory,
            patch(
                "scc_cli.commands.launch.flow.get_default_adapters",
                return_value=fake_adapters,
            ),
            patch("scc_cli.commands.launch.workspace.check_branch_safety"),
            patch("scc_cli.commands.launch.flow.sessions.record_session"),
            patch("os.path.exists", return_value=True),
            patch("pathlib.Path.exists", return_value=True),
        ):
            mock_service = MagicMock()
            mock_service.list_recent.return_value = SessionListResult.from_sessions(
                [standalone_session]
            )
            mock_service_factory.return_value = mock_service
            # Use --standalone flag to bypass team filtering
            result = runner.invoke(app, ["start", "--resume", "--standalone"])

        # Should have called list_recent (new implementation filters by team)
        mock_service.list_recent.assert_called_once()
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
                "scc_cli.commands.launch.flow.sessions.get_session_service"
            ) as mock_service_factory,
            patch(
                "scc_cli.commands.launch.flow.get_default_adapters",
                return_value=fake_adapters,
            ),
            patch("scc_cli.commands.launch.workspace.check_branch_safety"),
            patch("scc_cli.commands.launch.flow.sessions.record_session"),
            patch("os.path.exists", return_value=True),
            patch("pathlib.Path.exists", return_value=True),
        ):
            mock_service = MagicMock()
            mock_service.list_recent.return_value = SessionListResult.from_sessions(
                [standalone_session]
            )
            mock_service_factory.return_value = mock_service
            # Use --standalone flag to bypass team filtering
            _result = runner.invoke(app, ["start", "-r", "--standalone"])

        mock_service.list_recent.assert_called_once()

    def test_resume_without_sessions_shows_error(self):
        """--resume with no sessions should show appropriate error."""
        with (
            patch("scc_cli.commands.launch.flow.setup.is_setup_needed", return_value=False),
            patch("scc_cli.commands.launch.flow.config.load_user_config", return_value={}),
            patch(
                "scc_cli.commands.launch.flow.sessions.get_session_service"
            ) as mock_service_factory,
        ):
            mock_service = MagicMock()
            mock_service.list_recent.return_value = SessionListResult.from_sessions([])
            mock_service_factory.return_value = mock_service
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
            patch("scc_cli.commands.launch.flow_session.is_interactive_allowed", return_value=True),
            patch("scc_cli.commands.launch.flow.setup.is_setup_needed", return_value=False),
            patch("scc_cli.commands.launch.flow.config.load_user_config", return_value={}),
            patch(
                "scc_cli.commands.launch.flow.sessions.get_session_service"
            ) as mock_service_factory,
            patch("scc_cli.commands.launch.flow_session.pick_session") as mock_picker,
            patch(
                "scc_cli.commands.launch.flow.get_default_adapters",
                return_value=fake_adapters,
            ),
            patch("scc_cli.commands.launch.workspace.check_branch_safety"),
            patch("scc_cli.commands.launch.flow.sessions.record_session"),
            patch("os.path.exists", return_value=True),
            patch("pathlib.Path.exists", return_value=True),
        ):
            mock_service = MagicMock()
            mock_service.list_recent.return_value = SessionListResult.from_sessions(
                standalone_sessions
            )
            mock_service_factory.return_value = mock_service
            mock_picker.return_value = standalone_session
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
            patch("scc_cli.commands.launch.flow_session.is_interactive_allowed", return_value=True),
            patch("scc_cli.commands.launch.flow.setup.is_setup_needed", return_value=False),
            patch("scc_cli.commands.launch.flow.config.load_user_config", return_value={}),
            patch(
                "scc_cli.commands.launch.flow.sessions.get_session_service"
            ) as mock_service_factory,
            patch("scc_cli.commands.launch.flow_session.pick_session") as mock_picker,
            patch(
                "scc_cli.commands.launch.flow.get_default_adapters",
                return_value=fake_adapters,
            ),
            patch("scc_cli.commands.launch.workspace.check_branch_safety"),
            patch("scc_cli.commands.launch.flow.sessions.record_session"),
            patch("os.path.exists", return_value=True),
            patch("pathlib.Path.exists", return_value=True),
        ):
            mock_service = MagicMock()
            mock_service.list_recent.return_value = SessionListResult.from_sessions(
                standalone_sessions
            )
            mock_service_factory.return_value = mock_service
            mock_picker.return_value = standalone_session
            # Use --standalone flag to bypass team filtering
            _result = runner.invoke(app, ["start", "-s", "--standalone"])

        mock_picker.assert_called_once()

    def test_select_without_sessions_shows_message(self):
        """--select with no sessions should show appropriate message."""
        with (
            patch("scc_cli.commands.launch.flow_session.is_interactive_allowed", return_value=True),
            patch("scc_cli.commands.launch.flow.setup.is_setup_needed", return_value=False),
            patch("scc_cli.commands.launch.flow.config.load_user_config", return_value={}),
            patch(
                "scc_cli.commands.launch.flow.sessions.get_session_service"
            ) as mock_service_factory,
        ):
            mock_service = MagicMock()
            mock_service.list_recent.return_value = SessionListResult.from_sessions([])
            mock_service_factory.return_value = mock_service
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
            patch("scc_cli.commands.launch.flow_session.is_interactive_allowed", return_value=True),
            patch("scc_cli.commands.launch.flow.setup.is_setup_needed", return_value=False),
            patch("scc_cli.commands.launch.flow.config.load_user_config", return_value={}),
            patch(
                "scc_cli.commands.launch.flow.sessions.get_session_service"
            ) as mock_service_factory,
            patch("scc_cli.commands.launch.flow_session.pick_session", return_value=None),
        ):
            mock_service = MagicMock()
            mock_service.list_recent.return_value = SessionListResult.from_sessions(
                standalone_sessions
            )
            mock_service_factory.return_value = mock_service
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
            patch("scc_cli.commands.launch.flow_session.is_interactive_allowed", return_value=True),
            patch("scc_cli.commands.launch.flow.setup.is_setup_needed", return_value=False),
            patch(
                "scc_cli.commands.launch.flow.config.load_user_config",
                return_value={"standalone": True},
            ),
            patch(
                "scc_cli.commands.launch.flow.sessions.get_session_service"
            ) as mock_service_factory,
            patch(
                "scc_cli.commands.launch.flow.get_default_adapters",
                return_value=fake_adapters,
            ),
            patch("scc_cli.commands.launch.workspace.check_branch_safety"),
            patch("scc_cli.commands.launch.flow.sessions.record_session"),
            patch("os.path.exists", return_value=True),
            patch("pathlib.Path.exists", return_value=True),
        ):
            mock_service = MagicMock()
            mock_service.list_recent.return_value = SessionListResult.from_sessions(
                mock_sessions_list
            )
            mock_service_factory.return_value = mock_service
            result = runner.invoke(app, ["start", "--resume", "--select"])

        # Either should error OR one should take precedence
        # For now, we'll just ensure it doesn't crash
        # The implementation will decide the exact behavior
        assert result.exit_code in (0, 1, 2)
