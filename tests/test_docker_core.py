"""Tests for docker module - core functions and error handling.

These tests focus on:
1. Pure functions (no Docker daemon needed)
2. Command construction
3. Error handling paths
4. Security validation (filename injection prevention)

Per plan: Tests verify OUR code behavior, not Docker daemon functionality.
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from scc_cli import docker
from scc_cli.errors import (
    ContainerNotFoundError,
    DockerNotFoundError,
    DockerVersionError,
    SandboxLaunchError,
    SandboxNotAvailableError,
)

# ═══════════════════════════════════════════════════════════════════════════════
# Tests for _parse_version (pure function)
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseVersion:
    """Tests for _parse_version() - version string parsing."""

    def test_parse_standard_version(self):
        """Should parse standard version format."""
        result = docker._parse_version("Docker version 27.5.1, build a187fa5")
        assert result == (27, 5, 1)

    def test_parse_simple_version(self):
        """Should parse simple version string."""
        result = docker._parse_version("4.50.0")
        assert result == (4, 50, 0)

    def test_parse_version_with_prefix(self):
        """Should extract version from longer strings."""
        result = docker._parse_version("Docker Desktop version 4.50.1 on macOS")
        assert result == (4, 50, 1)

    def test_parse_version_invalid_returns_zeros(self):
        """Should return (0, 0, 0) for invalid version strings."""
        result = docker._parse_version("not a version")
        assert result == (0, 0, 0)

    def test_parse_version_empty_string(self):
        """Should return (0, 0, 0) for empty string."""
        result = docker._parse_version("")
        assert result == (0, 0, 0)

    def test_parse_version_partial_version(self):
        """Should handle partial versions in larger strings."""
        # Only complete X.Y.Z matches
        result = docker._parse_version("version 1.2 is incomplete")
        assert result == (0, 0, 0)

    def test_parse_version_multiple_versions_takes_first(self):
        """Should extract first complete version if multiple present."""
        result = docker._parse_version("1.2.3 and 4.5.6")
        assert result == (1, 2, 3)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for generate_container_name (pure function)
# ═══════════════════════════════════════════════════════════════════════════════


class TestGenerateContainerName:
    """Tests for generate_container_name() - deterministic naming."""

    def test_generates_scc_prefix(self, tmp_path):
        """Container name should start with 'scc-' prefix."""
        workspace = tmp_path / "my-project"
        workspace.mkdir()

        name = docker.generate_container_name(workspace)

        assert name.startswith("scc-")

    def test_includes_workspace_name(self, tmp_path):
        """Container name should include sanitized workspace name."""
        workspace = tmp_path / "my-project"
        workspace.mkdir()

        name = docker.generate_container_name(workspace)

        assert "my-project" in name

    def test_deterministic_for_same_workspace(self, tmp_path):
        """Same workspace should always produce same name."""
        workspace = tmp_path / "project"
        workspace.mkdir()

        name1 = docker.generate_container_name(workspace)
        name2 = docker.generate_container_name(workspace)

        assert name1 == name2

    def test_different_branches_produce_different_names(self, tmp_path):
        """Different branches should produce different container names."""
        workspace = tmp_path / "project"
        workspace.mkdir()

        name_main = docker.generate_container_name(workspace, branch="main")
        name_feature = docker.generate_container_name(workspace, branch="feature-x")

        assert name_main != name_feature

    def test_sanitizes_special_characters(self, tmp_path):
        """Should sanitize special characters in workspace name."""
        workspace = tmp_path / "My_Project.V2"
        workspace.mkdir()

        name = docker.generate_container_name(workspace)

        # Should be lowercase and alphanumeric only (with hyphens)
        assert name == name.lower()
        assert "." not in name
        assert "_" not in name or "-" in name  # _ might be converted to -

    def test_hash_suffix_is_8_chars(self, tmp_path):
        """Hash suffix should be exactly 8 characters."""
        workspace = tmp_path / "project"
        workspace.mkdir()

        name = docker.generate_container_name(workspace)

        # Format: scc-<workspace>-<8char_hash>
        parts = name.split("-")
        assert len(parts[-1]) == 8


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for build_labels (pure function)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildLabels:
    """Tests for build_labels() - Docker label construction."""

    def test_always_includes_managed_label(self):
        """Should always include scc.managed=true label."""
        labels = docker.build_labels()

        assert "scc.managed" in labels
        assert labels["scc.managed"] == "true"

    def test_always_includes_created_timestamp(self):
        """Should always include scc.created timestamp."""
        labels = docker.build_labels()

        assert "scc.created" in labels
        # ISO format check
        assert "T" in labels["scc.created"]  # ISO datetime has T separator

    def test_includes_profile_when_provided(self):
        """Should include profile label when specified."""
        labels = docker.build_labels(profile="platform")

        assert "scc.profile" in labels
        assert labels["scc.profile"] == "platform"

    def test_includes_workspace_when_provided(self, tmp_path):
        """Should include workspace label when specified."""
        workspace = tmp_path / "project"

        labels = docker.build_labels(workspace=workspace)

        assert "scc.workspace" in labels
        assert str(workspace) in labels["scc.workspace"]

    def test_includes_branch_when_provided(self):
        """Should include branch label when specified."""
        labels = docker.build_labels(branch="feature-x")

        assert "scc.branch" in labels
        assert labels["scc.branch"] == "feature-x"

    def test_excludes_optional_labels_when_not_provided(self):
        """Should not include optional labels if not specified."""
        labels = docker.build_labels()

        assert "scc.profile" not in labels
        assert "scc.workspace" not in labels
        assert "scc.branch" not in labels


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for build_command (pure function)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildCommand:
    """Tests for build_command() - Docker sandbox command construction.

    Command format: docker sandbox run [-w path] claude [args]
    Credential persistence is handled by:
    - Docker sandbox auto-mounts docker-claude-sandbox-data:/mnt/claude-data
    - run() forking a child process to create symlinks inside container
    """

    def test_basic_command_structure(self):
        """Command should have correct docker sandbox structure."""
        cmd = docker.build_command()

        assert cmd[0] == "docker"
        assert cmd[1] == "sandbox"
        assert cmd[2] == "run"
        assert "claude" in cmd

    def test_no_explicit_volume_mount(self):
        """Should NOT include explicit volume mount (Docker sandbox auto-mounts it).

        Docker sandbox automatically mounts docker-claude-sandbox-data:/mnt/claude-data.
        Adding an explicit -v flag causes "Duplicate mount point" error.
        """
        cmd = docker.build_command()

        # Volume mount should NOT be present (Docker sandbox handles it)
        assert "-v" not in cmd

    def test_does_not_use_credentials_flag(self):
        """Should NOT use --credentials flag (we use symlink workaround instead)."""
        cmd = docker.build_command()

        assert "--credentials" not in cmd

    def test_claude_is_agent(self):
        """Claude should be specified as the agent."""
        cmd = docker.build_command()

        assert "claude" in cmd

    def test_includes_workspace_flag(self, tmp_path):
        """Should include -w flag with workspace path before claude."""
        workspace = tmp_path / "project"
        workspace.mkdir()

        cmd = docker.build_command(workspace=workspace)

        assert "-w" in cmd
        w_idx = cmd.index("-w")
        assert cmd[w_idx + 1] == str(workspace)
        # -w should come before claude
        claude_idx = cmd.index("claude")
        assert w_idx < claude_idx

    def test_continue_session_flag(self):
        """Should include -c flag after claude when continue_session is True."""
        cmd = docker.build_command(continue_session=True)

        claude_idx = cmd.index("claude")
        assert "-c" in cmd
        assert cmd.index("-c") > claude_idx

    def test_resume_flag(self):
        """Should include --resume flag after claude when resume is True."""
        cmd = docker.build_command(resume=True)

        claude_idx = cmd.index("claude")
        assert "--resume" in cmd
        assert cmd.index("--resume") > claude_idx

    def test_continue_takes_precedence_over_resume(self):
        """When both continue and resume are True, only -c should be used."""
        cmd = docker.build_command(continue_session=True, resume=True)

        assert "-c" in cmd
        assert "--resume" not in cmd

    def test_no_session_flags_when_not_specified(self):
        """Should not include session flags when neither continue nor resume specified."""
        cmd = docker.build_command()

        assert "-c" not in cmd
        assert "--resume" not in cmd
        # Without session flags, command should end with 'claude'
        assert cmd[-1] == "claude"
        # Verify expected command structure: docker sandbox run claude
        # (no explicit volume mount - Docker sandbox auto-mounts it)
        assert cmd == ["docker", "sandbox", "run", "claude"]

    def test_detached_mode_includes_d_flag(self):
        """When detached=True, command should include -d flag."""
        cmd = docker.build_command(detached=True)

        assert "-d" in cmd
        # Agent name is ALWAYS required by docker sandbox run
        assert cmd == ["docker", "sandbox", "run", "-d", "claude"]

    def test_detached_mode_includes_claude_agent(self):
        """When detached=True, command should still include claude agent (required by docker)."""
        cmd = docker.build_command(detached=True)

        # docker sandbox run ALWAYS requires the agent name
        assert "claude" in cmd

    def test_detached_mode_skips_session_flags(self):
        """When detached=True, session flags should be skipped (passed via exec later)."""
        cmd = docker.build_command(detached=True, continue_session=True, resume=True)

        assert "-d" in cmd
        assert "claude" in cmd
        # Session flags are passed via docker exec, not during container creation
        assert "-c" not in cmd
        assert "--resume" not in cmd

    def test_detached_with_workspace(self, tmp_path):
        """Detached mode should still include workspace path."""
        workspace = tmp_path / "project"
        workspace.mkdir()

        cmd = docker.build_command(workspace=workspace, detached=True)

        assert "-d" in cmd
        assert "-w" in cmd
        assert str(workspace) in cmd
        assert "claude" in cmd  # Agent always required

    def test_default_not_detached(self):
        """By default, detached should be False and command includes claude."""
        cmd = docker.build_command()

        assert "-d" not in cmd
        assert "claude" in cmd

    # ───────────────────────────────────────────────────────────────────────────
    # Safety-net policy mount tests
    # ───────────────────────────────────────────────────────────────────────────

    def test_policy_mount_when_path_provided(self, tmp_path):
        """When policy_host_path is provided, should include -v mount flag."""
        policy_file = tmp_path / "effective_policy.json"
        policy_file.write_text('{"action": "block"}')

        cmd = docker.build_command(policy_host_path=policy_file)

        assert "-v" in cmd
        # Find the -v argument and verify it includes the host path
        v_idx = cmd.index("-v")
        mount_arg = cmd[v_idx + 1]
        assert str(policy_file) in mount_arg

    def test_policy_env_var_when_path_provided(self, tmp_path):
        """When policy_host_path is provided, should set SCC_POLICY_PATH env var."""
        policy_file = tmp_path / "effective_policy.json"
        policy_file.write_text('{"action": "warn"}')

        cmd = docker.build_command(policy_host_path=policy_file)

        assert "-e" in cmd
        e_idx = cmd.index("-e")
        env_arg = cmd[e_idx + 1]
        assert env_arg.startswith("SCC_POLICY_PATH=")
        # Should point to container path, not host path
        assert "/mnt/claude-data/effective_policy.json" in env_arg

    def test_no_policy_mount_when_path_none(self):
        """When policy_host_path is None, should not include policy mount."""
        cmd = docker.build_command(policy_host_path=None)

        # No -v for policy (test_no_explicit_volume_mount covers general case)
        # But let's be explicit: no SCC_POLICY_PATH env var should be set
        if "-e" in cmd:
            e_idx = cmd.index("-e")
            env_arg = cmd[e_idx + 1]
            assert "SCC_POLICY_PATH" not in env_arg

    def test_policy_mount_is_read_only(self, tmp_path):
        """Policy mount should have :ro suffix for kernel-enforced read-only."""
        policy_file = tmp_path / "effective_policy.json"
        policy_file.write_text('{"action": "block"}')

        cmd = docker.build_command(policy_host_path=policy_file)

        v_idx = cmd.index("-v")
        mount_arg = cmd[v_idx + 1]
        # Mount format: host_path:container_path:ro
        assert mount_arg.endswith(":ro"), f"Mount should end with :ro, got: {mount_arg}"

    def test_policy_path_handles_path_object(self, tmp_path):
        """Policy path should work with pathlib.Path objects via os.fspath()."""
        from pathlib import Path

        policy_file = tmp_path / "effective_policy.json"
        policy_file.write_text('{"action": "allow"}')

        # Explicitly pass as Path object (not string)
        cmd = docker.build_command(policy_host_path=Path(policy_file))

        v_idx = cmd.index("-v")
        mount_arg = cmd[v_idx + 1]
        # Should contain the resolved path string
        assert str(policy_file) in mount_arg

    def test_policy_mount_with_workspace(self, tmp_path):
        """Policy mount should work alongside workspace mount."""
        workspace = tmp_path / "project"
        workspace.mkdir()
        policy_file = tmp_path / "effective_policy.json"
        policy_file.write_text('{"action": "block"}')

        cmd = docker.build_command(workspace=workspace, policy_host_path=policy_file)

        # Both -w (workspace) and -v (policy) should be present
        assert "-w" in cmd
        assert "-v" in cmd
        # Policy mount should come before claude agent
        v_idx = cmd.index("-v")
        claude_idx = cmd.index("claude")
        assert v_idx < claude_idx, "Policy mount should come before claude agent"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for build_start_command (pure function)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildStartCommand:
    """Tests for build_start_command() - container start command."""

    def test_basic_structure(self):
        """Should build docker start command with correct flags."""
        cmd = docker.build_start_command("my-container")

        assert cmd == ["docker", "start", "-ai", "my-container"]

    def test_includes_interactive_flags(self):
        """Should include -ai flags for interactive attach."""
        cmd = docker.build_start_command("test-container")

        assert "-ai" in cmd


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for validate_container_filename (security function)
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateContainerFilename:
    """Tests for validate_container_filename() - security validation.

    SECURITY: This function provides defense-in-depth against path traversal.
    Tests verify all attack vectors are blocked.
    """

    def test_valid_filename_passes(self):
        """Valid filenames should pass validation."""
        assert docker.validate_container_filename("settings.json") == "settings.json"
        assert docker.validate_container_filename("test-file.txt") == "test-file.txt"
        assert docker.validate_container_filename("my_script.sh") == "my_script.sh"

    def test_rejects_empty_filename(self):
        """Should reject empty filename."""
        with pytest.raises(ValueError, match="cannot be empty"):
            docker.validate_container_filename("")

    def test_rejects_forward_slash(self):
        """Should reject forward slashes (path traversal attempt)."""
        with pytest.raises(ValueError, match="path separators not allowed"):
            docker.validate_container_filename("../etc/passwd")

    def test_rejects_backward_slash(self):
        """Should reject backward slashes (Windows path traversal)."""
        with pytest.raises(ValueError, match="path separators not allowed"):
            docker.validate_container_filename("..\\windows\\system32")

    def test_rejects_hidden_files(self):
        """Should reject hidden files starting with dot."""
        with pytest.raises(ValueError, match="hidden files not allowed"):
            docker.validate_container_filename(".bashrc")

    def test_rejects_dot_dot(self):
        """Should reject parent directory reference."""
        with pytest.raises(ValueError, match="path separators not allowed"):
            docker.validate_container_filename("../../etc/shadow")

    def test_rejects_null_bytes(self):
        """Should reject null bytes (C string truncation attack)."""
        with pytest.raises(ValueError, match="null bytes not allowed"):
            docker.validate_container_filename("settings.json\x00.txt")

    def test_complex_traversal_attempt(self):
        """Should reject complex path traversal attempts."""
        with pytest.raises(ValueError, match="path separators not allowed"):
            docker.validate_container_filename("foo/../../../etc/passwd")


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for check_docker_available (error handling)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckDockerAvailable:
    """Tests for check_docker_available() - Docker requirement checking."""

    def test_raises_docker_not_found_when_not_installed(self):
        """Should raise DockerNotFoundError when Docker not installed."""
        with patch("scc_cli.docker.core._check_docker_installed", return_value=False):
            with pytest.raises(DockerNotFoundError):
                docker.check_docker_available()

    def test_raises_version_error_when_too_old(self):
        """Should raise DockerVersionError when version is too old."""
        with (
            patch("scc_cli.docker.core._check_docker_installed", return_value=True),
            patch("scc_cli.docker.core.get_docker_version", return_value="4.0.0"),
            patch("scc_cli.docker.core.check_docker_sandbox", return_value=True),
        ):
            with pytest.raises(DockerVersionError):
                docker.check_docker_available()

    def test_raises_sandbox_not_available_when_missing(self):
        """Should raise SandboxNotAvailableError when sandbox not available."""
        with (
            patch("scc_cli.docker.core._check_docker_installed", return_value=True),
            patch("scc_cli.docker.core.get_docker_version", return_value="27.5.1"),
            patch("scc_cli.docker.core.check_docker_sandbox", return_value=False),
        ):
            with pytest.raises(SandboxNotAvailableError):
                docker.check_docker_available()

    def test_passes_when_all_requirements_met(self):
        """Should not raise when all requirements are met."""
        with (
            patch("scc_cli.docker.core._check_docker_installed", return_value=True),
            patch("scc_cli.docker.core.get_docker_version", return_value="27.5.1"),
            patch("scc_cli.docker.core.check_docker_sandbox", return_value=True),
        ):
            # Should not raise
            docker.check_docker_available()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for _check_docker_installed (pure function)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckDockerInstalled:
    """Tests for _check_docker_installed() - Docker binary detection."""

    def test_returns_true_when_docker_found(self):
        """Should return True when docker is in PATH."""
        with patch("shutil.which", return_value="/usr/local/bin/docker"):
            assert docker._check_docker_installed() is True

    def test_returns_false_when_docker_not_found(self):
        """Should return False when docker is not in PATH."""
        with patch("shutil.which", return_value=None):
            assert docker._check_docker_installed() is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for check_docker_sandbox
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckDockerSandbox:
    """Tests for check_docker_sandbox() - sandbox feature detection."""

    def test_returns_false_when_docker_not_installed(self):
        """Should return False when Docker is not installed."""
        with patch("scc_cli.docker.core._check_docker_installed", return_value=False):
            assert docker.check_docker_sandbox() is False

    def test_checks_sandbox_help_command(self):
        """Should check 'docker sandbox --help' to detect feature."""
        with (
            patch("scc_cli.docker.core._check_docker_installed", return_value=True),
            patch("scc_cli.docker.core.run_command_bool", return_value=True) as mock_run,
        ):
            result = docker.check_docker_sandbox()

            assert result is True
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert call_args == ["docker", "sandbox", "--help"]


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for get_docker_version
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetDockerVersion:
    """Tests for get_docker_version() - version string retrieval."""

    def test_returns_version_string(self):
        """Should return Docker version string."""
        with patch("scc_cli.docker.core.run_command", return_value="Docker version 27.5.1"):
            result = docker.get_docker_version()

            assert result == "Docker version 27.5.1"

    def test_returns_none_on_failure(self):
        """Should return None when command fails."""
        with patch("scc_cli.docker.core.run_command", return_value=None):
            result = docker.get_docker_version()

            assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for container_exists
# ═══════════════════════════════════════════════════════════════════════════════


class TestContainerExists:
    """Tests for container_exists() - container existence check."""

    def test_returns_true_when_container_exists(self):
        """Should return True when container name is in output."""
        with patch("scc_cli.docker.core.run_command", return_value="my-container"):
            assert docker.container_exists("my-container") is True

    def test_returns_false_when_container_not_found(self):
        """Should return False when container name not in output."""
        with patch("scc_cli.docker.core.run_command", return_value=""):
            assert docker.container_exists("my-container") is False

    def test_returns_false_on_command_failure(self):
        """Should return False when command fails."""
        with patch("scc_cli.docker.core.run_command", return_value=None):
            assert docker.container_exists("my-container") is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for get_container_status
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetContainerStatus:
    """Tests for get_container_status() - container status retrieval."""

    def test_returns_status_string(self):
        """Should return status string when container exists."""
        with patch("scc_cli.docker.core.run_command", return_value="Up 2 hours"):
            result = docker.get_container_status("my-container")

            assert result == "Up 2 hours"

    def test_returns_none_when_not_found(self):
        """Should return None when container not found."""
        with patch("scc_cli.docker.core.run_command", return_value=""):
            result = docker.get_container_status("my-container")

            assert result is None

    def test_returns_none_on_command_failure(self):
        """Should return None when command fails."""
        with patch("scc_cli.docker.core.run_command", return_value=None):
            result = docker.get_container_status("my-container")

            assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for run (error handling)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRun:
    """Tests for run() - Docker command execution.

    Note: We test error handling, not Docker daemon behavior.
    Credential persistence is now handled by the wrapper script in build_command(),
    eliminating the previous fork/sleep workaround.

    Tests that patch os.name to "nt" must also mock write_safety_net_policy_to_host
    because the policy writer uses get_cache_dir() which is platform-specific.
    """

    def test_raises_sandbox_launch_error_on_file_not_found(self):
        """Should raise SandboxLaunchError when command not found."""
        with (
            patch("os.name", "nt"),  # Windows path for easier testing
            patch(
                "scc_cli.docker.launch.write_safety_net_policy_to_host",
                return_value=None,
            ),
            patch("subprocess.run", side_effect=FileNotFoundError()),
        ):
            with pytest.raises(SandboxLaunchError) as exc_info:
                docker.run(["nonexistent-cmd"])

            assert "not found" in str(exc_info.value).lower()

    def test_raises_sandbox_launch_error_on_os_error(self):
        """Should raise SandboxLaunchError on OS error."""
        with (
            patch("os.name", "nt"),  # Windows path for easier testing
            patch(
                "scc_cli.docker.launch.write_safety_net_policy_to_host",
                return_value=None,
            ),
            patch("subprocess.run", side_effect=OSError("Permission denied")),
        ):
            with pytest.raises(SandboxLaunchError):
                docker.run(["docker", "sandbox", "run"])

    def test_windows_uses_subprocess_run(self):
        """On Windows, should use subprocess.run instead of execvp."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with (
            patch("os.name", "nt"),
            patch(
                "scc_cli.docker.launch.write_safety_net_policy_to_host",
                return_value=None,
            ),
            patch("subprocess.run", return_value=mock_result) as mock_subprocess,
        ):
            result = docker.run(["docker", "sandbox", "run"])

            mock_subprocess.assert_called_once()
            assert result == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for start_container (error handling)
# ═══════════════════════════════════════════════════════════════════════════════


class TestStartContainer:
    """Tests for start_container() - container start operations."""

    def test_raises_container_not_found_when_missing(self):
        """Should raise ContainerNotFoundError when container doesn't exist."""
        with patch("scc_cli.docker.core.container_exists", return_value=False):
            with pytest.raises(ContainerNotFoundError) as exc_info:
                docker.start_container("nonexistent-container")

            assert "nonexistent-container" in str(exc_info.value)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for stop_container and remove_container
# ═══════════════════════════════════════════════════════════════════════════════


class TestStopContainer:
    """Tests for stop_container() - container stop operations."""

    def test_calls_docker_stop(self):
        """Should call docker stop with container ID."""
        with patch("scc_cli.docker.core.run_command_bool", return_value=True) as mock_run:
            result = docker.stop_container("abc123")

            assert result is True
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert call_args == ["docker", "stop", "abc123"]


class TestRemoveContainer:
    """Tests for remove_container() - container removal operations."""

    def test_calls_docker_rm(self):
        """Should call docker rm with container name."""
        with patch("scc_cli.docker.core.run_command_bool", return_value=True) as mock_run:
            result = docker.remove_container("my-container")

            assert result is True
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert call_args == ["docker", "rm", "my-container"]

    def test_force_flag_adds_f(self):
        """Should add -f flag when force is True."""
        with patch("scc_cli.docker.core.run_command_bool", return_value=True) as mock_run:
            docker.remove_container("my-container", force=True)

            call_args = mock_run.call_args[0][0]
            assert "-f" in call_args


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for run_detached
# ═══════════════════════════════════════════════════════════════════════════════


class TestRunDetached:
    """Tests for run_detached() - background execution."""

    def test_starts_process_in_background(self):
        """Should start subprocess with background settings."""
        mock_popen = MagicMock()

        with patch("subprocess.Popen", return_value=mock_popen) as mock_popen_class:
            result = docker.run_detached(["docker", "sandbox", "run"])

            assert result == mock_popen
            mock_popen_class.assert_called_once()
            call_kwargs = mock_popen_class.call_args[1]
            assert call_kwargs["start_new_session"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for list_scc_containers
# ═══════════════════════════════════════════════════════════════════════════════


class TestListSccContainers:
    """Tests for list_scc_containers() - container listing."""

    def test_returns_container_info_list(self):
        """Should parse container list output correctly."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "abc123\tmy-container\tUp 2 hours\tplatform\t/home/user/proj\tmain\n"

        with patch("subprocess.run", return_value=mock_result):
            containers = docker.list_scc_containers()

            assert len(containers) == 1
            assert containers[0].id == "abc123"
            assert containers[0].name == "my-container"
            assert containers[0].status == "Up 2 hours"
            assert containers[0].profile == "platform"
            assert containers[0].workspace == "/home/user/proj"
            assert containers[0].branch == "main"

    def test_returns_empty_list_on_failure(self):
        """Should return empty list when command fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            containers = docker.list_scc_containers()

            assert containers == []

    def test_handles_timeout(self):
        """Should return empty list on timeout."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 10)):
            containers = docker.list_scc_containers()

            assert containers == []

    def test_handles_docker_not_found(self):
        """Should return empty list when Docker not found."""
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            containers = docker.list_scc_containers()

            assert containers == []


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for list_running_sandboxes
# ═══════════════════════════════════════════════════════════════════════════════


class TestListRunningSandboxes:
    """Tests for list_running_sandboxes() - sandbox listing."""

    def test_returns_sandbox_info_list(self):
        """Should parse sandbox list output correctly."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "xyz789\tclaude-sandbox-abc\tUp 30 minutes\n"

        with patch("subprocess.run", return_value=mock_result):
            sandboxes = docker.list_running_sandboxes()

            assert len(sandboxes) == 1
            assert sandboxes[0].id == "xyz789"
            assert sandboxes[0].name == "claude-sandbox-abc"
            assert sandboxes[0].status == "Up 30 minutes"

    def test_returns_empty_list_on_failure(self):
        """Should return empty list when command fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            sandboxes = docker.list_running_sandboxes()

            assert sandboxes == []


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for prepare_sandbox_volume_for_credentials
# ═══════════════════════════════════════════════════════════════════════════════


class TestPrepareSandboxVolumeForCredentials:
    """Tests for prepare_sandbox_volume_for_credentials().

    Prepares both .claude.json (OAuth/Claude Max) and credentials.json (API keys)
    in the Docker volume with proper permissions for the agent user (uid=1000).

    NOTE: This is an INTENTIONAL workaround for Docker Desktop bugs.
    We test that the workaround WORKS, not that it "should not exist".
    """

    def test_returns_true_on_success(self):
        """Should return True when volume preparation succeeds."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = docker.prepare_sandbox_volume_for_credentials()

            assert result is True

    def test_returns_false_on_failure(self):
        """Should return False when volume preparation fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = docker.prepare_sandbox_volume_for_credentials()

            assert result is False

    def test_handles_timeout(self):
        """Should return False on timeout."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 30)):
            result = docker.prepare_sandbox_volume_for_credentials()

            assert result is False

    def test_handles_docker_not_found(self):
        """Should return False when Docker not found."""
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = docker.prepare_sandbox_volume_for_credentials()

            assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for get_or_create_container
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetOrCreateContainer:
    """Tests for get_or_create_container() - container management."""

    def test_returns_command_tuple(self, tmp_path):
        """Should return tuple of (command, is_resume)."""
        workspace = tmp_path / "project"
        workspace.mkdir()

        cmd, is_resume = docker.get_or_create_container(workspace=workspace)

        assert isinstance(cmd, list)
        assert isinstance(is_resume, bool)

    def test_is_resume_always_false_for_sandboxes(self, tmp_path):
        """Sandboxes don't support resume - is_resume should always be False."""
        workspace = tmp_path / "project"
        workspace.mkdir()

        _, is_resume = docker.get_or_create_container(workspace=workspace)

        # Docker sandbox is ephemeral - no resume support
        assert is_resume is False

    def test_command_includes_workspace(self, tmp_path):
        """Command should include workspace mount."""
        workspace = tmp_path / "project"
        workspace.mkdir()

        cmd, _ = docker.get_or_create_container(workspace=workspace)

        assert "-w" in cmd
        assert str(workspace) in cmd

    def test_continue_session_flag_passed(self, tmp_path):
        """Should pass continue_session flag to build_command."""
        workspace = tmp_path / "project"
        workspace.mkdir()

        cmd, _ = docker.get_or_create_container(workspace=workspace, continue_session=True)

        assert "-c" in cmd
