"""Tests for marketplace/resolve.py - effective config resolution.

This module tests:
- ConfigFetchError exception with remediation hints
- _get_fetch_remediation() helper function
- EffectiveConfig dataclass and properties
- resolve_effective_config() orchestrator for inline and federated teams
- _validate_defaults_dont_need_org_marketplaces() validation
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from scc_cli.marketplace.compute import TeamNotFoundError
from scc_cli.marketplace.resolve import (
    ConfigFetchError,
    EffectiveConfig,
    _get_fetch_remediation,
    _validate_defaults_dont_need_org_marketplaces,
    resolve_effective_config,
)
from scc_cli.marketplace.schema import (
    ConfigSourceGit,
    ConfigSourceGitHub,
    ConfigSourceURL,
    DefaultsConfig,
    MarketplaceSourceGitHub,
    OrganizationConfig,
    TeamProfile,
    TrustGrant,
)
from scc_cli.marketplace.trust import TrustViolationError

# ─────────────────────────────────────────────────────────────────────────────
# ConfigFetchError Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestConfigFetchError:
    """Tests for ConfigFetchError exception class."""

    def test_has_team_id(self) -> None:
        """Error stores team_id."""
        error = ConfigFetchError(
            team_id="backend",
            source_type="github",
            source_url="github.com/org/repo",
            error="Not found",
        )
        assert error.team_id == "backend"

    def test_has_source_type(self) -> None:
        """Error stores source_type."""
        error = ConfigFetchError(
            team_id="backend",
            source_type="url",
            source_url="https://example.com/config.json",
            error="Connection timeout",
        )
        assert error.source_type == "url"

    def test_has_source_url(self) -> None:
        """Error stores source_url."""
        error = ConfigFetchError(
            team_id="backend",
            source_type="git",
            source_url="git@github.com:org/repo.git",
            error="Clone failed",
        )
        assert error.source_url == "git@github.com:org/repo.git"

    def test_message_includes_team_and_source(self) -> None:
        """Error message includes team_id, source_type, and source_url."""
        error = ConfigFetchError(
            team_id="frontend",
            source_type="github",
            source_url="github.com/org/plugins",
            error="Repository not found",
        )
        message = str(error)
        assert "frontend" in message
        assert "github" in message
        assert "github.com/org/plugins" in message
        assert "Repository not found" in message

    def test_message_includes_remediation_hint(self) -> None:
        """Error message includes remediation hint when applicable."""
        error = ConfigFetchError(
            team_id="backend",
            source_type="url",
            source_url="https://example.com/config.json",
            error="HTTP 404 Not Found",
        )
        message = str(error)
        # Should include hint about verifying URL
        assert "Verify" in message or "URL" in message


class TestGetFetchRemediation:
    """Tests for _get_fetch_remediation() helper function."""

    def test_network_error_returns_update_hint(self) -> None:
        """Network errors suggest running org update."""
        hint = _get_fetch_remediation("github", "Network connection error")
        assert "scc org update" in hint
        assert "connected" in hint

    def test_connection_error_returns_update_hint(self) -> None:
        """Connection errors suggest running org update."""
        hint = _get_fetch_remediation("url", "Connection refused")
        assert "scc org update" in hint

    def test_max_stale_age_returns_cache_expired_hint(self) -> None:
        """Cache expiration mentions MAX_STALE_AGE."""
        hint = _get_fetch_remediation("github", "max_stale_age exceeded")
        assert "expired" in hint

    def test_expired_cache_returns_network_hint(self) -> None:
        """Expired cache suggests connecting to network."""
        hint = _get_fetch_remediation("git", "Cache expired after TTL")
        assert "network" in hint.lower()

    def test_git_clone_error_returns_access_hint(self) -> None:
        """Git clone errors suggest checking access."""
        hint = _get_fetch_remediation("git", "Failed to clone repository")
        assert "access" in hint.lower() or "permissions" in hint.lower()

    def test_git_branch_error_returns_branch_hint(self) -> None:
        """Git branch errors suggest verifying branch name."""
        hint = _get_fetch_remediation("github", "Branch 'develop' not found")
        assert "branch" in hint.lower()

    def test_git_path_not_found_returns_path_hint(self) -> None:
        """Git path errors suggest checking file path."""
        hint = _get_fetch_remediation("git", "Path 'configs/team.json' not found")
        assert "team-config.json" in hint or "path" in hint.lower()

    def test_url_401_returns_auth_hint(self) -> None:
        """HTTP 401 suggests adding authentication."""
        hint = _get_fetch_remediation("url", "HTTP 401 Unauthorized")
        assert "auth" in hint.lower()

    def test_url_403_returns_permission_hint(self) -> None:
        """HTTP 403 suggests checking permissions."""
        hint = _get_fetch_remediation("url", "HTTP 403 Forbidden")
        assert "permission" in hint.lower() or "access" in hint.lower()

    def test_url_404_returns_verify_url_hint(self) -> None:
        """HTTP 404 suggests verifying URL."""
        hint = _get_fetch_remediation("url", "HTTP 404 Not Found")
        assert "verify" in hint.lower() or "correct" in hint.lower()

    def test_generic_error_returns_update_hint(self) -> None:
        """Unknown errors suggest running org update to retry."""
        hint = _get_fetch_remediation("github", "Unknown internal error")
        assert "scc org update" in hint


# ─────────────────────────────────────────────────────────────────────────────
# EffectiveConfig Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestEffectiveConfig:
    """Tests for EffectiveConfig dataclass."""

    def test_has_security_violations_empty_blocked(self) -> None:
        """No blocked plugins means no security violations."""
        config = EffectiveConfig(
            team_id="backend",
            is_federated=False,
            enabled_plugins={"plugin-a@shared"},
            blocked_plugins=[],
        )
        assert config.has_security_violations is False

    def test_has_security_violations_with_blocked(self) -> None:
        """Blocked plugins means security violations present."""
        from scc_cli.marketplace.compute import BlockedPlugin

        config = EffectiveConfig(
            team_id="backend",
            is_federated=False,
            enabled_plugins=set(),
            blocked_plugins=[
                BlockedPlugin(plugin_id="malware@evil", reason="Blocked", pattern="*@evil")
            ],
        )
        assert config.has_security_violations is True

    def test_plugin_count(self) -> None:
        """Plugin count returns number of enabled plugins."""
        config = EffectiveConfig(
            team_id="backend",
            is_federated=False,
            enabled_plugins={"a@shared", "b@shared", "c@official"},
        )
        assert config.plugin_count == 3

    def test_plugin_count_empty(self) -> None:
        """Plugin count is zero when no plugins enabled."""
        config = EffectiveConfig(
            team_id="backend",
            is_federated=False,
            enabled_plugins=set(),
        )
        assert config.plugin_count == 0


class TestEffectiveConfigSourceDescription:
    """Tests for EffectiveConfig.source_description property."""

    def test_inline_returns_inline(self) -> None:
        """Non-federated config returns 'inline'."""
        config = EffectiveConfig(
            team_id="backend",
            is_federated=False,
            enabled_plugins=set(),
        )
        assert config.source_description == "inline"

    def test_federated_without_source_returns_inline(self) -> None:
        """Federated with no config_source returns 'inline'."""
        config = EffectiveConfig(
            team_id="backend",
            is_federated=True,
            enabled_plugins=set(),
            config_source=None,
        )
        assert config.source_description == "inline"

    def test_github_source_returns_github_url(self) -> None:
        """GitHub source returns formatted github.com URL."""
        config = EffectiveConfig(
            team_id="backend",
            is_federated=True,
            enabled_plugins=set(),
            config_source=ConfigSourceGitHub(
                source="github",
                owner="myorg",
                repo="plugins",
            ),
        )
        assert config.source_description == "github.com/myorg/plugins"

    def test_git_source_https_strips_protocol(self) -> None:
        """Git HTTPS source strips https:// prefix."""
        config = EffectiveConfig(
            team_id="backend",
            is_federated=True,
            enabled_plugins=set(),
            config_source=ConfigSourceGit(
                source="git",
                url="https://gitlab.com/org/repo.git",
            ),
        )
        desc = config.source_description
        assert desc.startswith("gitlab.com")
        assert not desc.startswith("https://")

    def test_git_source_ssh_normalizes(self) -> None:
        """Git SSH source normalizes git@ format."""
        config = EffectiveConfig(
            team_id="backend",
            is_federated=True,
            enabled_plugins=set(),
            config_source=ConfigSourceGit(
                source="git",
                url="git@github.com:org/repo.git",
            ),
        )
        desc = config.source_description
        assert "github.com" in desc
        assert not desc.startswith("git@")

    def test_url_source_strips_https(self) -> None:
        """URL source strips https:// prefix."""
        config = EffectiveConfig(
            team_id="backend",
            is_federated=True,
            enabled_plugins=set(),
            config_source=ConfigSourceURL(
                source="url",
                url="https://example.com/configs/team.json",
            ),
        )
        desc = config.source_description
        assert desc.startswith("example.com")
        assert not desc.startswith("https://")


class TestEffectiveConfigToPhase1Format:
    """Tests for EffectiveConfig.to_phase1_format() method."""

    def test_returns_tuple(self) -> None:
        """Returns tuple of EffectivePlugins and marketplaces dict."""
        config = EffectiveConfig(
            team_id="backend",
            is_federated=False,
            enabled_plugins={"plugin-a@shared"},
            marketplaces={},
        )
        result = config.to_phase1_format()
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_plugins_have_enabled_set(self) -> None:
        """EffectivePlugins contains enabled set."""
        config = EffectiveConfig(
            team_id="backend",
            is_federated=False,
            enabled_plugins={"a@x", "b@y"},
        )
        plugins, _ = config.to_phase1_format()
        assert plugins.enabled == {"a@x", "b@y"}

    def test_plugins_have_blocked_list(self) -> None:
        """EffectivePlugins contains blocked list."""
        from scc_cli.marketplace.compute import BlockedPlugin

        blocked = [BlockedPlugin(plugin_id="bad@evil", reason="Blocked", pattern="*@evil")]
        config = EffectiveConfig(
            team_id="backend",
            is_federated=False,
            enabled_plugins=set(),
            blocked_plugins=blocked,
        )
        plugins, _ = config.to_phase1_format()
        assert plugins.blocked == blocked

    def test_marketplaces_preserved(self) -> None:
        """Marketplaces dict is preserved."""
        mp = MarketplaceSourceGitHub(source="github", owner="org", repo="mp")
        config = EffectiveConfig(
            team_id="backend",
            is_federated=False,
            enabled_plugins=set(),
            marketplaces={"shared": mp},
        )
        _, marketplaces = config.to_phase1_format()
        assert marketplaces == {"shared": mp}


# ─────────────────────────────────────────────────────────────────────────────
# resolve_effective_config() Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestResolveEffectiveConfigInline:
    """Tests for resolve_effective_config() with inline teams."""

    def test_team_not_found_raises(self) -> None:
        """Non-existent team raises TeamNotFoundError."""
        config = OrganizationConfig(
            name="Test Org",
            schema_version=1,
            profiles={"backend": TeamProfile(name="backend")},
        )
        with pytest.raises(TeamNotFoundError) as exc_info:
            resolve_effective_config(config, "frontend")
        assert exc_info.value.team_id == "frontend"
        assert "backend" in exc_info.value.available_teams

    def test_inline_team_returns_not_federated(self) -> None:
        """Inline team (no config_source) returns is_federated=False."""
        config = OrganizationConfig(
            name="Test Org",
            schema_version=1,
            profiles={"backend": TeamProfile(name="backend")},
        )
        result = resolve_effective_config(config, "backend")
        assert result.is_federated is False
        assert result.team_id == "backend"

    def test_inline_team_uses_compute_effective_plugins(self) -> None:
        """Inline team uses compute_effective_plugins() for resolution."""
        config = OrganizationConfig(
            name="Test Org",
            schema_version=1,
            defaults=DefaultsConfig(
                enabled_plugins=["plugin-a@claude-plugins-official"],
            ),
            profiles={
                "backend": TeamProfile(name="backend"),
            },
        )
        result = resolve_effective_config(config, "backend")
        assert "plugin-a@claude-plugins-official" in result.enabled_plugins


class TestResolveEffectiveConfigFederated:
    """Tests for resolve_effective_config() with federated teams."""

    @patch("scc_cli.marketplace.resolve.fetch_team_config_with_fallback")
    def test_federated_team_returns_federated(self, mock_fetch: MagicMock) -> None:
        """Federated team (has config_source) returns is_federated=True."""
        # Setup mock
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.result.team_config = {"schema_version": 1, "enabled_plugins": []}
        mock_result.result.source_type = "github"
        mock_result.result.source_url = "github.com/org/repo"
        mock_result.result.commit_sha = "abc123"
        mock_result.result.etag = None
        mock_result.used_cache = False
        mock_result.is_stale = False
        mock_result.staleness_warning = None
        mock_fetch.return_value = mock_result

        config = OrganizationConfig(
            name="Test Org",
            schema_version=1,
            profiles={
                "frontend": TeamProfile(
                    name="frontend",
                    config_source=ConfigSourceGitHub(
                        source="github",
                        owner="org",
                        repo="team-configs",
                    ),
                    trust=TrustGrant(),
                ),
            },
        )
        result = resolve_effective_config(config, "frontend")
        assert result.is_federated is True
        assert result.config_commit_sha == "abc123"

    @patch("scc_cli.marketplace.resolve.fetch_team_config_with_fallback")
    def test_federated_fetch_failure_raises_config_fetch_error(self, mock_fetch: MagicMock) -> None:
        """Failed fetch raises ConfigFetchError with details."""
        # Setup mock for failed fetch
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.result.team_config = None
        mock_result.result.source_type = "url"
        mock_result.result.source_url = "https://example.com/config.json"
        mock_result.result.error = "HTTP 404 Not Found"
        mock_fetch.return_value = mock_result

        config = OrganizationConfig(
            name="Test Org",
            schema_version=1,
            profiles={
                "frontend": TeamProfile(
                    name="frontend",
                    config_source=ConfigSourceURL(
                        source="url",
                        url="https://example.com/config.json",
                    ),
                ),
            },
        )
        with pytest.raises(ConfigFetchError) as exc_info:
            resolve_effective_config(config, "frontend")
        assert exc_info.value.team_id == "frontend"
        assert exc_info.value.source_type == "url"
        assert "404" in str(exc_info.value)

    @patch("scc_cli.marketplace.resolve.fetch_team_config_with_fallback")
    def test_federated_uses_cache_status(self, mock_fetch: MagicMock) -> None:
        """Federated resolution tracks cache status."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.result.team_config = {"schema_version": 1, "enabled_plugins": []}
        mock_result.result.source_type = "github"
        mock_result.result.source_url = "github.com/org/repo"
        mock_result.result.commit_sha = None
        mock_result.result.etag = None
        mock_result.used_cache = True
        mock_result.is_stale = True
        mock_result.staleness_warning = "Cache is 5 days old"
        mock_fetch.return_value = mock_result

        config = OrganizationConfig(
            name="Test Org",
            schema_version=1,
            profiles={
                "frontend": TeamProfile(
                    name="frontend",
                    config_source=ConfigSourceGitHub(
                        source="github",
                        owner="org",
                        repo="configs",
                    ),
                    trust=TrustGrant(),
                ),
            },
        )
        result = resolve_effective_config(config, "frontend")
        assert result.used_cached_config is True
        assert result.cache_is_stale is True
        assert result.staleness_warning == "Cache is 5 days old"


# ─────────────────────────────────────────────────────────────────────────────
# _validate_defaults_dont_need_org_marketplaces() Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateDefaultsDontNeedOrgMarketplaces:
    """Tests for validation when inherit_org_marketplaces=false."""

    def test_no_defaults_no_validation_needed(self) -> None:
        """No defaults means no validation needed."""
        config = OrganizationConfig(
            name="Test Org",
            schema_version=1,
            profiles={"backend": TeamProfile(name="backend")},
        )
        # Should not raise
        _validate_defaults_dont_need_org_marketplaces(
            config=config,
            org_marketplaces={},
            team_id="backend",
        )

    def test_defaults_without_enabled_plugins_no_validation(self) -> None:
        """Defaults without enabled_plugins needs no validation."""
        from scc_cli.marketplace.schema import DefaultsConfig

        config = OrganizationConfig(
            name="Test Org",
            schema_version=1,
            profiles={"backend": TeamProfile(name="backend")},
            defaults=DefaultsConfig(disabled_plugins=["some-plugin"]),
        )
        # Should not raise
        _validate_defaults_dont_need_org_marketplaces(
            config=config,
            org_marketplaces={},
            team_id="backend",
        )

    def test_defaults_using_implicit_marketplace_allowed(self) -> None:
        """Defaults using implicit marketplace (claude-plugins-official) allowed."""
        from scc_cli.marketplace.schema import DefaultsConfig

        config = OrganizationConfig(
            name="Test Org",
            schema_version=1,
            profiles={"backend": TeamProfile(name="backend")},
            defaults=DefaultsConfig(
                enabled_plugins=["some-plugin@claude-plugins-official"],
            ),
        )
        # Should not raise - implicit marketplace always available
        _validate_defaults_dont_need_org_marketplaces(
            config=config,
            org_marketplaces={},
            team_id="backend",
        )

    def test_defaults_using_org_marketplace_raises(self) -> None:
        """Defaults referencing org marketplace raises when inherit=false."""
        from scc_cli.marketplace.schema import DefaultsConfig

        org_mp = MarketplaceSourceGitHub(source="github", owner="org", repo="mp")
        config = OrganizationConfig(
            name="Test Org",
            schema_version=1,
            profiles={"backend": TeamProfile(name="backend")},
            defaults=DefaultsConfig(
                enabled_plugins=["plugin-a@shared"],
            ),
        )
        with pytest.raises(TrustViolationError) as exc_info:
            _validate_defaults_dont_need_org_marketplaces(
                config=config,
                org_marketplaces={"shared": org_mp},
                team_id="backend",
            )
        assert "inherit_org_marketplaces=false" in str(exc_info.value)
        assert "shared" in str(exc_info.value)

    def test_multiple_conflicting_plugins_all_reported(self) -> None:
        """Multiple plugins requiring org marketplaces are all reported."""
        from scc_cli.marketplace.schema import DefaultsConfig

        org_mp = MarketplaceSourceGitHub(source="github", owner="org", repo="mp")
        config = OrganizationConfig(
            name="Test Org",
            schema_version=1,
            profiles={"backend": TeamProfile(name="backend")},
            defaults=DefaultsConfig(
                enabled_plugins=[
                    "plugin-a@shared",
                    "plugin-b@shared",
                    "plugin-c@internal",
                ],
            ),
        )
        with pytest.raises(TrustViolationError) as exc_info:
            _validate_defaults_dont_need_org_marketplaces(
                config=config,
                org_marketplaces={"shared": org_mp, "internal": org_mp},
                team_id="backend",
            )
        error_msg = str(exc_info.value)
        assert "plugin-a@shared" in error_msg
        assert "plugin-b@shared" in error_msg
        assert "plugin-c@internal" in error_msg
