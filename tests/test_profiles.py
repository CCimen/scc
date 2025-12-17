"""Tests for profiles module (renamed from teams.py).

Tests profile resolution and marketplace URL logic with HTTPS-only enforcement.
"""

import pytest

from scc_cli import profiles

# ═══════════════════════════════════════════════════════════════════════════════
# Test Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_org_config():
    """Create a sample org config with multiple marketplaces and profiles."""
    return {
        "organization": {
            "name": "Example Organization",
            "id": "example-org",
        },
        "marketplaces": [
            {
                "name": "internal",
                "type": "gitlab",
                "host": "gitlab.example.org",
                "repo": "group/claude-marketplace",
                "ref": "main",
                "auth": "env:GITLAB_TOKEN",
            },
            {
                "name": "public",
                "type": "github",
                "repo": "my-org/public-plugins",
                "ref": "main",
                "auth": None,
            },
            {
                "name": "custom",
                "type": "https",
                "url": "https://plugins.example.org/marketplace",
                "auth": "env:CUSTOM_TOKEN",
            },
        ],
        "profiles": {
            "platform": {
                "description": "Platform team (Python, FastAPI)",
                "plugin": "platform",
                "marketplace": "internal",
            },
            "api": {
                "description": "API team (Java, Spring Boot)",
                "plugin": "api",
                "marketplace": "public",
            },
            "custom-team": {
                "description": "Custom team",
                "plugin": "custom-plugin",
                "marketplace": "custom",
            },
        },
    }


@pytest.fixture
def legacy_config():
    """Legacy config format (single marketplace in 'marketplace' key)."""
    return {
        "marketplace": {
            "name": "sundsvall",
            "repo": "sundsvall/claude-plugins-marketplace",
        },
        "profiles": {
            "base": {
                "description": "Default profile - no team plugin",
                "plugin": None,
            },
            "ai-teamet": {
                "description": "AI platform development",
                "plugin": "ai-teamet",
            },
        },
    }


@pytest.fixture
def empty_config():
    """Create an empty config."""
    return {}


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for list_profiles
# ═══════════════════════════════════════════════════════════════════════════════


class TestListProfiles:
    """Tests for list_profiles function."""

    def test_list_profiles_returns_all_profiles(self, sample_org_config):
        """list_profiles should return all profiles from org config."""
        result = profiles.list_profiles(sample_org_config)
        assert len(result) == 3
        profile_names = [p["name"] for p in result]
        assert "platform" in profile_names
        assert "api" in profile_names
        assert "custom-team" in profile_names

    def test_list_profiles_includes_all_fields(self, sample_org_config):
        """list_profiles should include all profile fields."""
        result = profiles.list_profiles(sample_org_config)
        platform = next(p for p in result if p["name"] == "platform")
        assert platform["description"] == "Platform team (Python, FastAPI)"
        assert platform["plugin"] == "platform"
        assert platform["marketplace"] == "internal"

    def test_list_profiles_empty_config(self, empty_config):
        """list_profiles should return empty list for empty config."""
        result = profiles.list_profiles(empty_config)
        assert result == []

    def test_list_profiles_no_profiles_key(self):
        """list_profiles should handle config without profiles key."""
        result = profiles.list_profiles({"other": "data"})
        assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for resolve_profile
# ═══════════════════════════════════════════════════════════════════════════════


class TestResolveProfile:
    """Tests for resolve_profile function."""

    def test_resolve_profile_existing(self, sample_org_config):
        """resolve_profile should return full profile for existing name."""
        result = profiles.resolve_profile(sample_org_config, "platform")
        assert result["name"] == "platform"
        assert result["description"] == "Platform team (Python, FastAPI)"
        assert result["plugin"] == "platform"
        assert result["marketplace"] == "internal"

    def test_resolve_profile_nonexistent_raises(self, sample_org_config):
        """resolve_profile should raise ValueError for nonexistent profile."""
        with pytest.raises(ValueError, match="Profile 'nonexistent' not found"):
            profiles.resolve_profile(sample_org_config, "nonexistent")

    def test_resolve_profile_error_shows_available(self, sample_org_config):
        """resolve_profile error should list available profiles."""
        with pytest.raises(ValueError, match="Available:"):
            profiles.resolve_profile(sample_org_config, "nonexistent")


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for resolve_marketplace
# ═══════════════════════════════════════════════════════════════════════════════


class TestResolveMarketplace:
    """Tests for resolve_marketplace function."""

    def test_resolve_marketplace_existing(self, sample_org_config):
        """resolve_marketplace should return marketplace for profile."""
        profile = profiles.resolve_profile(sample_org_config, "platform")
        marketplace = profiles.resolve_marketplace(sample_org_config, profile)
        assert marketplace["name"] == "internal"
        assert marketplace["type"] == "gitlab"
        assert marketplace["host"] == "gitlab.example.org"

    def test_resolve_marketplace_nonexistent_raises(self, sample_org_config):
        """resolve_marketplace should raise ValueError for nonexistent marketplace."""
        bad_profile = {"name": "test", "marketplace": "nonexistent"}
        with pytest.raises(ValueError, match="Marketplace 'nonexistent' not found"):
            profiles.resolve_marketplace(sample_org_config, bad_profile)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for get_marketplace_url - CRITICAL HTTPS-only enforcement
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetMarketplaceUrl:
    """Tests for get_marketplace_url function - HTTPS-only enforcement."""

    def test_github_default_host(self):
        """GitHub marketplace should use github.com by default."""
        marketplace = {"type": "github", "repo": "my-org/plugins"}
        assert profiles.get_marketplace_url(marketplace) == "https://github.com/my-org/plugins"

    def test_gitlab_default_host(self):
        """GitLab marketplace should use gitlab.com by default."""
        marketplace = {"type": "gitlab", "repo": "group/plugins"}
        assert profiles.get_marketplace_url(marketplace) == "https://gitlab.com/group/plugins"

    def test_gitlab_custom_host(self):
        """GitLab with custom host should use provided host."""
        marketplace = {"type": "gitlab", "host": "gitlab.example.org", "repo": "group/repo"}
        assert profiles.get_marketplace_url(marketplace) == "https://gitlab.example.org/group/repo"

    def test_github_enterprise_custom_host(self):
        """GitHub Enterprise with custom host should work."""
        marketplace = {"type": "github", "host": "github.corp.example.com", "repo": "org/plugins"}
        assert (
            profiles.get_marketplace_url(marketplace)
            == "https://github.corp.example.com/org/plugins"
        )

    def test_custom_host_with_port(self):
        """Custom host with port should be preserved."""
        marketplace = {"type": "gitlab", "host": "gitlab.example.org:8443", "repo": "group/repo"}
        assert (
            profiles.get_marketplace_url(marketplace)
            == "https://gitlab.example.org:8443/group/repo"
        )

    def test_https_url_direct(self):
        """Direct HTTPS URL should be used as-is (normalized)."""
        marketplace = {"type": "https", "url": "https://plugins.example.org/marketplace"}
        assert (
            profiles.get_marketplace_url(marketplace) == "https://plugins.example.org/marketplace"
        )

    def test_https_url_with_trailing_slash(self):
        """Trailing slash should be stripped."""
        marketplace = {"type": "https", "url": "https://plugins.example.org/marketplace/"}
        assert (
            profiles.get_marketplace_url(marketplace) == "https://plugins.example.org/marketplace"
        )

    def test_repo_path_strips_leading_slash(self):
        """Leading slash in repo path should be stripped."""
        marketplace = {"type": "github", "repo": "/my-org/plugins"}
        assert profiles.get_marketplace_url(marketplace) == "https://github.com/my-org/plugins"

    def test_repo_path_strips_git_suffix(self):
        """Repo path ending with .git should be stripped."""
        marketplace = {"type": "github", "repo": "my-org/plugins.git"}
        assert profiles.get_marketplace_url(marketplace) == "https://github.com/my-org/plugins"

    def test_repo_path_with_subgroups(self):
        """GitLab subgroups should be preserved."""
        marketplace = {
            "type": "gitlab",
            "host": "gitlab.example.org",
            "repo": "group/subgroup/repo",
        }
        assert (
            profiles.get_marketplace_url(marketplace)
            == "https://gitlab.example.org/group/subgroup/repo"
        )

    # --- SECURITY: HTTPS-only enforcement ---

    def test_rejects_ssh_url(self):
        """SSH URLs should be rejected."""
        marketplace = {"type": "github", "url": "git@github.com:org/repo.git"}
        with pytest.raises(ValueError, match="SSH URL not supported"):
            profiles.get_marketplace_url(marketplace)

    def test_rejects_ssh_protocol_url(self):
        """ssh:// protocol URLs should be rejected."""
        marketplace = {"type": "github", "url": "ssh://git@github.com/org/repo.git"}
        with pytest.raises(ValueError, match="SSH URL not supported"):
            profiles.get_marketplace_url(marketplace)

    def test_rejects_http_url(self):
        """HTTP URLs should be rejected (HTTPS required)."""
        marketplace = {"type": "https", "url": "http://plugins.example.org/marketplace"}
        with pytest.raises(ValueError, match="HTTP not allowed"):
            profiles.get_marketplace_url(marketplace)

    def test_rejects_unsupported_scheme(self):
        """Unsupported URL schemes should be rejected."""
        marketplace = {"type": "https", "url": "ftp://plugins.example.org/marketplace"}
        with pytest.raises(ValueError, match="Unsupported URL scheme"):
            profiles.get_marketplace_url(marketplace)

    def test_rejects_host_with_path(self):
        """Host containing path components should be rejected."""
        marketplace = {"type": "gitlab", "host": "gitlab.example.org/extra", "repo": "group/repo"}
        with pytest.raises(ValueError, match="'host' must not include path"):
            profiles.get_marketplace_url(marketplace)

    def test_requires_url_or_host_for_unknown_type(self):
        """Unknown type without url or host should raise error."""
        marketplace = {"type": "bitbucket", "repo": "org/repo"}
        with pytest.raises(ValueError, match="requires 'url' or 'host'"):
            profiles.get_marketplace_url(marketplace)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for backward compatibility with legacy config format
# ═══════════════════════════════════════════════════════════════════════════════


class TestLegacyConfigCompatibility:
    """Tests for backward compatibility with legacy single-marketplace config."""

    def test_list_teams_legacy(self, legacy_config):
        """list_teams should work with legacy config."""
        result = profiles.list_teams(legacy_config)
        assert len(result) == 2
        team_names = [t["name"] for t in result]
        assert "base" in team_names
        assert "ai-teamet" in team_names

    def test_get_team_details_legacy(self, legacy_config):
        """get_team_details should work with legacy config."""
        result = profiles.get_team_details("ai-teamet", legacy_config)
        assert result is not None
        assert result["name"] == "ai-teamet"
        assert result["plugin"] == "ai-teamet"
        assert result["marketplace"] == "sundsvall"

    def test_get_team_sandbox_settings_legacy(self, legacy_config):
        """get_team_sandbox_settings should work with legacy config."""
        result = profiles.get_team_sandbox_settings("ai-teamet", legacy_config)
        assert "extraKnownMarketplaces" in result
        assert "enabledPlugins" in result
        assert result["enabledPlugins"] == ["ai-teamet@sundsvall"]

    def test_get_team_plugin_id_legacy(self, legacy_config):
        """get_team_plugin_id should work with legacy config."""
        result = profiles.get_team_plugin_id("ai-teamet", legacy_config)
        assert result == "ai-teamet@sundsvall"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateProfile:
    """Tests for validate_team_profile function (backward compatible name)."""

    def test_validate_valid_profile(self, sample_org_config):
        """validate_team_profile should return valid=True for valid profile."""
        result = profiles.validate_team_profile("platform", sample_org_config)
        assert result["valid"] is True
        assert result["team"] == "platform"
        assert result["plugin"] == "platform"
        assert result["errors"] == []

    def test_validate_nonexistent_profile(self, sample_org_config):
        """validate_team_profile should return valid=False for nonexistent profile."""
        result = profiles.validate_team_profile("nonexistent", sample_org_config)
        assert result["valid"] is False
        assert "not found" in result["errors"][0]
