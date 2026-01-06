"""Tests for plugin isolation via global settings reset.

Verifies that reset_global_settings() properly resets the Docker sandbox
volume settings to prevent plugin mixing across teams.
"""

from unittest.mock import patch

from scc_cli import docker


class TestResetGlobalSettings:
    """Tests for reset_global_settings() function."""

    def test_reset_global_settings_writes_empty_json(self):
        """reset_global_settings should write empty JSON to settings.json."""
        with patch(
            "scc_cli.docker.launch.inject_file_to_sandbox_volume", return_value=True
        ) as mock_inject:
            result = docker.reset_global_settings()

            assert result is True
            mock_inject.assert_called_once_with("settings.json", "{}")

    def test_reset_global_settings_returns_false_on_failure(self):
        """reset_global_settings should return False when injection fails."""
        with patch("scc_cli.docker.launch.inject_file_to_sandbox_volume", return_value=False):
            result = docker.reset_global_settings()

            assert result is False

    def test_reset_global_settings_called_in_run_sandbox(self):
        """run_sandbox should call reset_global_settings before container exec."""
        with (
            patch("scc_cli.docker.launch.reset_global_settings") as mock_reset,
            patch(
                "scc_cli.docker.launch.get_effective_safety_net_policy",
                return_value={"action": "block"},
            ),
            patch(
                "scc_cli.docker.launch.write_safety_net_policy_to_host",
                return_value="/tmp/policy.json",
            ),
            patch("scc_cli.docker.launch.build_command", return_value=["docker", "run"]),
            patch("scc_cli.docker.launch.subprocess.run") as mock_subprocess,
            patch("os.name", "nt"),  # Skip credential flow on Windows path
        ):
            mock_subprocess.return_value.returncode = 0

            docker.run_sandbox()

            # Verify reset was called
            mock_reset.assert_called_once()


class TestPluginIsolationScenario:
    """Integration-like tests for plugin isolation across teams."""

    def test_settings_reset_clears_old_plugins(self):
        """Existing plugins in volume should be cleared after reset."""
        # This simulates the scenario where team A's plugins were in the volume
        existing_settings = {
            "enabledPlugins": ["old-plugin@team-a-marketplace"],
            "extraKnownMarketplaces": {"team-a": {"name": "Team A Market"}},
        }

        # After reset, settings should be empty
        with (
            patch(
                "scc_cli.docker.launch.get_sandbox_settings",
                return_value=existing_settings,
            ),
            patch(
                "scc_cli.docker.launch.inject_file_to_sandbox_volume", return_value=True
            ) as mock_inject,
        ):
            result = docker.reset_global_settings()

            # Should inject empty JSON, ignoring existing settings
            assert result is True
            mock_inject.assert_called_once_with("settings.json", "{}")

    def test_inject_settings_merges_after_reset(self):
        """inject_settings should work normally after reset (no old plugins)."""
        new_team_settings = {
            "enabledPlugins": ["new-plugin@team-b-marketplace"],
            "extraKnownMarketplaces": {"team-b": {"name": "Team B Market"}},
        }

        # After reset, volume settings are empty
        with (
            patch("scc_cli.docker.launch.get_sandbox_settings", return_value={}),
            patch(
                "scc_cli.docker.launch.inject_file_to_sandbox_volume", return_value=True
            ) as mock_inject,
        ):
            result = docker.inject_settings(new_team_settings)

            assert result is True
            # Should inject only the new team's settings (no old remnants)
            call_args = mock_inject.call_args
            import json

            injected = json.loads(call_args[0][1])
            assert injected["enabledPlugins"] == ["new-plugin@team-b-marketplace"]
            assert "team-a" not in injected.get("extraKnownMarketplaces", {})
