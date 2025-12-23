"""
Tests for scc status command.

TDD approach: Tests written before implementation.
These tests define the contract for the status command.
"""

import json
from unittest.mock import patch

import click

# ═══════════════════════════════════════════════════════════════════════════════
# Status Command Basic Output Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatusBasicOutput:
    """Test basic status command output."""

    def test_status_shows_organization_name(self, capsys):
        """Status should display organization name from config."""
        from scc_cli.cli_admin import status_cmd

        mock_cfg = {
            "organization_source": {
                "url": "https://example.org/config.json",
            },
        }
        mock_org = {
            "name": "Acme Corp",
        }

        with patch("scc_cli.cli_admin.config.load_user_config", return_value=mock_cfg):
            with patch("scc_cli.cli_admin.config.load_cached_org_config", return_value=mock_org):
                with patch("scc_cli.cli_admin.docker.list_running_sandboxes", return_value=[]):
                    status_cmd()

        captured = capsys.readouterr()
        assert "Acme Corp" in captured.out

    def test_status_shows_current_team(self, capsys):
        """Status should display currently selected team."""
        from scc_cli.cli_admin import status_cmd

        mock_cfg = {
            "selected_profile": "platform",
        }
        mock_org = {}

        with patch("scc_cli.cli_admin.config.load_user_config", return_value=mock_cfg):
            with patch("scc_cli.cli_admin.config.load_cached_org_config", return_value=mock_org):
                with patch("scc_cli.cli_admin.docker.list_running_sandboxes", return_value=[]):
                    status_cmd()

        captured = capsys.readouterr()
        assert "platform" in captured.out

    def test_status_shows_no_team_selected(self, capsys):
        """Status should handle no team selected gracefully."""
        from scc_cli.cli_admin import status_cmd

        mock_cfg = {}
        mock_org = {}

        with patch("scc_cli.cli_admin.config.load_user_config", return_value=mock_cfg):
            with patch("scc_cli.cli_admin.config.load_cached_org_config", return_value=mock_org):
                with patch("scc_cli.cli_admin.docker.list_running_sandboxes", return_value=[]):
                    status_cmd()

        captured = capsys.readouterr()
        # Should show some indication that no team is selected
        assert "None" in captured.out or "not selected" in captured.out.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Status Command Session Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatusSessionInfo:
    """Test session information in status output."""

    def test_status_shows_running_session(self, capsys):
        """Status should show running session when active."""
        from scc_cli.cli_admin import status_cmd
        from scc_cli.docker.core import ContainerInfo

        mock_cfg = {}
        mock_org = {}
        mock_container = ContainerInfo(
            id="abc123",
            name="scc-myproject-xyz",
            status="Up 2 hours",
            created="2025-01-01T10:00:00Z",
            workspace="/home/user/myproject",
        )

        with patch("scc_cli.cli_admin.config.load_user_config", return_value=mock_cfg):
            with patch("scc_cli.cli_admin.config.load_cached_org_config", return_value=mock_org):
                with patch(
                    "scc_cli.cli_admin.docker.list_running_sandboxes", return_value=[mock_container]
                ):
                    status_cmd()

        captured = capsys.readouterr()
        # Should indicate session is running
        assert "running" in captured.out.lower() or "active" in captured.out.lower()

    def test_status_shows_no_active_session(self, capsys):
        """Status should indicate no active session when none running."""
        from scc_cli.cli_admin import status_cmd

        mock_cfg = {}
        mock_org = {}

        with patch("scc_cli.cli_admin.config.load_user_config", return_value=mock_cfg):
            with patch("scc_cli.cli_admin.config.load_cached_org_config", return_value=mock_org):
                with patch("scc_cli.cli_admin.docker.list_running_sandboxes", return_value=[]):
                    status_cmd()

        captured = capsys.readouterr()
        # Should indicate no active session
        assert (
            "no active" in captured.out.lower()
            or "not running" in captured.out.lower()
            or "none" in captured.out.lower()
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Status Command JSON Output Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatusJsonOutput:
    """Test JSON output format for status command."""

    def test_status_json_has_correct_kind(self, capsys):
        """JSON output should have kind=Status."""
        from scc_cli.cli_admin import status_cmd

        mock_cfg = {}
        mock_org = {}

        with patch("scc_cli.cli_admin.config.load_user_config", return_value=mock_cfg):
            with patch("scc_cli.cli_admin.config.load_cached_org_config", return_value=mock_org):
                with patch("scc_cli.cli_admin.docker.list_running_sandboxes", return_value=[]):
                    try:
                        status_cmd(json_output=True, pretty=False)
                    except click.exceptions.Exit:
                        pass  # Expected - typer.Exit raises click.exceptions.Exit

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        assert output["kind"] == "Status"

    def test_status_json_has_envelope_structure(self, capsys):
        """JSON output should follow envelope structure."""
        from scc_cli.cli_admin import status_cmd

        mock_cfg = {}
        mock_org = {}

        with patch("scc_cli.cli_admin.config.load_user_config", return_value=mock_cfg):
            with patch("scc_cli.cli_admin.config.load_cached_org_config", return_value=mock_org):
                with patch("scc_cli.cli_admin.docker.list_running_sandboxes", return_value=[]):
                    try:
                        status_cmd(json_output=True, pretty=False)
                    except click.exceptions.Exit:
                        pass  # Expected - typer.Exit raises click.exceptions.Exit

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        # Check envelope structure
        assert "apiVersion" in output
        assert output["apiVersion"] == "scc.cli/v1"
        assert "kind" in output
        assert "metadata" in output
        assert "status" in output
        assert "data" in output

    def test_status_json_data_contains_expected_fields(self, capsys):
        """JSON data should contain organization, team, and session info."""
        from scc_cli.cli_admin import status_cmd

        mock_cfg = {
            "organization_source": {"url": "https://example.org/config.json"},
            "selected_profile": "platform",
        }
        mock_org = {"name": "Acme Corp"}

        with patch("scc_cli.cli_admin.config.load_user_config", return_value=mock_cfg):
            with patch("scc_cli.cli_admin.config.load_cached_org_config", return_value=mock_org):
                with patch("scc_cli.cli_admin.docker.list_running_sandboxes", return_value=[]):
                    try:
                        status_cmd(json_output=True, pretty=False)
                    except click.exceptions.Exit:
                        pass  # Expected - typer.Exit raises click.exceptions.Exit

        captured = capsys.readouterr()
        output = json.loads(captured.out)
        data = output["data"]

        # Should have these fields
        assert "organization" in data
        assert "team" in data
        assert "session" in data


# ═══════════════════════════════════════════════════════════════════════════════
# Status Command Verbose Mode Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatusVerboseMode:
    """Test verbose mode for status command."""

    def test_status_verbose_shows_source_urls(self, capsys):
        """Verbose mode should show organization source URL."""
        from scc_cli.cli_admin import status_cmd

        mock_cfg = {
            "organization_source": {"url": "https://example.org/config.json"},
        }
        mock_org = {"name": "Acme Corp"}

        with patch("scc_cli.cli_admin.config.load_user_config", return_value=mock_cfg):
            with patch("scc_cli.cli_admin.config.load_cached_org_config", return_value=mock_org):
                with patch("scc_cli.cli_admin.docker.list_running_sandboxes", return_value=[]):
                    status_cmd(verbose=True)

        captured = capsys.readouterr()
        assert "https://example.org/config.json" in captured.out

    def test_status_verbose_shows_delegation_info(self, capsys):
        """Verbose mode should show team delegation information."""
        from scc_cli.cli_admin import status_cmd

        mock_cfg = {
            "selected_profile": "platform",
        }
        mock_org = {
            "profiles": [
                {
                    "name": "platform",
                    "delegation": {
                        "allow_additional_plugins": True,
                        "allow_additional_mcp_servers": False,
                    },
                }
            ]
        }

        with patch("scc_cli.cli_admin.config.load_user_config", return_value=mock_cfg):
            with patch("scc_cli.cli_admin.config.load_cached_org_config", return_value=mock_org):
                with patch("scc_cli.cli_admin.docker.list_running_sandboxes", return_value=[]):
                    status_cmd(verbose=True)

        captured = capsys.readouterr()
        # Should show delegation info
        assert "delegation" in captured.out.lower() or "plugin" in captured.out.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Status Command Workspace Detection Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatusWorkspaceDetection:
    """Test workspace detection in status command."""

    def test_status_shows_workspace_path(self, capsys, tmp_path, monkeypatch):
        """Status should show current workspace path."""
        from scc_cli.cli_admin import status_cmd

        # Change to temp directory
        monkeypatch.chdir(tmp_path)

        mock_cfg = {}
        mock_org = {}

        with patch("scc_cli.cli_admin.config.load_user_config", return_value=mock_cfg):
            with patch("scc_cli.cli_admin.config.load_cached_org_config", return_value=mock_org):
                with patch("scc_cli.cli_admin.docker.list_running_sandboxes", return_value=[]):
                    status_cmd()

        captured = capsys.readouterr()
        # Should show workspace path
        assert str(tmp_path) in captured.out or "Workspace" in captured.out

    def test_status_indicates_scc_yaml_present(self, capsys, tmp_path, monkeypatch):
        """Status should indicate when .scc.yaml is present in workspace."""
        from scc_cli.cli_admin import status_cmd

        # Create .scc.yaml in temp directory
        scc_yaml = tmp_path / ".scc.yaml"
        scc_yaml.write_text("plugins: []")
        monkeypatch.chdir(tmp_path)

        mock_cfg = {}
        mock_org = {}

        with patch("scc_cli.cli_admin.config.load_user_config", return_value=mock_cfg):
            with patch("scc_cli.cli_admin.config.load_cached_org_config", return_value=mock_org):
                with patch("scc_cli.cli_admin.docker.list_running_sandboxes", return_value=[]):
                    status_cmd()

        captured = capsys.readouterr()
        # Should indicate .scc.yaml was found
        assert ".scc.yaml" in captured.out


# ═══════════════════════════════════════════════════════════════════════════════
# Status Data Builder Tests (Pure Function)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildStatusData:
    """Test the pure function that builds status data."""

    def test_build_status_data_with_full_config(self):
        """build_status_data should assemble all status information."""
        from scc_cli.cli_admin import build_status_data

        cfg = {
            "organization_source": {"url": "https://example.org/config.json"},
            "selected_profile": "platform",
        }
        org = {"name": "Acme Corp"}
        running_containers = []

        result = build_status_data(cfg, org, running_containers)

        assert result["organization"]["name"] == "Acme Corp"
        assert result["team"]["name"] == "platform"
        assert result["session"]["active"] is False

    def test_build_status_data_with_running_session(self):
        """build_status_data should include active session info."""
        from scc_cli.cli_admin import build_status_data
        from scc_cli.docker.core import ContainerInfo

        cfg = {}
        org = {}
        running_containers = [
            ContainerInfo(
                id="abc123",
                name="scc-myproject-xyz",
                status="Up 2 hours",
                created="2025-01-01T10:00:00Z",
                workspace="/home/user/myproject",
            )
        ]

        result = build_status_data(cfg, org, running_containers)

        assert result["session"]["active"] is True
        assert result["session"]["count"] == 1

    def test_build_status_data_with_no_organization(self):
        """build_status_data should handle missing organization gracefully."""
        from scc_cli.cli_admin import build_status_data

        cfg = {}
        org = None
        running_containers = []

        result = build_status_data(cfg, org, running_containers)

        assert result["organization"]["name"] is None
        assert result["organization"]["configured"] is False
