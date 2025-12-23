"""
Tests for scc start --dry-run command.

TDD approach: Tests written before implementation.
These tests define the contract for the --dry-run functionality.
"""

import json
from unittest.mock import MagicMock, patch

import click

# ═══════════════════════════════════════════════════════════════════════════════
# Dry Run Basic Behavior Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDryRunBasicBehavior:
    """Test basic --dry-run behavior."""

    def test_dry_run_does_not_launch_docker(self, tmp_path, monkeypatch):
        """--dry-run should NOT start a Docker container."""
        from scc_cli.cli_launch import start

        monkeypatch.chdir(tmp_path)

        # Create a minimal workspace
        (tmp_path / ".git").mkdir()

        mock_docker_run = MagicMock()

        with patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False):
            with patch("scc_cli.cli_launch.config.load_config", return_value={}):
                with patch("scc_cli.cli_launch.config.load_cached_org_config", return_value={}):
                    with patch("scc_cli.cli_launch.docker.run", mock_docker_run):
                        with patch("scc_cli.cli_launch.docker.check_docker_available"):
                            try:
                                start(
                                    workspace=str(tmp_path),
                                    team=None,
                                    session_name=None,
                                    resume=False,
                                    select=False,
                                    continue_session=False,
                                    worktree_name=None,
                                    fresh=False,
                                    install_deps=False,
                                    offline=False,
                                    standalone=False,
                                    dry_run=True,
                                )
                            except click.exceptions.Exit:
                                pass  # Expected exit

        # Docker run should NOT have been called
        mock_docker_run.assert_not_called()

    def test_dry_run_shows_workspace_path(self, tmp_path, monkeypatch, capsys):
        """--dry-run should display the workspace path."""
        from scc_cli.cli_launch import start

        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        with patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False):
            with patch("scc_cli.cli_launch.config.load_config", return_value={}):
                with patch("scc_cli.cli_launch.config.load_cached_org_config", return_value={}):
                    with patch("scc_cli.cli_launch.docker.check_docker_available"):
                        try:
                            start(
                                workspace=str(tmp_path),
                                team=None,
                                session_name=None,
                                resume=False,
                                select=False,
                                continue_session=False,
                                worktree_name=None,
                                fresh=False,
                                install_deps=False,
                                offline=False,
                                standalone=False,
                                dry_run=True,
                            )
                        except click.exceptions.Exit:
                            pass

        captured = capsys.readouterr()
        assert str(tmp_path) in captured.out or "Workspace" in captured.out


# ═══════════════════════════════════════════════════════════════════════════════
# Dry Run Team Configuration Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDryRunTeamConfig:
    """Test --dry-run team configuration display."""

    def test_dry_run_shows_team_name(self, tmp_path, monkeypatch, capsys):
        """--dry-run should display the selected team."""
        from scc_cli.cli_launch import start

        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        mock_org = {
            "profiles": [
                {"name": "platform", "description": "Platform team"},
            ]
        }

        with patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False):
            with patch(
                "scc_cli.cli_launch.config.load_config",
                return_value={"selected_profile": "platform"},
            ):
                with patch(
                    "scc_cli.cli_launch.config.load_cached_org_config",
                    return_value=mock_org,
                ):
                    with patch("scc_cli.cli_launch.docker.check_docker_available"):
                        with patch(
                            "scc_cli.cli_launch.teams.validate_team_profile",
                            return_value={"valid": True},
                        ):
                            with patch("scc_cli.cli_launch.docker.inject_team_settings"):
                                try:
                                    start(
                                        workspace=str(tmp_path),
                                        team="platform",
                                        session_name=None,
                                        resume=False,
                                        select=False,
                                        continue_session=False,
                                        worktree_name=None,
                                        fresh=False,
                                        install_deps=False,
                                        offline=False,
                                        standalone=False,
                                        dry_run=True,
                                    )
                                except click.exceptions.Exit:
                                    pass

        captured = capsys.readouterr()
        assert "platform" in captured.out


# ═══════════════════════════════════════════════════════════════════════════════
# Dry Run JSON Output Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDryRunJsonOutput:
    """Test --dry-run JSON output format."""

    def test_dry_run_json_has_correct_kind(self, tmp_path, monkeypatch, capsys):
        """--dry-run --json should have kind=StartDryRun."""
        from scc_cli.cli_launch import start

        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        with patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False):
            with patch("scc_cli.cli_launch.config.load_config", return_value={}):
                with patch("scc_cli.cli_launch.config.load_cached_org_config", return_value={}):
                    with patch("scc_cli.cli_launch.docker.check_docker_available"):
                        try:
                            start(
                                workspace=str(tmp_path),
                                team=None,
                                session_name=None,
                                resume=False,
                                select=False,
                                continue_session=False,
                                worktree_name=None,
                                fresh=False,
                                install_deps=False,
                                offline=False,
                                standalone=False,
                                dry_run=True,
                                json_output=True,
                                pretty=False,
                            )
                        except click.exceptions.Exit:
                            pass

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["kind"] == "StartDryRun"

    def test_dry_run_json_has_envelope_structure(self, tmp_path, monkeypatch, capsys):
        """--dry-run --json should follow envelope structure."""
        from scc_cli.cli_launch import start

        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        with patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False):
            with patch("scc_cli.cli_launch.config.load_config", return_value={}):
                with patch("scc_cli.cli_launch.config.load_cached_org_config", return_value={}):
                    with patch("scc_cli.cli_launch.docker.check_docker_available"):
                        try:
                            start(
                                workspace=str(tmp_path),
                                team=None,
                                session_name=None,
                                resume=False,
                                select=False,
                                continue_session=False,
                                worktree_name=None,
                                fresh=False,
                                install_deps=False,
                                offline=False,
                                standalone=False,
                                dry_run=True,
                                json_output=True,
                                pretty=False,
                            )
                        except click.exceptions.Exit:
                            pass

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert "apiVersion" in output
        assert output["apiVersion"] == "scc.cli/v1"
        assert "kind" in output
        assert "metadata" in output
        assert "status" in output
        assert "data" in output


# ═══════════════════════════════════════════════════════════════════════════════
# Dry Run Data Builder Tests (Pure Function)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildDryRunData:
    """Test the pure function that builds dry run data."""

    def test_build_dry_run_data_basic(self, tmp_path):
        """build_dry_run_data should assemble configuration information."""
        from scc_cli.cli_launch import build_dry_run_data

        result = build_dry_run_data(
            workspace_path=tmp_path,
            team="platform",
            org_config=None,
            project_config=None,
        )

        assert result["workspace"] == str(tmp_path)
        assert result["team"] == "platform"
        assert "plugins" in result
        assert "ready_to_start" in result

    def test_build_dry_run_data_with_plugins(self, tmp_path):
        """build_dry_run_data should include plugins from org config."""
        from scc_cli.cli_launch import build_dry_run_data

        mock_org = {
            "profiles": [
                {
                    "name": "platform",
                    "plugins": [
                        {"name": "github-copilot"},
                    ],
                }
            ]
        }

        result = build_dry_run_data(
            workspace_path=tmp_path,
            team="platform",
            org_config=mock_org,
            project_config=None,
        )

        assert len(result["plugins"]) > 0
        plugin_names = [p["name"] for p in result["plugins"]]
        assert "github-copilot" in plugin_names

    def test_build_dry_run_data_ready_to_start(self, tmp_path):
        """build_dry_run_data should indicate ready state when no blockers."""
        from scc_cli.cli_launch import build_dry_run_data

        result = build_dry_run_data(
            workspace_path=tmp_path,
            team=None,
            org_config=None,
            project_config=None,
        )

        assert result["ready_to_start"] is True
        assert result["blocked_items"] == []


# ═══════════════════════════════════════════════════════════════════════════════
# Dry Run Exit Code Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDryRunExitCodes:
    """Test --dry-run exit codes."""

    def test_dry_run_exits_zero_when_ready(self, tmp_path, monkeypatch):
        """--dry-run should exit 0 when configuration is valid and ready."""
        from scc_cli.cli_launch import start

        monkeypatch.chdir(tmp_path)
        (tmp_path / ".git").mkdir()

        exit_code = None

        with patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False):
            with patch("scc_cli.cli_launch.config.load_config", return_value={}):
                with patch("scc_cli.cli_launch.config.load_cached_org_config", return_value={}):
                    with patch("scc_cli.cli_launch.docker.check_docker_available"):
                        try:
                            start(
                                workspace=str(tmp_path),
                                team=None,
                                session_name=None,
                                resume=False,
                                select=False,
                                continue_session=False,
                                worktree_name=None,
                                fresh=False,
                                install_deps=False,
                                offline=False,
                                standalone=False,
                                dry_run=True,
                            )
                            exit_code = 0  # If no exit raised, exit code is 0
                        except click.exceptions.Exit as e:
                            exit_code = e.exit_code

        assert exit_code == 0
