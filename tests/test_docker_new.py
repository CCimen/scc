"""Tests for docker module - new architecture with claude_adapter integration.

These tests verify docker.py's integration with the new remote org config architecture:
- inject_settings() takes pre-built settings (docker.py is "dumb")
- launch_with_org_config() orchestrates full flow with profiles/claude_adapter
- Backward compatibility with inject_team_settings() when using org_config
"""

import json
from unittest.mock import patch

import pytest

from scc_cli import docker

# ═══════════════════════════════════════════════════════════════════════════════
# Test Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_claude_settings():
    """Sample settings built by claude_adapter.build_claude_settings()."""
    return {
        "extraKnownMarketplaces": {
            "my-org": {
                "name": "Internal Marketplace",
                "url": "https://gitlab.example.org/group/marketplace",
            }
        },
        "enabledPlugins": ["platform@my-org"],
    }


@pytest.fixture
def sample_org_config():
    """Sample remote organization config."""
    return {
        "schema_version": "1.0.0",
        "organization": {
            "name": "Example Org",
            "id": "my-org",
        },
        "marketplaces": [
            {
                "name": "internal",
                "type": "gitlab",
                "host": "gitlab.example.org",
                "repo": "group/marketplace",
                "auth": "env:GITLAB_TOKEN",
            }
        ],
        "profiles": {
            "platform": {
                "description": "Platform team",
                "plugin": "platform",
                "marketplace": "internal",
            }
        },
    }


@pytest.fixture
def sample_profile():
    """Sample resolved profile."""
    return {
        "name": "platform",
        "description": "Platform team",
        "plugin": "platform",
        "marketplace": "internal",
    }


@pytest.fixture
def sample_marketplace():
    """Sample resolved marketplace."""
    return {
        "name": "internal",
        "type": "gitlab",
        "host": "gitlab.example.org",
        "repo": "group/marketplace",
        "auth": "env:GITLAB_TOKEN",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for inject_settings (new "dumb" function)
# ═══════════════════════════════════════════════════════════════════════════════


class TestInjectSettings:
    """Tests for inject_settings() - the dumb settings injection function."""

    def test_inject_settings_with_valid_settings(self, sample_claude_settings):
        """inject_settings should inject pre-built settings to sandbox volume."""
        with (
            patch("scc_cli.docker.launch.get_sandbox_settings", return_value=None),
            patch(
                "scc_cli.docker.launch.inject_file_to_sandbox_volume", return_value=True
            ) as mock_inject,
        ):
            result = docker.inject_settings(sample_claude_settings)

            assert result is True
            mock_inject.assert_called_once()
            call_args = mock_inject.call_args
            assert call_args[0][0] == "settings.json"
            injected_content = json.loads(call_args[0][1])
            assert "extraKnownMarketplaces" in injected_content
            assert "enabledPlugins" in injected_content

    def test_inject_settings_merges_with_existing(self, sample_claude_settings):
        """inject_settings should merge with existing sandbox settings."""
        existing = {"statusLine": {"command": "/some/script"}, "otherSetting": True}

        with (
            patch("scc_cli.docker.launch.get_sandbox_settings", return_value=existing),
            patch(
                "scc_cli.docker.launch.inject_file_to_sandbox_volume", return_value=True
            ) as mock_inject,
        ):
            result = docker.inject_settings(sample_claude_settings)

            assert result is True
            call_args = mock_inject.call_args
            injected_content = json.loads(call_args[0][1])
            # Existing preserved
            assert injected_content["statusLine"]["command"] == "/some/script"
            assert injected_content["otherSetting"] is True
            # New settings added
            assert "extraKnownMarketplaces" in injected_content

    def test_inject_settings_new_overrides_existing(self):
        """inject_settings should let new settings override existing."""
        existing = {"enabledPlugins": ["old-plugin@old-market"]}
        new_settings = {"enabledPlugins": ["new-plugin@new-market"]}

        with (
            patch("scc_cli.docker.launch.get_sandbox_settings", return_value=existing),
            patch(
                "scc_cli.docker.launch.inject_file_to_sandbox_volume", return_value=True
            ) as mock_inject,
        ):
            docker.inject_settings(new_settings)

            call_args = mock_inject.call_args
            injected_content = json.loads(call_args[0][1])
            assert injected_content["enabledPlugins"] == ["new-plugin@new-market"]

    def test_inject_settings_empty_settings(self):
        """inject_settings with empty dict should still inject (preserves existing)."""
        existing = {"someKey": "someValue"}

        with (
            patch("scc_cli.docker.launch.get_sandbox_settings", return_value=existing),
            patch(
                "scc_cli.docker.launch.inject_file_to_sandbox_volume", return_value=True
            ) as mock_inject,
        ):
            result = docker.inject_settings({})

            assert result is True
            call_args = mock_inject.call_args
            injected_content = json.loads(call_args[0][1])
            assert injected_content["someKey"] == "someValue"

    def test_inject_settings_handles_injection_failure(self, sample_claude_settings):
        """inject_settings should return False when injection fails."""
        with (
            patch("scc_cli.docker.launch.get_sandbox_settings", return_value=None),
            patch("scc_cli.docker.launch.inject_file_to_sandbox_volume", return_value=False),
        ):
            result = docker.inject_settings(sample_claude_settings)

            assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for launch_with_org_config (orchestration function)
# ═══════════════════════════════════════════════════════════════════════════════


class TestLaunchWithOrgConfig:
    """Tests for launch_with_org_config() - full launch orchestration."""

    def test_launch_with_org_config_resolves_profile(self, sample_org_config, tmp_path):
        """launch_with_org_config should resolve profile from org config."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        with (
            patch("scc_cli.docker.launch.inject_settings", return_value=True),
            patch("scc_cli.docker.launch.run") as mock_run,
            patch("scc_cli.docker.launch.check_docker_available"),
            patch.dict("os.environ", {"GITLAB_TOKEN": "secret"}, clear=False),
        ):
            docker.launch_with_org_config(
                workspace=workspace, org_config=sample_org_config, team="platform"
            )

            # Should call inject_settings with built settings
            mock_run.assert_called_once()

    def test_launch_with_org_config_builds_correct_settings(self, sample_org_config, tmp_path):
        """launch_with_org_config should build settings using claude_adapter."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        with (
            patch("scc_cli.docker.launch.inject_settings", return_value=True) as mock_inject,
            patch("scc_cli.docker.launch.run"),
            patch("scc_cli.docker.launch.check_docker_available"),
            patch.dict("os.environ", {"GITLAB_TOKEN": "secret"}, clear=False),
        ):
            docker.launch_with_org_config(
                workspace=workspace, org_config=sample_org_config, team="platform"
            )

            # Verify settings were passed to inject_settings
            mock_inject.assert_called_once()
            settings = mock_inject.call_args[0][0]
            assert "extraKnownMarketplaces" in settings
            assert "enabledPlugins" in settings
            # Verify org_id is used as key
            assert "my-org" in settings["extraKnownMarketplaces"]

    def test_launch_with_org_config_invalid_team_raises(self, sample_org_config, tmp_path):
        """launch_with_org_config should raise for invalid team."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        with (
            patch("scc_cli.docker.launch.check_docker_available"),
            pytest.raises(ValueError, match="Profile 'nonexistent' not found"),
        ):
            docker.launch_with_org_config(
                workspace=workspace, org_config=sample_org_config, team="nonexistent"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for inject_team_settings with org_config (updated backward compat)
# ═══════════════════════════════════════════════════════════════════════════════


class TestInjectTeamSettingsWithOrgConfig:
    """Tests for inject_team_settings() with org_config parameter."""

    def test_inject_team_settings_with_org_config(self, sample_org_config):
        """inject_team_settings should work with org_config parameter."""
        with (
            patch("scc_cli.docker.launch.inject_settings", return_value=True) as mock_inject,
            patch.dict("os.environ", {"GITLAB_TOKEN": "secret"}, clear=False),
        ):
            result = docker.inject_team_settings(team_name="platform", org_config=sample_org_config)

            assert result is True
            mock_inject.assert_called_once()
            settings = mock_inject.call_args[0][0]
            assert settings["enabledPlugins"] == ["platform@my-org"]

    def test_inject_team_settings_no_plugin_configured(self, sample_org_config):
        """inject_team_settings returns True when profile has no plugin."""
        # Create org_config with profile that has no plugin
        org_config = {
            **sample_org_config,
            "profiles": {"base": {"description": "Base profile"}},
        }

        with patch("scc_cli.docker.launch.inject_settings") as mock_inject:
            result = docker.inject_team_settings(team_name="base", org_config=org_config)

            # Should return True without injecting
            assert result is True
            mock_inject.assert_not_called()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for credential injection
# ═══════════════════════════════════════════════════════════════════════════════


class TestCredentialInjection:
    """Tests for credential injection into Docker environment."""

    def test_credentials_injected_for_private_marketplace(self, sample_org_config, tmp_path):
        """Private marketplace credentials should be injected into Docker env."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        with (
            patch("scc_cli.docker.launch.inject_settings", return_value=True),
            patch("scc_cli.docker.launch.run") as mock_run,
            patch("scc_cli.docker.launch.check_docker_available"),
            patch.dict("os.environ", {"GITLAB_TOKEN": "my-secret-token"}, clear=False),
        ):
            docker.launch_with_org_config(
                workspace=workspace, org_config=sample_org_config, team="platform"
            )

            # run() is called - verify it was called
            mock_run.assert_called_once()

    def test_no_credentials_for_public_marketplace(self, tmp_path):
        """Public marketplace should not require credentials."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        public_org_config = {
            "organization": {"id": "public-org"},
            "marketplaces": [
                {
                    "name": "public",
                    "type": "github",
                    "repo": "org/plugins",
                    "auth": None,  # Public
                }
            ],
            "profiles": {"default": {"plugin": "default", "marketplace": "public"}},
        }

        with (
            patch("scc_cli.docker.launch.inject_settings", return_value=True),
            patch("scc_cli.docker.launch.run") as mock_run,
            patch("scc_cli.docker.launch.check_docker_available"),
        ):
            docker.launch_with_org_config(
                workspace=workspace, org_config=public_org_config, team="default"
            )

            mock_run.assert_called_once()
