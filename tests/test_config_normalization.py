"""Tests for config normalization.

Verify that raw dict configs are correctly normalized to typed models.
"""

from __future__ import annotations

import pytest

from scc_cli.adapters.config_normalizer import (
    normalize_org_config,
    normalize_project_config,
    normalize_user_config,
)


class TestNormalizeUserConfig:
    """Test user config normalization."""

    def test_empty_config_returns_defaults(self) -> None:
        """Empty dict should return default values."""
        result = normalize_user_config({})

        assert result.selected_profile is None
        assert result.standalone is False
        assert result.organization_source is None
        assert result.workspace_team_map == {}
        assert result.onboarding_seen is False

    def test_selected_profile_preserved(self) -> None:
        """Selected profile should be preserved."""
        result = normalize_user_config({"selected_profile": "platform"})

        assert result.selected_profile == "platform"

    def test_standalone_mode_normalized(self) -> None:
        """Standalone flag should be normalized to bool."""
        result = normalize_user_config({"standalone": True})

        assert result.standalone is True

    def test_organization_source_normalized(self) -> None:
        """Organization source should be normalized."""
        raw = {
            "organization_source": {
                "url": "https://example.com/org.json",
                "auth": "token123",
                "auth_header": "X-Custom-Auth",
            }
        }
        result = normalize_user_config(raw)

        assert result.organization_source is not None
        assert result.organization_source.url == "https://example.com/org.json"
        assert result.organization_source.auth == "token123"
        assert result.organization_source.auth_header == "X-Custom-Auth"

    def test_workspace_team_map_preserved(self) -> None:
        """Workspace team map should be preserved."""
        raw = {"workspace_team_map": {"/path/to/project": "backend"}}
        result = normalize_user_config(raw)

        assert result.workspace_team_map == {"/path/to/project": "backend"}

    def test_invalid_workspace_map_becomes_empty(self) -> None:
        """Invalid workspace map type should become empty dict."""
        result = normalize_user_config({"workspace_team_map": "invalid"})

        assert result.workspace_team_map == {}


class TestNormalizeOrgConfig:
    """Test organization config normalization."""

    def test_minimal_config_returns_defaults(self) -> None:
        """Minimal config should return default values for optional fields."""
        result = normalize_org_config({"organization": {"name": "TestOrg"}})

        assert result.organization.name == "TestOrg"
        assert result.security.blocked_plugins == ()
        assert result.defaults.enabled_plugins == ()
        assert result.profiles == {}
        assert result.marketplaces == {}

    def test_security_config_normalized(self) -> None:
        """Security config should be normalized."""
        raw = {
            "organization": {"name": "TestOrg"},
            "security": {
                "blocked_plugins": ["malicious-*", "bad-plugin"],
                "blocked_mcp_servers": ["evil.com"],
                "allow_stdio_mcp": True,
                "allowed_stdio_prefixes": ["/usr/bin", "/opt"],
            },
        }
        result = normalize_org_config(raw)

        assert result.security.blocked_plugins == ("malicious-*", "bad-plugin")
        assert result.security.blocked_mcp_servers == ("evil.com",)
        assert result.security.allow_stdio_mcp is True
        assert result.security.allowed_stdio_prefixes == ("/usr/bin", "/opt")

    def test_defaults_config_normalized(self) -> None:
        """Defaults config should be normalized."""
        raw = {
            "organization": {"name": "TestOrg"},
            "defaults": {
                "enabled_plugins": ["plugin-a", "plugin-b"],
                "disabled_plugins": ["deprecated-plugin"],
                "allowed_plugins": ["plugin-*"],
                "network_policy": "restrictive",
                "session": {"timeout_hours": 8, "auto_resume": True},
            },
        }
        result = normalize_org_config(raw)

        assert result.defaults.enabled_plugins == ("plugin-a", "plugin-b")
        assert result.defaults.disabled_plugins == ("deprecated-plugin",)
        assert result.defaults.allowed_plugins == ("plugin-*",)
        assert result.defaults.network_policy == "restrictive"
        assert result.defaults.session.timeout_hours == 8
        assert result.defaults.session.auto_resume is True

    def test_allowed_plugins_none_vs_empty(self) -> None:
        """None allowed_plugins (no allowlist) differs from empty (deny all)."""
        no_allowlist = normalize_org_config({"organization": {"name": "Test"}})
        empty_allowlist = normalize_org_config(
            {
                "organization": {"name": "Test"},
                "defaults": {"allowed_plugins": []},
            }
        )

        assert no_allowlist.defaults.allowed_plugins is None
        assert empty_allowlist.defaults.allowed_plugins == ()

    def test_delegation_config_normalized(self) -> None:
        """Delegation config should be normalized."""
        raw = {
            "organization": {"name": "TestOrg"},
            "delegation": {
                "teams": {
                    "allow_additional_plugins": ["platform-*", "backend-*"],
                    "allow_additional_mcp_servers": ["platform-*"],
                },
                "projects": {"inherit_team_delegation": True},
            },
        }
        result = normalize_org_config(raw)

        assert result.delegation.teams.allow_additional_plugins == ("platform-*", "backend-*")
        assert result.delegation.teams.allow_additional_mcp_servers == ("platform-*",)
        assert result.delegation.projects.inherit_team_delegation is True

    def test_profiles_normalized(self) -> None:
        """Team profiles should be normalized."""
        raw = {
            "organization": {"name": "TestOrg"},
            "profiles": {
                "platform": {
                    "description": "Platform team",
                    "plugin": "platform-plugin",
                    "marketplace": "internal",
                    "additional_plugins": ["extra-plugin"],
                    "additional_mcp_servers": [
                        {"name": "server1", "type": "sse", "url": "https://example.com"}
                    ],
                    "session": {"timeout_hours": 12},
                    "delegation": {"allow_project_overrides": True},
                }
            },
        }
        result = normalize_org_config(raw)

        assert "platform" in result.profiles
        profile = result.profiles["platform"]
        assert profile.name == "platform"
        assert profile.description == "Platform team"
        assert profile.plugin == "platform-plugin"
        assert profile.marketplace == "internal"
        assert profile.additional_plugins == ("extra-plugin",)
        assert len(profile.additional_mcp_servers) == 1
        assert profile.additional_mcp_servers[0].name == "server1"
        assert profile.session.timeout_hours == 12
        assert profile.delegation.allow_project_overrides is True

    def test_marketplaces_normalized(self) -> None:
        """Marketplaces should be normalized."""
        raw = {
            "organization": {"name": "TestOrg"},
            "marketplaces": {
                "internal": {
                    "source": "github",
                    "owner": "myorg",
                    "repo": "plugins",
                    "branch": "main",
                }
            },
        }
        result = normalize_org_config(raw)

        assert "internal" in result.marketplaces
        marketplace = result.marketplaces["internal"]
        assert marketplace.name == "internal"
        assert marketplace.source == "github"
        assert marketplace.owner == "myorg"
        assert marketplace.repo == "plugins"
        assert marketplace.branch == "main"

    def test_get_profile_returns_profile(self) -> None:
        """get_profile should return the requested profile."""
        raw = {
            "organization": {"name": "TestOrg"},
            "profiles": {"platform": {"description": "Platform"}},
        }
        result = normalize_org_config(raw)

        profile = result.get_profile("platform")
        assert profile is not None
        assert profile.name == "platform"

    def test_get_profile_returns_none_for_missing(self) -> None:
        """get_profile should return None for missing profile."""
        result = normalize_org_config({"organization": {"name": "TestOrg"}})

        assert result.get_profile("nonexistent") is None

    def test_list_profile_names(self) -> None:
        """list_profile_names should return all profile names."""
        raw = {
            "organization": {"name": "TestOrg"},
            "profiles": {"platform": {}, "backend": {}, "frontend": {}},
        }
        result = normalize_org_config(raw)

        names = result.list_profile_names()
        assert set(names) == {"platform", "backend", "frontend"}


class TestNormalizeProjectConfig:
    """Test project config normalization."""

    def test_none_input_returns_none(self) -> None:
        """None input should return None."""
        result = normalize_project_config(None)

        assert result is None

    def test_empty_config_returns_defaults(self) -> None:
        """Empty dict should return default values."""
        result = normalize_project_config({})

        assert result is not None
        assert result.additional_plugins == ()
        assert result.additional_mcp_servers == ()
        assert result.session.timeout_hours is None

    def test_plugins_normalized(self) -> None:
        """Additional plugins should be normalized."""
        raw = {"additional_plugins": ["local-plugin"]}
        result = normalize_project_config(raw)

        assert result is not None
        assert result.additional_plugins == ("local-plugin",)

    def test_mcp_servers_normalized(self) -> None:
        """MCP servers should be normalized."""
        raw = {
            "additional_mcp_servers": [
                {"name": "local-mcp", "type": "stdio", "command": "/usr/bin/tool"}
            ]
        }
        result = normalize_project_config(raw)

        assert result is not None
        assert len(result.additional_mcp_servers) == 1
        server = result.additional_mcp_servers[0]
        assert server.name == "local-mcp"
        assert server.type == "stdio"
        assert server.command == "/usr/bin/tool"

    def test_session_normalized(self) -> None:
        """Session config should be normalized."""
        raw = {"session": {"timeout_hours": 16}}
        result = normalize_project_config(raw)

        assert result is not None
        assert result.session.timeout_hours == 16


class TestConfigModelImmutability:
    """Test that config models are immutable (frozen dataclasses)."""

    def test_user_config_is_frozen(self) -> None:
        """NormalizedUserConfig should be immutable."""
        config = normalize_user_config({"selected_profile": "test"})

        with pytest.raises(AttributeError):
            config.selected_profile = "new"  # type: ignore[misc]

    def test_org_config_is_frozen(self) -> None:
        """NormalizedOrgConfig should be immutable."""
        config = normalize_org_config({"organization": {"name": "Test"}})

        with pytest.raises(AttributeError):
            config.organization = None  # type: ignore[misc]

    def test_team_config_is_frozen(self) -> None:
        """NormalizedTeamConfig should be immutable."""
        raw = {"organization": {"name": "Test"}, "profiles": {"team": {}}}
        config = normalize_org_config(raw)
        profile = config.profiles["team"]

        with pytest.raises(AttributeError):
            profile.name = "new"  # type: ignore[misc]
