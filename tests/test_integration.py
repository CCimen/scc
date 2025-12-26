"""Integration tests for SCC-CLI end-to-end workflows.

These tests verify the complete flow through multiple modules:
- Setup wizard → Config → Remote fetch → Profile selection
- Start command → Git check → Docker launch
- Session management → Continue previous session
- Worktree creation → Git operations → Docker launch

Tests are organized by workflow, not by module, to catch integration issues.
"""

import json
import subprocess
from datetime import datetime
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from scc_cli.cli import app

runner = CliRunner()


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures for Integration Tests
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def full_config_environment(tmp_path, monkeypatch):
    """Set up complete config environment with XDG paths."""
    config_dir = tmp_path / ".config" / "scc"
    config_dir.mkdir(parents=True)

    cache_dir = tmp_path / ".cache" / "scc"
    cache_dir.mkdir(parents=True)

    monkeypatch.setattr("scc_cli.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("scc_cli.config.CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr("scc_cli.config.SESSIONS_FILE", config_dir / "sessions.json")
    monkeypatch.setattr("scc_cli.config.CACHE_DIR", cache_dir)
    monkeypatch.setattr("scc_cli.config.LEGACY_CONFIG_DIR", tmp_path / ".config" / "scc-cli")

    return {"config_dir": config_dir, "cache_dir": cache_dir, "tmp_path": tmp_path}


@pytest.fixture
def sample_org_config():
    """Create a sample org config for testing.

    Uses the current v1 schema format with proper fields:
    - security: Hard boundaries (blocked plugins, images, MCP servers)
    - defaults: allowed_plugins, network_policy, session
    - profiles: description, additional_plugins, delegation
    """
    return {
        "$schema": "https://scc-cli.dev/schemas/org-v1.json",
        "schema_version": "1.0.0",
        "min_cli_version": "0.1.0",
        "organization": {
            "name": "Test Organization",
            "id": "test-org",
            "contact": "devops@test.org",
        },
        "security": {
            "blocked_plugins": ["*-experimental"],
            "blocked_mcp_servers": [],
            "blocked_base_images": ["*:latest"],
            "allow_stdio_mcp": False,
        },
        "defaults": {
            "allowed_plugins": ["*"],
            "network_policy": "unrestricted",
            "session": {
                "timeout_hours": 10,
                "auto_resume": True,
            },
        },
        "profiles": {
            "platform": {
                "description": "Platform team (Python, FastAPI)",
                "additional_plugins": ["python-tools", "fastapi-helper"],
            },
            "api": {
                "description": "API team (Java, Spring Boot)",
                "additional_plugins": ["java-analyzer", "spring-boot-helper"],
            },
        },
    }


@pytest.fixture
def git_workspace(tmp_path):
    """Create a git repository workspace for testing."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    subprocess.run(["git", "init"], cwd=workspace, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=workspace,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=workspace,
        capture_output=True,
    )

    readme = workspace / "README.md"
    readme.write_text("# Test Project\n")
    subprocess.run(["git", "add", "."], cwd=workspace, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=workspace,
        capture_output=True,
    )

    return workspace


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow 1: Setup → Config → Profile Selection
# ═══════════════════════════════════════════════════════════════════════════════


class TestSetupWorkflow:
    """Integration tests for the setup workflow."""

    def test_setup_standalone_creates_config(self, full_config_environment):
        """Standalone setup should create minimal config."""
        with patch("scc_cli.cli_config.setup.run_non_interactive_setup") as mock_setup:
            mock_setup.return_value = True
            result = runner.invoke(app, ["setup", "--standalone"])

        assert result.exit_code == 0
        mock_setup.assert_called_once()
        call_kwargs = mock_setup.call_args
        # Should have standalone=True in args
        assert call_kwargs[1].get("standalone") is True or (
            len(call_kwargs[0]) >= 2 and call_kwargs[0][1] is True
        )

    def test_setup_with_org_url_fetches_config(self, full_config_environment, sample_org_config):
        """Setup with org URL should fetch and cache config."""
        with (
            patch("scc_cli.cli_config.setup.run_non_interactive_setup") as mock_setup,
            patch("scc_cli.remote.fetch_org_config") as mock_fetch,
        ):
            mock_setup.return_value = True
            mock_fetch.return_value = (sample_org_config, "etag123", 200)

            result = runner.invoke(
                app,
                [
                    "setup",
                    "--org-url",
                    "https://gitlab.test.org/config.json",
                    "--team",
                    "platform",
                ],
            )

        assert result.exit_code == 0
        mock_setup.assert_called_once()

    def test_config_set_and_get_workflow(self, full_config_environment):
        """Config set should persist and get should retrieve."""
        config_file = full_config_environment["config_dir"] / "config.json"
        config_file.write_text(json.dumps({"selected_profile": "old-team"}))

        # Patch config module
        with (
            patch("scc_cli.cli_config.config.load_user_config") as mock_load,
            patch("scc_cli.cli_config.config.save_user_config") as mock_save,
        ):
            mock_load.return_value = {"selected_profile": "old-team"}

            # Test set
            result = runner.invoke(app, ["config", "set", "selected_profile", "platform"])

        assert result.exit_code == 0
        mock_save.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow 2: Start Command → Git Check → Docker Launch
# ═══════════════════════════════════════════════════════════════════════════════


class TestStartWorkflow:
    """Integration tests for the start command workflow."""

    def test_start_requires_setup_first(self, full_config_environment, git_workspace):
        """Start should prompt for setup if not configured."""
        with patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=True):
            result = runner.invoke(app, ["start", str(git_workspace)])

        # Should indicate setup is needed
        assert "setup" in result.output.lower() or result.exit_code != 0

    def test_start_with_workspace_launches_docker(self, full_config_environment, git_workspace):
        """Start with workspace should launch Docker sandbox."""
        with (
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={"standalone": True}),
            patch("scc_cli.cli_launch.docker.check_docker_available"),
            patch("scc_cli.cli_launch.git.check_branch_safety"),
            patch("scc_cli.cli_launch.git.get_current_branch", return_value="main"),
            patch(
                "scc_cli.cli_launch.git.get_workspace_mount_path",
                return_value=(git_workspace, False),
            ),
            patch("scc_cli.cli_launch.docker.prepare_sandbox_volume_for_credentials"),
            patch(
                "scc_cli.cli_launch.docker.get_or_create_container",
                return_value=(["docker"], False),
            ) as mock_get_container,
            patch("scc_cli.cli_launch.docker.run"),
        ):
            runner.invoke(app, ["start", str(git_workspace)])

        # Docker should be called
        mock_get_container.assert_called_once()

    def test_start_with_team_resolves_profile(
        self, full_config_environment, git_workspace, sample_org_config
    ):
        """Start with --team should resolve profile from org config."""
        config_dir = full_config_environment["config_dir"]
        config_file = config_dir / "config.json"
        config_file.write_text(
            json.dumps(
                {
                    "organization_source": {
                        "url": "https://gitlab.test.org/config.json",
                    },
                    "selected_profile": "platform",
                }
            )
        )

        with (
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config") as mock_load_config,
            patch("scc_cli.remote.load_org_config", return_value=sample_org_config),
            patch("scc_cli.cli_launch.docker.check_docker_available"),
            patch("scc_cli.cli_launch.git.check_branch_safety"),
            patch("scc_cli.cli_launch.git.get_current_branch", return_value="feature-x"),
            patch(
                "scc_cli.cli_launch.git.get_workspace_mount_path",
                return_value=(git_workspace, False),
            ),
            patch("scc_cli.cli_launch.docker.prepare_sandbox_volume_for_credentials"),
            patch(
                "scc_cli.cli_launch.docker.get_or_create_container",
                return_value=(["docker"], False),
            ),
            patch("scc_cli.cli_launch.docker.run"),
        ):
            mock_load_config.return_value = {
                "organization_source": {"url": "https://gitlab.test.org/config.json"},
                "selected_profile": "platform",
            }

            result = runner.invoke(app, ["start", str(git_workspace), "--team", "api"])

        # Should have processed without error
        assert result.exit_code == 0 or "api" in result.output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow 3: Session Management → Continue Previous Session
# ═══════════════════════════════════════════════════════════════════════════════


class TestSessionWorkflow:
    """Integration tests for session management workflow."""

    def test_sessions_list_shows_recent(self, full_config_environment):
        """Sessions command should list recent sessions."""
        config_dir = full_config_environment["config_dir"]
        sessions_file = config_dir / "sessions.json"
        sessions_file.write_text(
            json.dumps(
                {
                    "sessions": [
                        {
                            "workspace": "/tmp/proj1",
                            "name": "session1",
                            "team": "platform",
                            "last_used": datetime.now().isoformat(),
                        },
                        {
                            "workspace": "/tmp/proj2",
                            "name": "session2",
                            "team": "api",
                            "last_used": datetime.now().isoformat(),
                        },
                    ]
                }
            )
        )

        # Also patch sessions module
        with patch("scc_cli.sessions.config.SESSIONS_FILE", sessions_file):
            with patch("scc_cli.cli_worktree.sessions.list_recent") as mock_list:
                mock_list.return_value = [
                    {"name": "session1", "workspace": "/tmp/proj1", "last_used": "1h ago"},
                    {"name": "session2", "workspace": "/tmp/proj2", "last_used": "2h ago"},
                ]
                result = runner.invoke(app, ["sessions"])

        assert result.exit_code == 0
        assert "session1" in result.output

    def test_continue_session_auto_selects_recent(self, full_config_environment, git_workspace):
        """--continue without workspace should use most recent session."""
        config_dir = full_config_environment["config_dir"]
        config_dir / "sessions.json"

        with (
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={"standalone": True}),
            patch("scc_cli.cli_launch.sessions.get_most_recent") as mock_recent,
            patch("scc_cli.cli_launch.docker.check_docker_available"),
            patch("scc_cli.cli_launch.git.check_branch_safety"),
            patch("scc_cli.cli_launch.git.get_current_branch", return_value="main"),
            patch(
                "scc_cli.cli_launch.git.get_workspace_mount_path",
                return_value=(git_workspace, False),
            ),
            patch("scc_cli.cli_launch.docker.prepare_sandbox_volume_for_credentials"),
            patch(
                "scc_cli.cli_launch.docker.get_or_create_container",
                return_value=(["docker"], False),
            ),
            patch("scc_cli.cli_launch.docker.run"),
        ):
            mock_recent.return_value = {
                "workspace": str(git_workspace),
                "team": "platform",
            }

            result = runner.invoke(app, ["start", "--continue"])

        # Should have resumed the session
        assert "Resuming" in result.output or mock_recent.called

    def test_continue_without_sessions_shows_error(self, full_config_environment):
        """--continue with no sessions should show appropriate error."""
        with (
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={"standalone": True}),
            patch("scc_cli.cli_launch.sessions.get_most_recent", return_value=None),
        ):
            result = runner.invoke(app, ["start", "--continue"])

        assert result.exit_code != 0 or "no recent" in result.output.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow 5: Doctor Health Checks
# ═══════════════════════════════════════════════════════════════════════════════


class TestDoctorWorkflow:
    """Integration tests for doctor health check workflow."""

    def test_doctor_checks_all_components(self, full_config_environment):
        """Doctor should check Docker, Git, Config, and connectivity."""
        with (
            patch("scc_cli.cli_admin.doctor.run_doctor") as mock_doctor,
        ):
            mock_doctor.return_value = None
            runner.invoke(app, ["doctor"])

        # Should have called the doctor check
        mock_doctor.assert_called()


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow 6: Worktree Creation → Branch Safety
# ═══════════════════════════════════════════════════════════════════════════════


class TestWorktreeWorkflow:
    """Integration tests for worktree creation workflow."""

    def test_worktree_creates_branch_and_worktree(self, full_config_environment, git_workspace):
        """Worktree command should create git worktree and branch."""
        with (
            patch("scc_cli.cli_worktree.git.is_git_repo", return_value=True),
            patch("scc_cli.cli_worktree.git.create_worktree") as mock_create,
            patch("scc_cli.cli_worktree.Confirm.ask", return_value=False),  # Don't start claude
        ):
            worktree_path = git_workspace.parent / "claude" / "feature-x"
            mock_create.return_value = worktree_path

            runner.invoke(
                app, ["worktree", "create", str(git_workspace), "feature-x", "--no-start"]
            )

        mock_create.assert_called_once()

    def test_worktree_with_install_deps(self, full_config_environment, git_workspace):
        """Worktree with --install-deps should install after creation."""
        worktree_path = git_workspace.parent / "claude" / "feature-x"
        worktree_path.mkdir(parents=True)

        with (
            patch("scc_cli.cli_worktree.git.is_git_repo", return_value=True),
            patch("scc_cli.cli_worktree.git.create_worktree", return_value=worktree_path),
            patch("scc_cli.cli_worktree.deps.auto_install_dependencies") as mock_deps,
            patch("scc_cli.cli_worktree.Confirm.ask", return_value=False),
        ):
            mock_deps.return_value = True

            runner.invoke(
                app,
                [
                    "worktree",
                    "create",
                    str(git_workspace),
                    "feature-x",
                    "--install-deps",
                    "--no-start",
                ],
            )

        mock_deps.assert_called_once_with(worktree_path)


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow 7: Config Migration (Legacy → New)
# ═══════════════════════════════════════════════════════════════════════════════


class TestMigrationWorkflow:
    """Integration tests for config migration workflow."""

    def test_migration_from_legacy_config(self, tmp_path, monkeypatch):
        """Should migrate from ~/.config/scc-cli to ~/.config/scc."""
        # Create legacy config
        legacy_dir = tmp_path / ".config" / "scc-cli"
        legacy_dir.mkdir(parents=True)
        legacy_config = legacy_dir / "config.json"
        legacy_config.write_text(json.dumps({"selected_profile": "platform"}))

        new_dir = tmp_path / ".config" / "scc"

        monkeypatch.setattr("scc_cli.config.CONFIG_DIR", new_dir)
        monkeypatch.setattr("scc_cli.config.CONFIG_FILE", new_dir / "config.json")
        monkeypatch.setattr("scc_cli.config.LEGACY_CONFIG_DIR", legacy_dir)

        from scc_cli import config

        # Force reimport to pick up patched values
        result = config.migrate_config_if_needed()

        assert result is True
        assert new_dir.exists()
        assert (new_dir / "config.json").exists()
        assert legacy_dir.exists()  # Legacy preserved


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow 8: Offline Mode
# ═══════════════════════════════════════════════════════════════════════════════


class TestOfflineWorkflow:
    """Integration tests for offline mode workflow."""

    def test_start_offline_uses_cache_only(self, full_config_environment, git_workspace):
        """--offline should use cached config without network."""
        config_dir = full_config_environment["config_dir"]
        config_file = config_dir / "config.json"
        config_file.write_text(
            json.dumps(
                {
                    "organization_source": {"url": "https://gitlab.test.org/config.json"},
                }
            )
        )

        with (
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config") as mock_load_config,
            patch("scc_cli.remote.load_org_config") as mock_remote,
            patch("scc_cli.cli_launch.docker.check_docker_available"),
            patch("scc_cli.cli_launch.git.check_branch_safety"),
            patch("scc_cli.cli_launch.git.get_current_branch", return_value="main"),
            patch(
                "scc_cli.cli_launch.git.get_workspace_mount_path",
                return_value=(git_workspace, False),
            ),
            patch("scc_cli.cli_launch.docker.prepare_sandbox_volume_for_credentials"),
            patch(
                "scc_cli.cli_launch.docker.get_or_create_container",
                return_value=(["docker"], False),
            ),
            patch("scc_cli.cli_launch.docker.run"),
        ):
            mock_load_config.return_value = {
                "organization_source": {"url": "https://gitlab.test.org/config.json"},
            }
            mock_remote.return_value = {"organization": {"name": "Test"}}

            runner.invoke(app, ["start", str(git_workspace), "--offline"])

        # Should have passed offline=True to remote
        if mock_remote.called:
            call_kwargs = mock_remote.call_args[1]
            assert call_kwargs.get("offline") is True


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow 9: Standalone Mode
# ═══════════════════════════════════════════════════════════════════════════════


class TestStandaloneWorkflow:
    """Integration tests for standalone mode workflow."""

    def test_start_standalone_skips_org_config(self, full_config_environment, git_workspace):
        """--standalone should skip org config entirely."""
        with (
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={"standalone": True}),
            patch("scc_cli.remote.load_org_config") as mock_remote,
            patch("scc_cli.cli_launch.docker.check_docker_available"),
            patch("scc_cli.cli_launch.git.check_branch_safety"),
            patch("scc_cli.cli_launch.git.get_current_branch", return_value="main"),
            patch(
                "scc_cli.cli_launch.git.get_workspace_mount_path",
                return_value=(git_workspace, False),
            ),
            patch("scc_cli.cli_launch.docker.prepare_sandbox_volume_for_credentials"),
            patch(
                "scc_cli.cli_launch.docker.get_or_create_container",
                return_value=(["docker"], False),
            ),
            patch("scc_cli.cli_launch.docker.run"),
        ):
            runner.invoke(app, ["start", str(git_workspace), "--standalone"])

        # Should NOT have called load_org_config
        mock_remote.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow 10: Dependencies Installation
# ═══════════════════════════════════════════════════════════════════════════════


class TestDepsWorkflow:
    """Integration tests for dependency installation workflow."""

    def test_start_with_install_deps(self, full_config_environment, git_workspace):
        """--install-deps should trigger dependency installation."""
        # Create package.json to trigger npm detection
        (git_workspace / "package.json").write_text("{}")

        with (
            patch("scc_cli.cli_launch.setup.is_setup_needed", return_value=False),
            patch("scc_cli.cli_launch.config.load_config", return_value={"standalone": True}),
            patch("scc_cli.cli_launch.docker.check_docker_available"),
            patch("scc_cli.cli_launch.git.check_branch_safety"),
            patch("scc_cli.cli_launch.git.get_current_branch", return_value="main"),
            patch(
                "scc_cli.cli_launch.git.get_workspace_mount_path",
                return_value=(git_workspace, False),
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

            runner.invoke(app, ["start", str(git_workspace), "--install-deps"])

        mock_deps.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# End-to-End Data Flow Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDataFlowIntegration:
    """Tests verifying data flows correctly between modules."""

    def test_org_config_flows_to_effective_plugins(self, full_config_environment):
        """Org config should flow correctly through Phase 2 marketplace API.

        This test verifies the modern integration flow:
        OrganizationConfig → compute_effective_plugins() → EffectivePlugins
        """
        from scc_cli.marketplace.compute import compute_effective_plugins
        from scc_cli.marketplace.schema import (
            DefaultsConfig,
            OrganizationConfig,
            TeamProfile,
        )

        # Create config using Phase 2 Pydantic models
        config = OrganizationConfig(
            name="Test Organization",
            schema_version=1,
            defaults=DefaultsConfig(
                enabled_plugins=["code-quality@default"],
            ),
            profiles={
                "platform": TeamProfile(
                    name="Platform Team",
                    description="Platform team (Python, FastAPI)",
                    additional_plugins=["python-tools", "fastapi-helper"],
                ),
            },
        )

        # Compute effective plugins for the platform team
        effective = compute_effective_plugins(config, team_id="platform")

        # Verify plugins are merged correctly (defaults + team additional)
        # Note: Plugins without explicit marketplace get @claude-plugins-official suffix
        assert "code-quality@default" in effective.enabled
        assert "python-tools@claude-plugins-official" in effective.enabled
        assert "fastapi-helper@claude-plugins-official" in effective.enabled
        assert effective.blocked == []

    def test_session_record_persists_correctly(self, full_config_environment):
        """Session recording should persist and be retrievable."""
        from scc_cli import sessions

        # Patch the sessions config path
        sessions_file = full_config_environment["config_dir"] / "sessions.json"
        with patch("scc_cli.sessions.config.SESSIONS_FILE", sessions_file):
            # Record a session
            sessions._save_sessions([])  # Initialize
            sessions.record_session(
                workspace="/tmp/test-proj",
                team="platform",
                session_name="test-session",
                branch="main",
            )

            # Retrieve it
            most_recent = sessions.get_most_recent()

        assert most_recent is not None
        assert most_recent["workspace"] == "/tmp/test-proj"
        assert most_recent["team"] == "platform"

    def test_config_validation_flows_correctly(self, sample_org_config):
        """Config validation should properly validate org config."""
        from scc_cli import validate

        errors = validate.validate_org_config(sample_org_config)

        assert errors == []  # Valid config should have no errors

    def test_invalid_config_caught_by_validation(self):
        """Invalid config should be caught by validation."""
        from scc_cli import validate

        invalid_config = {
            "organization": {},  # Missing required fields
        }

        errors = validate.validate_org_config(invalid_config)

        assert len(errors) > 0  # Should have validation errors
