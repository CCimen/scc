"""Tests for docker module - team settings injection."""

import json
from unittest.mock import MagicMock, patch

import pytest

from scc_cli import docker

# ═══════════════════════════════════════════════════════════════════════════════
# Test Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_team_settings():
    """Sample team settings returned by teams.get_team_sandbox_settings."""
    return {
        "extraKnownMarketplaces": {
            "sundsvall": {
                "source": {
                    "source": "github",
                    "repo": "sundsvall/claude-plugins-marketplace",
                }
            }
        },
        "enabledPlugins": ["ai-teamet@sundsvall"],
    }


@pytest.fixture
def mock_existing_settings():
    """Sample existing settings in the Docker volume."""
    return {
        "statusLine": {
            "command": "/mnt/claude-data/scc-statusline.sh",
        },
        "someOtherSetting": True,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for inject_team_settings
# ═══════════════════════════════════════════════════════════════════════════════


class TestInjectTeamSettings:
    """Tests for inject_team_settings function."""

    def test_inject_team_settings_with_plugin(self, mock_team_settings):
        """inject_team_settings should inject team config when plugin exists."""
        with (
            patch("scc_cli.docker.launch.get_sandbox_settings", return_value=None),
            patch(
                "scc_cli.docker.launch.inject_file_to_sandbox_volume", return_value=True
            ) as mock_inject,
            patch("scc_cli.teams.get_team_sandbox_settings", return_value=mock_team_settings),
        ):
            result = docker.inject_team_settings("ai-teamet")

            assert result is True
            mock_inject.assert_called_once()
            # Verify the content is valid JSON with team settings
            call_args = mock_inject.call_args
            assert call_args[0][0] == "settings.json"
            injected_content = json.loads(call_args[0][1])
            assert "extraKnownMarketplaces" in injected_content
            assert "enabledPlugins" in injected_content

    def test_inject_team_settings_no_plugin(self):
        """inject_team_settings should return True when team has no plugin."""
        with patch("scc_cli.teams.get_team_sandbox_settings", return_value={}):
            result = docker.inject_team_settings("base")

            # Should return True (success) without injecting anything
            assert result is True

    def test_inject_team_settings_merges_with_existing(
        self, mock_team_settings, mock_existing_settings
    ):
        """inject_team_settings should merge with existing settings."""
        with (
            patch(
                "scc_cli.docker.launch.get_sandbox_settings", return_value=mock_existing_settings
            ),
            patch(
                "scc_cli.docker.launch.inject_file_to_sandbox_volume", return_value=True
            ) as mock_inject,
            patch("scc_cli.teams.get_team_sandbox_settings", return_value=mock_team_settings),
        ):
            result = docker.inject_team_settings("ai-teamet")

            assert result is True
            # Verify merged content contains both existing and team settings
            call_args = mock_inject.call_args
            injected_content = json.loads(call_args[0][1])
            # Existing settings preserved
            assert "statusLine" in injected_content
            assert "someOtherSetting" in injected_content
            # Team settings added
            assert "extraKnownMarketplaces" in injected_content
            assert "enabledPlugins" in injected_content

    def test_inject_team_settings_team_overrides_existing(self):
        """inject_team_settings should let team settings override existing."""
        existing = {"enabledPlugins": ["old-plugin@old-market"]}
        team = {"enabledPlugins": ["new-plugin@new-market"]}

        with (
            patch("scc_cli.docker.launch.get_sandbox_settings", return_value=existing),
            patch(
                "scc_cli.docker.launch.inject_file_to_sandbox_volume", return_value=True
            ) as mock_inject,
            patch("scc_cli.teams.get_team_sandbox_settings", return_value=team),
        ):
            docker.inject_team_settings("test-team")

            call_args = mock_inject.call_args
            injected_content = json.loads(call_args[0][1])
            # Team settings should override existing
            assert injected_content["enabledPlugins"] == ["new-plugin@new-market"]

    def test_inject_team_settings_handles_injection_failure(self, mock_team_settings):
        """inject_team_settings should return False when injection fails."""
        with (
            patch("scc_cli.docker.launch.get_sandbox_settings", return_value=None),
            patch("scc_cli.docker.launch.inject_file_to_sandbox_volume", return_value=False),
            patch("scc_cli.teams.get_team_sandbox_settings", return_value=mock_team_settings),
        ):
            result = docker.inject_team_settings("ai-teamet")

            assert result is False

    def test_inject_team_settings_nonexistent_team(self):
        """inject_team_settings should handle nonexistent team gracefully."""
        with patch("scc_cli.teams.get_team_sandbox_settings", return_value={}):
            # Should return True (no plugin to inject is not an error)
            result = docker.inject_team_settings("nonexistent-team")
            assert result is True


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


# ═══════════════════════════════════════════════════════════════════════════════
# Integration test scenarios
# ═══════════════════════════════════════════════════════════════════════════════


class TestTeamSettingsIntegration:
    """Integration tests for team settings workflow."""

    def test_full_team_injection_workflow(self, temp_config_dir):
        """Test complete workflow from config to injection."""
        from scc_cli import config

        # Setup: Save config with team profile
        test_config = {
            "marketplace": {
                "name": "sundsvall",
                "repo": "sundsvall/claude-plugins-marketplace",
            },
            "profiles": {
                "ai-teamet": {
                    "description": "AI platform development",
                    "plugin": "ai-teamet",
                },
            },
        }
        config.save_config(test_config)

        # Mock Docker operations
        with (
            patch("scc_cli.docker.launch.get_sandbox_settings", return_value=None),
            patch(
                "scc_cli.docker.launch.inject_file_to_sandbox_volume", return_value=True
            ) as mock_inject,
        ):
            result = docker.inject_team_settings("ai-teamet")

            assert result is True
            # Verify correct settings were injected
            call_args = mock_inject.call_args
            injected_content = json.loads(call_args[0][1])
            assert injected_content["enabledPlugins"] == ["ai-teamet@sundsvall"]
            assert "sundsvall" in injected_content["extraKnownMarketplaces"]

    def test_base_profile_no_injection(self, temp_config_dir):
        """Test that base profile doesn't inject plugin settings."""
        from scc_cli import config

        test_config = {
            "marketplace": {
                "name": "sundsvall",
                "repo": "sundsvall/claude-plugins-marketplace",
            },
            "profiles": {
                "base": {
                    "description": "Default profile",
                    "plugin": None,
                },
            },
        }
        config.save_config(test_config)

        with patch("scc_cli.docker.launch.inject_file_to_sandbox_volume") as mock_inject:
            result = docker.inject_team_settings("base")

            assert result is True
            # Should not attempt to inject anything
            mock_inject.assert_not_called()
