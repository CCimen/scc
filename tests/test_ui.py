"""Tests for UI module - validation logic only, NOT Rich rendering."""

from unittest.mock import MagicMock, patch

import pytest

from scc_cli import ui

# ═══════════════════════════════════════════════════════════════════════════════
# Tests for select_team
# ═══════════════════════════════════════════════════════════════════════════════


class TestSelectTeam:
    """Tests for select_team function validation logic."""

    def test_select_team_returns_selected_team(self):
        """select_team should return the team name selected by user."""
        console = MagicMock()
        cfg = {
            "profiles": {
                "team-a": {"description": "Team A"},
                "team-b": {"description": "Team B"},
            }
        }

        with patch("scc_cli.ui.IntPrompt.ask", return_value=2):
            result = ui.select_team(console, cfg)

        assert result == "team-b"

    def test_select_team_first_option_default(self):
        """select_team should handle first option selection."""
        console = MagicMock()
        cfg = {
            "profiles": {
                "default": {"description": "Default team"},
            }
        }

        with patch("scc_cli.ui.IntPrompt.ask", return_value=1):
            result = ui.select_team(console, cfg)

        assert result == "default"

    def test_select_team_empty_profiles_raises(self):
        """select_team should handle empty profiles dict."""
        console = MagicMock()
        cfg = {"profiles": {}}

        # With empty profiles, accessing team_list[choice - 1] will fail
        with patch("scc_cli.ui.IntPrompt.ask", return_value=1):
            with pytest.raises(IndexError):
                ui.select_team(console, cfg)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for select_workspace_source
# ═══════════════════════════════════════════════════════════════════════════════


class TestSelectWorkspaceSource:
    """Tests for select_workspace_source function validation logic."""

    def test_select_workspace_source_cancel_returns_cancel(self):
        """select_workspace_source should return 'cancel' when user selects 0."""
        console = MagicMock()
        cfg = {"profiles": {"team1": {}}}

        with patch("scc_cli.ui.IntPrompt.ask", return_value=0):
            result = ui.select_workspace_source(console, cfg, "team1")

        assert result == "cancel"

    def test_select_workspace_source_recent_option(self):
        """select_workspace_source should return 'recent' for first option."""
        console = MagicMock()
        cfg = {"profiles": {"team1": {}}}

        with patch("scc_cli.ui.IntPrompt.ask", return_value=1):
            result = ui.select_workspace_source(console, cfg, "team1")

        assert result == "recent"

    def test_select_workspace_source_custom_option(self):
        """select_workspace_source should return 'custom' for second option."""
        console = MagicMock()
        cfg = {"profiles": {"team1": {}}}

        with patch("scc_cli.ui.IntPrompt.ask", return_value=2):
            result = ui.select_workspace_source(console, cfg, "team1")

        assert result == "custom"

    def test_select_workspace_source_clone_option(self):
        """select_workspace_source should return 'clone' for third option."""
        console = MagicMock()
        cfg = {"profiles": {"team1": {}}}

        with patch("scc_cli.ui.IntPrompt.ask", return_value=3):
            result = ui.select_workspace_source(console, cfg, "team1")

        assert result == "clone"

    def test_select_workspace_source_team_repos_option_when_available(self):
        """select_workspace_source should show team_repos when team has repositories."""
        console = MagicMock()
        cfg = {
            "profiles": {
                "team1": {"repositories": [{"name": "repo1"}]}
            }
        }

        # With team_repos option inserted, selection 2 = team_repos
        with patch("scc_cli.ui.IntPrompt.ask", return_value=2):
            result = ui.select_workspace_source(console, cfg, "team1")

        assert result == "team_repos"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for select_recent_workspace
# ═══════════════════════════════════════════════════════════════════════════════


class TestSelectRecentWorkspace:
    """Tests for select_recent_workspace function validation logic."""

    def test_select_recent_workspace_empty_shows_prompt(self):
        """select_recent_workspace should fall back to custom prompt when no recents."""
        console = MagicMock()
        cfg = {}

        with (
            patch("scc_cli.sessions.list_recent", return_value=[]),
            patch("scc_cli.ui.prompt_custom_workspace", return_value="/custom/path") as mock_prompt,
        ):
            result = ui.select_recent_workspace(console, cfg)

        mock_prompt.assert_called_once_with(console)
        assert result == "/custom/path"

    def test_select_recent_workspace_back_returns_none(self):
        """select_recent_workspace should return None when user selects back."""
        console = MagicMock()
        cfg = {}
        recent = [{"workspace": "/path/to/project", "last_used": "2024-01-01"}]

        with (
            patch("scc_cli.sessions.list_recent", return_value=recent),
            patch("scc_cli.ui.IntPrompt.ask", return_value=0),
        ):
            result = ui.select_recent_workspace(console, cfg)

        assert result is None

    def test_select_recent_workspace_selects_from_list(self):
        """select_recent_workspace should return selected workspace."""
        console = MagicMock()
        cfg = {}
        recent = [
            {"workspace": "/path/one", "last_used": "2024-01-01"},
            {"workspace": "/path/two", "last_used": "2024-01-02"},
        ]

        with (
            patch("scc_cli.sessions.list_recent", return_value=recent),
            patch("scc_cli.ui.IntPrompt.ask", return_value=2),
        ):
            result = ui.select_recent_workspace(console, cfg)

        assert result == "/path/two"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for prompt_custom_workspace
# ═══════════════════════════════════════════════════════════════════════════════


class TestPromptCustomWorkspace:
    """Tests for prompt_custom_workspace function validation logic."""

    def test_prompt_custom_workspace_empty_returns_none(self):
        """prompt_custom_workspace should return None for empty input."""
        console = MagicMock()

        with patch("scc_cli.ui.Prompt.ask", return_value=""):
            result = ui.prompt_custom_workspace(console)

        assert result is None

    def test_prompt_custom_workspace_existing_path_returns_resolved(self, tmp_path):
        """prompt_custom_workspace should return resolved path for existing directory."""
        console = MagicMock()
        test_dir = tmp_path / "existing_project"
        test_dir.mkdir()

        with patch("scc_cli.ui.Prompt.ask", return_value=str(test_dir)):
            result = ui.prompt_custom_workspace(console)

        assert result == str(test_dir.resolve())

    def test_prompt_custom_workspace_nonexistent_no_create_returns_none(self, tmp_path):
        """prompt_custom_workspace should return None if user declines to create."""
        console = MagicMock()
        nonexistent = tmp_path / "does_not_exist"

        with (
            patch("scc_cli.ui.Prompt.ask", return_value=str(nonexistent)),
            patch("scc_cli.ui.Confirm.ask", return_value=False),
        ):
            result = ui.prompt_custom_workspace(console)

        assert result is None
        assert not nonexistent.exists()

    def test_prompt_custom_workspace_nonexistent_create_returns_path(self, tmp_path):
        """prompt_custom_workspace should create directory if user confirms."""
        console = MagicMock()
        new_dir = tmp_path / "new_project"

        with (
            patch("scc_cli.ui.Prompt.ask", return_value=str(new_dir)),
            patch("scc_cli.ui.Confirm.ask", return_value=True),
        ):
            result = ui.prompt_custom_workspace(console)

        assert result == str(new_dir.resolve())
        assert new_dir.exists()

    def test_prompt_custom_workspace_expands_tilde(self, tmp_path, monkeypatch):
        """prompt_custom_workspace should expand ~ to home directory."""
        console = MagicMock()

        # Create actual directory to test path resolution
        test_dir = tmp_path / "home_project"
        test_dir.mkdir()

        with patch("scc_cli.ui.Prompt.ask", return_value=str(test_dir)):
            result = ui.prompt_custom_workspace(console)

        assert result == str(test_dir.resolve())


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for select_team_repo
# ═══════════════════════════════════════════════════════════════════════════════


class TestSelectTeamRepo:
    """Tests for select_team_repo function validation logic."""

    def test_select_team_repo_empty_falls_back_to_custom(self):
        """select_team_repo should fall back to custom prompt when no repos."""
        console = MagicMock()
        cfg = {"profiles": {"team1": {"repositories": []}}}

        with patch("scc_cli.ui.prompt_custom_workspace", return_value="/custom") as mock_prompt:
            result = ui.select_team_repo(console, cfg, "team1")

        mock_prompt.assert_called_once_with(console)
        assert result == "/custom"

    def test_select_team_repo_no_repos_key_falls_back(self):
        """select_team_repo should fall back when no repositories key."""
        console = MagicMock()
        cfg = {"profiles": {"team1": {}}}

        with patch("scc_cli.ui.prompt_custom_workspace", return_value=None) as mock_prompt:
            result = ui.select_team_repo(console, cfg, "team1")

        mock_prompt.assert_called_once()
        assert result is None

    def test_select_team_repo_back_returns_none(self):
        """select_team_repo should return None when user selects back."""
        console = MagicMock()
        cfg = {
            "profiles": {
                "team1": {
                    "repositories": [
                        {"name": "repo1", "url": "https://github.com/org/repo1"}
                    ]
                }
            }
        }

        with patch("scc_cli.ui.IntPrompt.ask", return_value=0):
            result = ui.select_team_repo(console, cfg, "team1")

        assert result is None

    def test_select_team_repo_local_path_exists_returns_path(self, tmp_path):
        """select_team_repo should return local_path if it exists."""
        console = MagicMock()
        local_dir = tmp_path / "local_repo"
        local_dir.mkdir()

        cfg = {
            "profiles": {
                "team1": {
                    "repositories": [
                        {"name": "repo1", "local_path": str(local_dir)}
                    ]
                }
            }
        }

        with patch("scc_cli.ui.IntPrompt.ask", return_value=1):
            result = ui.select_team_repo(console, cfg, "team1")

        assert result == str(local_dir)

    def test_select_team_repo_needs_clone_calls_git(self, tmp_path):
        """select_team_repo should call git.clone_repo when local_path doesn't exist."""
        console = MagicMock()
        cfg = {
            "profiles": {
                "team1": {
                    "repositories": [
                        {"name": "repo1", "url": "https://github.com/org/repo1"}
                    ]
                }
            },
            "workspace_base": str(tmp_path),
        }

        with (
            patch("scc_cli.ui.IntPrompt.ask", return_value=1),
            patch("scc_cli.git.clone_repo", return_value="/cloned/path") as mock_clone,
        ):
            result = ui.select_team_repo(console, cfg, "team1")

        mock_clone.assert_called_once_with("https://github.com/org/repo1", str(tmp_path))
        assert result == "/cloned/path"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for select_session
# ═══════════════════════════════════════════════════════════════════════════════


class TestSelectSession:
    """Tests for select_session function validation logic."""

    def test_select_session_empty_list_returns_none(self):
        """select_session should return None for empty sessions list."""
        console = MagicMock()

        result = ui.select_session(console, [])

        assert result is None

    def test_select_session_cancel_returns_none(self):
        """select_session should return None when user selects cancel."""
        console = MagicMock()
        sessions = [{"name": "session1", "workspace": "/path", "last_used": "2024-01-01"}]

        with patch("scc_cli.ui.IntPrompt.ask", return_value=0):
            result = ui.select_session(console, sessions)

        assert result is None

    def test_select_session_returns_selected_session(self):
        """select_session should return the selected session dict."""
        console = MagicMock()
        sessions = [
            {"name": "session1", "workspace": "/path1", "last_used": "2024-01-01"},
            {"name": "session2", "workspace": "/path2", "last_used": "2024-01-02"},
        ]

        with patch("scc_cli.ui.IntPrompt.ask", return_value=2):
            result = ui.select_session(console, sessions)

        assert result == sessions[1]
        assert result["name"] == "session2"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for show_worktree_options
# ═══════════════════════════════════════════════════════════════════════════════


class TestShowWorktreeOptions:
    """Tests for show_worktree_options function validation logic."""

    def test_show_worktree_options_create(self, tmp_path):
        """show_worktree_options should return 'create' for first option."""
        console = MagicMock()

        with patch("scc_cli.ui.IntPrompt.ask", return_value=1):
            result = ui.show_worktree_options(console, tmp_path)

        assert result == "create"

    def test_show_worktree_options_list(self, tmp_path):
        """show_worktree_options should return 'list' for second option."""
        console = MagicMock()

        with patch("scc_cli.ui.IntPrompt.ask", return_value=2):
            result = ui.show_worktree_options(console, tmp_path)

        assert result == "list"

    def test_show_worktree_options_switch(self, tmp_path):
        """show_worktree_options should return 'switch' for third option."""
        console = MagicMock()

        with patch("scc_cli.ui.IntPrompt.ask", return_value=3):
            result = ui.show_worktree_options(console, tmp_path)

        assert result == "switch"

    def test_show_worktree_options_cleanup(self, tmp_path):
        """show_worktree_options should return 'cleanup' for fourth option."""
        console = MagicMock()

        with patch("scc_cli.ui.IntPrompt.ask", return_value=4):
            result = ui.show_worktree_options(console, tmp_path)

        assert result == "cleanup"

    def test_show_worktree_options_back(self, tmp_path):
        """show_worktree_options should return 'back' for fifth option."""
        console = MagicMock()

        with patch("scc_cli.ui.IntPrompt.ask", return_value=5):
            result = ui.show_worktree_options(console, tmp_path)

        assert result == "back"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for prompt_repo_url
# ═══════════════════════════════════════════════════════════════════════════════


class TestPromptRepoUrl:
    """Tests for prompt_repo_url function."""

    def test_prompt_repo_url_returns_user_input(self):
        """prompt_repo_url should return the URL entered by user."""
        console = MagicMock()

        with patch("scc_cli.ui.Prompt.ask", return_value="https://github.com/org/repo"):
            result = ui.prompt_repo_url(console)

        assert result == "https://github.com/org/repo"

    def test_prompt_repo_url_empty_returns_empty(self):
        """prompt_repo_url should return empty string if user enters nothing."""
        console = MagicMock()

        with patch("scc_cli.ui.Prompt.ask", return_value=""):
            result = ui.prompt_repo_url(console)

        assert result == ""

    def test_prompt_repo_url_ssh_format(self):
        """prompt_repo_url should accept SSH format URLs."""
        console = MagicMock()

        with patch("scc_cli.ui.Prompt.ask", return_value="git@github.com:org/repo.git"):
            result = ui.prompt_repo_url(console)

        assert result == "git@github.com:org/repo.git"
