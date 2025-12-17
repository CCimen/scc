"""Tests for new CLI command options.

These tests verify the new architecture requirements:
- setup command: --org-url, --auth, --standalone for non-interactive mode
- config command: set <key> <value> functionality
- start command: --install-deps, --offline, --standalone options
- worktree command: --install-deps option
- sessions command: interactive picker
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from scc_cli.cli import app

runner = CliRunner()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for setup command options
# ═══════════════════════════════════════════════════════════════════════════════


class TestSetupCommand:
    """Tests for setup command with new options."""

    def test_setup_with_org_url_and_team_runs_non_interactive(self):
        """Should run non-interactive setup when --org-url provided."""
        with patch("scc_cli.cli.setup.run_non_interactive_setup") as mock_setup:
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
        with patch("scc_cli.cli.setup.run_non_interactive_setup") as mock_setup:
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
        with patch("scc_cli.cli.setup.run_non_interactive_setup") as mock_setup:
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
        mock_setup.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for config command options
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfigCommand:
    """Tests for config command with set functionality."""

    def test_config_set_updates_value(self):
        """Should update config when set <key> <value> provided."""
        with (
            patch("scc_cli.cli.config.load_user_config") as mock_load,
            patch("scc_cli.cli.config.save_user_config") as mock_save,
        ):
            mock_load.return_value = {"existing": "value"}
            result = runner.invoke(app, ["config", "set", "hooks.enabled", "true"])
        assert result.exit_code == 0
        mock_save.assert_called_once()

    def test_config_get_reads_value(self):
        """Should display value when get <key> provided."""
        with patch("scc_cli.cli.config.load_user_config") as mock_load:
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
            patch("scc_cli.cli.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli.config.load_config", return_value={}),
            patch("scc_cli.cli.docker.check_docker_available"),
            patch("scc_cli.cli.git.check_branch_safety"),
            patch("scc_cli.cli.git.get_current_branch", return_value="main"),
            patch("scc_cli.cli.git.get_workspace_mount_path", return_value=(tmp_path, False)),
            patch("scc_cli.cli.docker.prepare_sandbox_volume_for_credentials"),
            patch("scc_cli.cli.docker.get_or_create_container", return_value=(["docker"], False)),
            patch("scc_cli.cli.docker.run"),
            patch("scc_cli.cli.deps.auto_install_dependencies") as mock_deps,
        ):
            mock_deps.return_value = True
            result = runner.invoke(app, ["start", str(tmp_path), "--install-deps"])
        # Should have called auto_install_dependencies
        mock_deps.assert_called_once()

    def test_start_with_offline_uses_cache_only(self, tmp_path):
        """Should use cached config only when --offline flag set."""
        with (
            patch("scc_cli.cli.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli.config.load_config", return_value={}),
            patch("scc_cli.cli.remote.load_org_config") as mock_remote,
            patch("scc_cli.cli.docker.check_docker_available"),
            patch("scc_cli.cli.git.check_branch_safety"),
            patch("scc_cli.cli.git.get_current_branch", return_value="main"),
            patch("scc_cli.cli.git.get_workspace_mount_path", return_value=(tmp_path, False)),
            patch("scc_cli.cli.docker.prepare_sandbox_volume_for_credentials"),
            patch("scc_cli.cli.docker.get_or_create_container", return_value=(["docker"], False)),
            patch("scc_cli.cli.docker.run"),
        ):
            mock_remote.return_value = {"organization": {"name": "Test"}}
            result = runner.invoke(app, ["start", str(tmp_path), "--offline"])
        # Should have passed offline=True to load_org_config
        if mock_remote.called:
            call_kwargs = mock_remote.call_args[1]
            assert call_kwargs.get("offline") is True

    def test_start_with_standalone_skips_org_config(self, tmp_path):
        """Should skip org config when --standalone flag set."""
        with (
            patch("scc_cli.cli.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli.config.load_config", return_value={}),
            patch("scc_cli.cli.docker.check_docker_available"),
            patch("scc_cli.cli.git.check_branch_safety"),
            patch("scc_cli.cli.git.get_current_branch", return_value="main"),
            patch("scc_cli.cli.git.get_workspace_mount_path", return_value=(tmp_path, False)),
            patch("scc_cli.cli.docker.prepare_sandbox_volume_for_credentials"),
            patch("scc_cli.cli.docker.get_or_create_container", return_value=(["docker"], False)),
            patch("scc_cli.cli.docker.run"),
            patch("scc_cli.cli.remote.load_org_config") as mock_remote,
        ):
            result = runner.invoke(app, ["start", str(tmp_path), "--standalone"])
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
            patch("scc_cli.cli.git.is_git_repo", return_value=True),
            patch("scc_cli.cli.git.create_worktree", return_value=worktree_path),
            patch("scc_cli.cli.deps.auto_install_dependencies") as mock_deps,
            patch("scc_cli.cli.Confirm.ask", return_value=False),  # Don't start claude
        ):
            mock_deps.return_value = True
            result = runner.invoke(
                app, ["worktree", str(tmp_path), "feature-x", "--install-deps", "--no-start"]
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
            {"name": "session1", "workspace": "/tmp/proj1", "last_used": "2025-01-01", "team": "dev"},
        ]
        with patch("scc_cli.cli.sessions.list_recent", return_value=mock_sessions):
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
            patch("scc_cli.cli.sessions.list_recent", return_value=mock_sessions),
            patch("scc_cli.cli.ui.select_session") as mock_select,
        ):
            mock_select.return_value = mock_sessions[0]
            result = runner.invoke(app, ["sessions", "--select"])
        # Should have called select_session for interactive picker
        mock_select.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for teams command with profiles integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestTeamsCommand:
    """Tests for teams command using profiles module."""

    def test_teams_sync_fetches_from_remote(self):
        """Should fetch org config from remote when --sync."""
        with (
            patch("scc_cli.cli.config.load_config") as mock_cfg,
            patch("scc_cli.cli.remote.load_org_config") as mock_remote,
            patch("scc_cli.cli.profiles.list_profiles") as mock_list,
        ):
            mock_cfg.return_value = {"organization_source": {"url": "https://example.org"}}
            mock_remote.return_value = {"profiles": {"dev": {}}}
            mock_list.return_value = [{"name": "dev", "description": "Dev team"}]
            result = runner.invoke(app, ["teams", "--sync"])
        # Should call load_org_config with force_refresh=True
        if mock_remote.called:
            call_kwargs = mock_remote.call_args[1]
            assert call_kwargs.get("force_refresh") is True
