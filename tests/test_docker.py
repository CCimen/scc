"""Tests for docker module - settings injection utilities.

Tests for the low-level Docker utilities:
- reset_global_settings() global settings reset
- inject_file_to_sandbox_volume() file injection
- get_sandbox_settings() reading existing sandbox settings
"""

from unittest.mock import MagicMock, patch

from scc_cli import docker

# ═══════════════════════════════════════════════════════════════════════════════
# Tests for reset_global_settings
# ═══════════════════════════════════════════════════════════════════════════════


class TestResetGlobalSettings:
    """Tests for reset_global_settings function."""

    def test_reset_global_settings_success(self):
        """reset_global_settings should return True on success."""
        with patch(
            "scc_cli.docker.launch.inject_file_to_sandbox_volume", return_value=True
        ) as mock_inject:
            result = docker.reset_global_settings()

            assert result is True
            mock_inject.assert_called_once_with("settings.json", "{}")

    def test_reset_global_settings_failure(self):
        """reset_global_settings should return False on failure."""
        with patch("scc_cli.docker.launch.inject_file_to_sandbox_volume", return_value=False):
            result = docker.reset_global_settings()

            assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for inject_file_to_sandbox_volume
# ═══════════════════════════════════════════════════════════════════════════════


class TestInjectFileToSandboxVolume:
    """Tests for inject_file_to_sandbox_volume function."""

    def test_inject_file_success(self):
        """inject_file_to_sandbox_volume should return True on success."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = docker.inject_file_to_sandbox_volume("test.txt", "test content")

            assert result is True
            mock_run.assert_called_once()
            # Verify docker command structure
            call_args = mock_run.call_args[0][0]
            assert call_args[0] == "docker"
            assert call_args[1] == "run"
            assert "--rm" in call_args
            assert "alpine" in call_args

    def test_inject_file_failure(self):
        """inject_file_to_sandbox_volume should return False on failure."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = docker.inject_file_to_sandbox_volume("test.txt", "test content")

            assert result is False

    def test_inject_file_timeout(self):
        """inject_file_to_sandbox_volume should return False on timeout."""
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 30)):
            result = docker.inject_file_to_sandbox_volume("test.txt", "test content")

            assert result is False

    def test_inject_file_docker_not_found(self):
        """inject_file_to_sandbox_volume should return False when Docker not found."""
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = docker.inject_file_to_sandbox_volume("test.txt", "test content")

            assert result is False

    def test_inject_file_escapes_content(self):
        """inject_file_to_sandbox_volume should escape single quotes in content."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        content_with_quotes = "test's content with 'quotes'"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            docker.inject_file_to_sandbox_volume("test.txt", content_with_quotes)

            # Verify the shell command contains escaped quotes
            call_args = mock_run.call_args[0][0]
            shell_cmd = call_args[-1]  # Last arg is the shell command
            # Single quotes should be escaped as '\"'\"'
            assert "test'\"'\"'s" in shell_cmd


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for get_sandbox_settings
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetSandboxSettings:
    """Tests for get_sandbox_settings function."""

    def test_get_sandbox_settings_returns_dict(self):
        """get_sandbox_settings should return parsed JSON dict."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"key": "value", "nested": {"a": 1}}'

        with patch("subprocess.run", return_value=mock_result):
            result = docker.get_sandbox_settings()

            assert result == {"key": "value", "nested": {"a": 1}}

    def test_get_sandbox_settings_returns_none_on_failure(self):
        """get_sandbox_settings should return None when command fails."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = docker.get_sandbox_settings()

            assert result is None

    def test_get_sandbox_settings_returns_none_on_empty(self):
        """get_sandbox_settings should return None for empty output."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "   "

        with patch("subprocess.run", return_value=mock_result):
            result = docker.get_sandbox_settings()

            assert result is None

    def test_get_sandbox_settings_handles_timeout(self):
        """get_sandbox_settings should return None on timeout."""
        import subprocess

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 30)):
            result = docker.get_sandbox_settings()

            assert result is None

    def test_get_sandbox_settings_handles_docker_not_found(self):
        """get_sandbox_settings should return None when Docker not found."""
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            result = docker.get_sandbox_settings()

            assert result is None

    def test_get_sandbox_settings_handles_invalid_json(self):
        """get_sandbox_settings should return None for invalid JSON."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "{invalid json}"

        with patch("subprocess.run", return_value=mock_result):
            result = docker.get_sandbox_settings()

            # Should return None due to JSON parse error
            assert result is None
