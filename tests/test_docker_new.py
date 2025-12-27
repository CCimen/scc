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
