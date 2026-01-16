"""Tests for EffectiveConfig dataclass (Phase 2: Federation).

Covers:
- EffectiveConfig dataclass creation and field validation
- Federated vs inline config detection
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from scc_cli.marketplace.schema import DelegationConfig, OrganizationConfig, TeamProfile


def make_org_config(**kwargs: Any) -> OrganizationConfig:
    from scc_cli.marketplace.schema import OrganizationConfig, OrganizationInfo

    organization = kwargs.pop(
        "organization",
        OrganizationInfo(name="Test Org", id="test-org"),
    )
    schema_version = kwargs.pop("schema_version", "1.0.0")
    return OrganizationConfig(
        schema_version=schema_version,
        organization=organization,
        **kwargs,
    )


def make_team_profile(**kwargs: Any) -> TeamProfile:
    from scc_cli.marketplace.schema import TeamProfile

    return TeamProfile(**kwargs)


def allow_all_delegation() -> DelegationConfig:
    from scc_cli.marketplace.schema import DelegationConfig, DelegationTeamsConfig

    return DelegationConfig(
        teams=DelegationTeamsConfig(allow_additional_plugins=["*"]),
    )


# ─────────────────────────────────────────────────────────────────────────────
# EffectiveConfig Dataclass Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestEffectiveConfigCreation:
    """Tests for EffectiveConfig dataclass instantiation."""

    def test_minimal_inline_config(self) -> None:
        """Create minimal inline (non-federated) effective config."""
        from scc_cli.marketplace.resolve import EffectiveConfig

        config = EffectiveConfig(
            team_id="backend",
            is_federated=False,
            enabled_plugins={"plugin-a@official", "plugin-b@official"},
        )

        assert config.team_id == "backend"
        assert config.is_federated is False
        assert config.enabled_plugins == {"plugin-a@official", "plugin-b@official"}
        assert config.config_source is None
        assert config.config_commit_sha is None

    def test_federated_config_with_github_source(self) -> None:
        """Create federated config with GitHub config source."""
        from scc_cli.marketplace.resolve import EffectiveConfig
        from scc_cli.marketplace.schema import ConfigSourceGitHub

        source = ConfigSourceGitHub(
            source="github",
            owner="sundsvall-backend",
            repo="team-config",
        )

        config = EffectiveConfig(
            team_id="backend",
            is_federated=True,
            config_source=source,
            config_commit_sha="abc123def456",
            enabled_plugins={"plugin-a@official"},
        )

        assert config.is_federated is True
        assert config.config_source == source
        assert config.config_commit_sha == "abc123def456"

    def test_federated_config_with_url_source(self) -> None:
        """Create federated config with URL config source."""
        from scc_cli.marketplace.resolve import EffectiveConfig
        from scc_cli.marketplace.schema import ConfigSourceURL

        source = ConfigSourceURL(
            source="url",
            url="https://teams.sundsvall.se/backend/team-config.json",
        )

        config = EffectiveConfig(
            team_id="backend",
            is_federated=True,
            config_source=source,
            config_etag='"xyz789"',
            enabled_plugins=set(),
        )

        assert config.config_source == source
        assert config.config_etag == '"xyz789"'
        assert config.config_commit_sha is None

    def test_blocked_plugins_tracking(self) -> None:
        """EffectiveConfig tracks blocked plugins with reasons."""
        from scc_cli.marketplace.compute import BlockedPlugin
        from scc_cli.marketplace.resolve import EffectiveConfig

        blocked = [
            BlockedPlugin(
                plugin_id="dangerous@evil",
                reason="Security risk",
                pattern="*@evil",
            ),
        ]

        config = EffectiveConfig(
            team_id="backend",
            is_federated=False,
            enabled_plugins=set(),
            blocked_plugins=blocked,
        )

        assert len(config.blocked_plugins) == 1
        assert config.blocked_plugins[0].plugin_id == "dangerous@evil"

    def test_disabled_and_not_allowed_plugins(self) -> None:
        """EffectiveConfig tracks disabled and not_allowed plugins."""
        from scc_cli.marketplace.resolve import EffectiveConfig

        config = EffectiveConfig(
            team_id="backend",
            is_federated=False,
            enabled_plugins={"allowed@official"},
            disabled_plugins=["disabled-by-pattern@official"],
            not_allowed_plugins=["blocked-by-allowlist@internal"],
        )

        assert config.disabled_plugins == ["disabled-by-pattern@official"]
        assert config.not_allowed_plugins == ["blocked-by-allowlist@internal"]

    def test_effective_marketplaces(self) -> None:
        """EffectiveConfig tracks effective marketplaces."""
        from scc_cli.marketplace.resolve import EffectiveConfig
        from scc_cli.marketplace.schema import MarketplaceSourceGitHub

        mp_source = MarketplaceSourceGitHub(
            source="github",
            owner="company",
            repo="plugins",
        )

        config = EffectiveConfig(
            team_id="backend",
            is_federated=False,
            enabled_plugins=set(),
            marketplaces={"shared": mp_source},
        )

        assert "shared" in config.marketplaces
        assert config.marketplaces["shared"] == mp_source

    def test_extra_marketplaces_list(self) -> None:
        """EffectiveConfig tracks extra marketplace IDs."""
        from scc_cli.marketplace.resolve import EffectiveConfig

        config = EffectiveConfig(
            team_id="backend",
            is_federated=False,
            enabled_plugins=set(),
            extra_marketplaces=["extra-mp-1", "extra-mp-2"],
        )

        assert config.extra_marketplaces == ["extra-mp-1", "extra-mp-2"]

    def test_default_values(self) -> None:
        """Optional fields have sensible defaults."""
        from scc_cli.marketplace.resolve import EffectiveConfig

        config = EffectiveConfig(
            team_id="backend",
            is_federated=False,
            enabled_plugins=set(),
        )

        assert config.config_source is None
        assert config.config_commit_sha is None
        assert config.config_etag is None
        assert config.blocked_plugins == []
        assert config.disabled_plugins == []
        assert config.not_allowed_plugins == []
        assert config.marketplaces == {}
        assert config.extra_marketplaces == []


class TestEffectiveConfigProperties:
    """Tests for EffectiveConfig computed properties."""

    def test_has_security_violations_when_blocked(self) -> None:
        """has_security_violations returns True when plugins blocked."""
        from scc_cli.marketplace.compute import BlockedPlugin
        from scc_cli.marketplace.resolve import EffectiveConfig

        config = EffectiveConfig(
            team_id="backend",
            is_federated=False,
            enabled_plugins=set(),
            blocked_plugins=[
                BlockedPlugin(plugin_id="x@y", reason="r", pattern="p"),
            ],
        )

        assert config.has_security_violations is True

    def test_has_security_violations_false_when_clean(self) -> None:
        """has_security_violations returns False when no blocked plugins."""
        from scc_cli.marketplace.resolve import EffectiveConfig

        config = EffectiveConfig(
            team_id="backend",
            is_federated=False,
            enabled_plugins={"clean@official"},
        )

        assert config.has_security_violations is False

    def test_plugin_count(self) -> None:
        """plugin_count returns total enabled plugins."""
        from scc_cli.marketplace.resolve import EffectiveConfig

        config = EffectiveConfig(
            team_id="backend",
            is_federated=False,
            enabled_plugins={"a@x", "b@x", "c@y"},
        )

        assert config.plugin_count == 3

    def test_source_description_for_inline(self) -> None:
        """source_description returns 'inline' for non-federated."""
        from scc_cli.marketplace.resolve import EffectiveConfig

        config = EffectiveConfig(
            team_id="backend",
            is_federated=False,
            enabled_plugins=set(),
        )

        assert config.source_description == "inline"

    def test_source_description_for_github(self) -> None:
        """source_description returns GitHub URL for GitHub source."""
        from scc_cli.marketplace.resolve import EffectiveConfig
        from scc_cli.marketplace.schema import ConfigSourceGitHub

        source = ConfigSourceGitHub(
            source="github",
            owner="sundsvall",
            repo="backend-config",
        )

        config = EffectiveConfig(
            team_id="backend",
            is_federated=True,
            config_source=source,
            enabled_plugins=set(),
        )

        assert "github.com/sundsvall/backend-config" in config.source_description

    def test_source_description_for_url(self) -> None:
        """source_description returns URL for URL source."""
        from scc_cli.marketplace.resolve import EffectiveConfig
        from scc_cli.marketplace.schema import ConfigSourceURL

        source = ConfigSourceURL(
            source="url",
            url="https://teams.sundsvall.se/backend/config.json",
        )

        config = EffectiveConfig(
            team_id="backend",
            is_federated=True,
            config_source=source,
            enabled_plugins=set(),
        )

        assert "teams.sundsvall.se" in config.source_description


# ─────────────────────────────────────────────────────────────────────────────
# resolve_effective_config() Orchestrator Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestResolveEffectiveConfigInline:
    """Tests for resolve_effective_config() with inline (non-federated) teams."""

    def test_inline_team_returns_effective_config(self) -> None:
        """Inline teams (no config_source) return EffectiveConfig with is_federated=False."""
        from scc_cli.marketplace.resolve import EffectiveConfig, resolve_effective_config
        from scc_cli.marketplace.schema import DefaultsConfig

        config = make_org_config(
            defaults=DefaultsConfig(
                enabled_plugins=["plugin-a@claude-plugins-official"],
            ),
            profiles={
                "backend": make_team_profile(),
            },
        )

        result = resolve_effective_config(config, "backend")

        assert isinstance(result, EffectiveConfig)
        assert result.team_id == "backend"
        assert result.is_federated is False
        assert "plugin-a@claude-plugins-official" in result.enabled_plugins

    def test_inline_team_applies_additional_plugins(self) -> None:
        """Inline teams merge defaults + additional plugins."""
        from scc_cli.marketplace.resolve import resolve_effective_config
        from scc_cli.marketplace.schema import DefaultsConfig

        config = make_org_config(
            defaults=DefaultsConfig(
                enabled_plugins=["default-plugin@claude-plugins-official"],
            ),
            delegation=allow_all_delegation(),
            profiles={
                "backend": make_team_profile(
                    additional_plugins=["extra-plugin@claude-plugins-official"],
                ),
            },
        )

        result = resolve_effective_config(config, "backend")

        assert "default-plugin@claude-plugins-official" in result.enabled_plugins
        assert "extra-plugin@claude-plugins-official" in result.enabled_plugins

    def test_inline_team_applies_disabled_plugins(self) -> None:
        """Inline teams apply disabled_plugins patterns."""
        from scc_cli.marketplace.resolve import resolve_effective_config
        from scc_cli.marketplace.schema import DefaultsConfig

        config = make_org_config(
            defaults=DefaultsConfig(
                enabled_plugins=[
                    "plugin-a@claude-plugins-official",
                    "plugin-b@claude-plugins-official",
                ],
                disabled_plugins=["plugin-b*"],
            ),
            profiles={
                "backend": make_team_profile(),
            },
        )

        result = resolve_effective_config(config, "backend")

        assert "plugin-a@claude-plugins-official" in result.enabled_plugins
        assert "plugin-b@claude-plugins-official" not in result.enabled_plugins
        assert "plugin-b@claude-plugins-official" in result.disabled_plugins

    def test_inline_team_applies_security_blocking(self) -> None:
        """Inline teams apply security.blocked_plugins."""
        from scc_cli.marketplace.resolve import resolve_effective_config
        from scc_cli.marketplace.schema import DefaultsConfig, SecurityConfig

        config = make_org_config(
            defaults=DefaultsConfig(
                enabled_plugins=["safe@claude-plugins-official", "risky@dangerous-mp"],
            ),
            profiles={
                "backend": make_team_profile(),
            },
            security=SecurityConfig(
                blocked_plugins=["*@dangerous-mp"],
            ),
        )

        result = resolve_effective_config(config, "backend")

        assert "safe@claude-plugins-official" in result.enabled_plugins
        assert len(result.blocked_plugins) == 1
        assert result.blocked_plugins[0].plugin_id == "risky@dangerous-mp"

    def test_inline_team_not_found_raises_error(self) -> None:
        """Missing team raises TeamNotFoundError."""
        from scc_cli.marketplace.compute import TeamNotFoundError
        from scc_cli.marketplace.resolve import resolve_effective_config

        config = make_org_config(
            profiles={
                "backend": make_team_profile(),
            },
        )

        with pytest.raises(TeamNotFoundError) as exc_info:
            resolve_effective_config(config, "nonexistent")

        assert "nonexistent" in str(exc_info.value)

    def test_inline_team_collects_marketplaces(self) -> None:
        """Inline teams include org marketplaces in result."""
        from scc_cli.marketplace.resolve import resolve_effective_config
        from scc_cli.marketplace.schema import MarketplaceSourceGitHub

        config = make_org_config(
            profiles={
                "backend": make_team_profile(),
            },
            marketplaces={
                "shared": MarketplaceSourceGitHub(
                    source="github",
                    owner="company",
                    repo="plugins",
                ),
            },
        )

        result = resolve_effective_config(config, "backend")

        assert "shared" in result.marketplaces


class TestResolveEffectiveConfigFederated:
    """Tests for resolve_effective_config() with federated teams."""

    def test_federated_team_detection(self) -> None:
        """Teams with config_source are detected as federated."""
        from unittest.mock import patch

        from scc_cli.marketplace.resolve import resolve_effective_config
        from scc_cli.marketplace.schema import (
            ConfigSourceGitHub,
            TeamConfig,
            TrustGrant,
        )

        source = ConfigSourceGitHub(
            source="github",
            owner="sundsvall-backend",
            repo="team-config",
        )

        config = make_org_config(
            profiles={
                "backend": make_team_profile(
                    config_source=source,
                    trust=TrustGrant(
                        inherit_org_marketplaces=True,
                    ),
                ),
            },
        )

        # Mock the fetch to return a valid team config
        team_config = TeamConfig(
            schema_version="1.0.0",
            enabled_plugins=["team-plugin@claude-plugins-official"],
        )

        with patch("scc_cli.marketplace.resolve.fetch_team_config_with_fallback") as mock_fetch:
            from unittest.mock import MagicMock

            mock_result = MagicMock()
            mock_result.success = True
            mock_result.result.team_config = team_config.model_dump()
            mock_result.result.source_type = "github"
            mock_result.result.source_url = "github.com/sundsvall-backend/team-config"
            mock_result.result.commit_sha = "abc123"
            mock_result.result.etag = None
            mock_result.used_cache = False
            mock_result.is_stale = False
            mock_result.staleness_warning = None
            mock_fetch.return_value = mock_result

            result = resolve_effective_config(config, "backend")

        assert result.is_federated is True
        assert result.config_source == source
        assert result.config_commit_sha == "abc123"

    def test_federated_team_uses_team_config_plugins(self) -> None:
        """Federated teams use TeamConfig.enabled_plugins, not additional_plugins."""
        from unittest.mock import patch

        from scc_cli.marketplace.resolve import resolve_effective_config
        from scc_cli.marketplace.schema import (
            ConfigSourceGitHub,
            DefaultsConfig,
            TeamConfig,
            TrustGrant,
        )

        config = make_org_config(
            defaults=DefaultsConfig(
                enabled_plugins=["default@claude-plugins-official"],
            ),
            delegation=allow_all_delegation(),
            profiles={
                "backend": make_team_profile(
                    config_source=ConfigSourceGitHub(
                        source="github",
                        owner="org",
                        repo="config",
                    ),
                    trust=TrustGrant(inherit_org_marketplaces=True),
                ),
            },
        )

        team_config = TeamConfig(
            schema_version="1.0.0",
            enabled_plugins=["team-specific@claude-plugins-official"],
        )

        with patch("scc_cli.marketplace.resolve.fetch_team_config_with_fallback") as mock_fetch:
            from unittest.mock import MagicMock

            mock_result = MagicMock()
            mock_result.success = True
            mock_result.result.team_config = team_config.model_dump()
            mock_result.result.source_type = "github"
            mock_result.result.source_url = "github.com/org/config"
            mock_result.result.commit_sha = "def456"
            mock_result.result.etag = None
            mock_result.used_cache = False
            mock_result.is_stale = False
            mock_result.staleness_warning = None
            mock_fetch.return_value = mock_result

            result = resolve_effective_config(config, "backend")

        # Should have both default and team plugins
        assert "default@claude-plugins-official" in result.enabled_plugins
        assert "team-specific@claude-plugins-official" in result.enabled_plugins

    def test_federated_team_security_always_enforced(self) -> None:
        """Security.blocked_plugins always enforced on federated teams."""
        from unittest.mock import patch

        from scc_cli.marketplace.resolve import resolve_effective_config
        from scc_cli.marketplace.schema import (
            ConfigSourceGitHub,
            SecurityConfig,
            TeamConfig,
            TrustGrant,
        )

        config = make_org_config(
            delegation=allow_all_delegation(),
            profiles={
                "backend": make_team_profile(
                    config_source=ConfigSourceGitHub(
                        source="github",
                        owner="org",
                        repo="config",
                    ),
                    trust=TrustGrant(inherit_org_marketplaces=True),
                ),
            },
            security=SecurityConfig(
                blocked_plugins=["dangerous@evil"],
            ),
        )

        team_config = TeamConfig(
            schema_version="1.0.0",
            enabled_plugins=["safe@claude-plugins-official", "dangerous@evil"],
        )

        with patch("scc_cli.marketplace.resolve.fetch_team_config_with_fallback") as mock_fetch:
            from unittest.mock import MagicMock

            mock_result = MagicMock()
            mock_result.success = True
            mock_result.result.team_config = team_config.model_dump()
            mock_result.result.source_type = "github"
            mock_result.result.source_url = "github.com/org/config"
            mock_result.result.commit_sha = None
            mock_result.result.etag = None
            mock_result.used_cache = False
            mock_result.is_stale = False
            mock_result.staleness_warning = None
            mock_fetch.return_value = mock_result

            result = resolve_effective_config(config, "backend")

        assert "safe@claude-plugins-official" in result.enabled_plugins
        assert len(result.blocked_plugins) == 1
        assert result.blocked_plugins[0].plugin_id == "dangerous@evil"


# ─────────────────────────────────────────────────────────────────────────────
# T2a-28: inherit_org_marketplaces=false Validation Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestInheritOrgMarketplacesValidation:
    """Tests for T2a-28: Validate inherit_org_marketplaces=false scenario."""

    def test_inherit_false_without_defaults_passes(self) -> None:
        """inherit_org_marketplaces=false is allowed when defaults don't use org marketplaces."""
        from unittest.mock import patch

        from scc_cli.marketplace.resolve import resolve_effective_config
        from scc_cli.marketplace.schema import (
            ConfigSourceGitHub,
            MarketplaceSourceGitHub,
            TeamConfig,
            TrustGrant,
        )

        config = make_org_config(
            profiles={
                "isolated": make_team_profile(
                    config_source=ConfigSourceGitHub(
                        source="github",
                        owner="team-isolated",
                        repo="config",
                    ),
                    trust=TrustGrant(
                        inherit_org_marketplaces=False,  # Team opts out of org marketplaces
                    ),
                ),
            },
            marketplaces={
                "shared": MarketplaceSourceGitHub(
                    source="github",
                    owner="company",
                    repo="plugins",
                ),
            },
            # No defaults.enabled_plugins set
        )

        team_config = TeamConfig(
            schema_version="1.0.0",
            enabled_plugins=["plugin@claude-plugins-official"],
        )

        with patch("scc_cli.marketplace.resolve.fetch_team_config_with_fallback") as mock_fetch:
            from unittest.mock import MagicMock

            mock_result = MagicMock()
            mock_result.success = True
            mock_result.result.team_config = team_config.model_dump()
            mock_result.result.source_type = "github"
            mock_result.result.source_url = "github.com/team-isolated/config"
            mock_result.result.commit_sha = "abc123"
            mock_result.result.etag = None
            mock_result.used_cache = False
            mock_result.is_stale = False
            mock_result.staleness_warning = None
            mock_fetch.return_value = mock_result

            # Should pass - no defaults reference org marketplaces
            result = resolve_effective_config(config, "isolated")

        assert result.is_federated is True
        assert "shared" not in result.marketplaces  # Org marketplace not inherited

    def test_inherit_false_with_implicit_marketplace_defaults_passes(self) -> None:
        """inherit_org_marketplaces=false allowed when defaults only use implicit marketplaces."""
        from unittest.mock import patch

        from scc_cli.marketplace.resolve import resolve_effective_config
        from scc_cli.marketplace.schema import (
            ConfigSourceGitHub,
            DefaultsConfig,
            MarketplaceSourceGitHub,
            TeamConfig,
            TrustGrant,
        )

        config = make_org_config(
            defaults=DefaultsConfig(
                enabled_plugins=[
                    "standard@claude-plugins-official",  # Implicit marketplace - always available
                ],
            ),
            profiles={
                "isolated": make_team_profile(
                    config_source=ConfigSourceGitHub(
                        source="github",
                        owner="team-isolated",
                        repo="config",
                    ),
                    trust=TrustGrant(
                        inherit_org_marketplaces=False,
                    ),
                ),
            },
            marketplaces={
                "shared": MarketplaceSourceGitHub(
                    source="github",
                    owner="company",
                    repo="plugins",
                ),
            },
        )

        team_config = TeamConfig(
            schema_version="1.0.0",
            enabled_plugins=["team-plugin@claude-plugins-official"],
        )

        with patch("scc_cli.marketplace.resolve.fetch_team_config_with_fallback") as mock_fetch:
            from unittest.mock import MagicMock

            mock_result = MagicMock()
            mock_result.success = True
            mock_result.result.team_config = team_config.model_dump()
            mock_result.result.source_type = "github"
            mock_result.result.source_url = "github.com/team-isolated/config"
            mock_result.result.commit_sha = "abc123"
            mock_result.result.etag = None
            mock_result.used_cache = False
            mock_result.is_stale = False
            mock_result.staleness_warning = None
            mock_fetch.return_value = mock_result

            # Should pass - defaults only reference implicit marketplace
            result = resolve_effective_config(config, "isolated")

        assert result.is_federated is True
        assert "shared" not in result.marketplaces

    def test_inherit_false_with_org_marketplace_defaults_raises(self) -> None:
        """inherit_org_marketplaces=false fails when defaults need org marketplaces."""
        from unittest.mock import patch

        from scc_cli.marketplace.resolve import resolve_effective_config
        from scc_cli.marketplace.schema import (
            ConfigSourceGitHub,
            DefaultsConfig,
            MarketplaceSourceGitHub,
            TeamConfig,
            TrustGrant,
        )
        from scc_cli.marketplace.trust import TrustViolationError

        config = make_org_config(
            defaults=DefaultsConfig(
                enabled_plugins=[
                    "required-plugin@shared",  # References org marketplace
                ],
            ),
            profiles={
                "isolated": make_team_profile(
                    config_source=ConfigSourceGitHub(
                        source="github",
                        owner="team-isolated",
                        repo="config",
                    ),
                    trust=TrustGrant(
                        inherit_org_marketplaces=False,  # Conflict!
                    ),
                ),
            },
            marketplaces={
                "shared": MarketplaceSourceGitHub(
                    source="github",
                    owner="company",
                    repo="plugins",
                ),
            },
        )

        team_config = TeamConfig(
            schema_version="1.0.0",
            enabled_plugins=["team-plugin@claude-plugins-official"],
        )

        with patch("scc_cli.marketplace.resolve.fetch_team_config_with_fallback") as mock_fetch:
            from unittest.mock import MagicMock

            mock_result = MagicMock()
            mock_result.success = True
            mock_result.result.team_config = team_config.model_dump()
            mock_result.result.source_type = "github"
            mock_result.result.source_url = "github.com/team-isolated/config"
            mock_result.result.commit_sha = "abc123"
            mock_result.result.etag = None
            mock_result.used_cache = False
            mock_result.is_stale = False
            mock_result.staleness_warning = None
            mock_fetch.return_value = mock_result

            # Should fail - defaults require @shared but inherit=false
            with pytest.raises(TrustViolationError) as exc_info:
                resolve_effective_config(config, "isolated")

        assert "inherit_org_marketplaces=false" in str(exc_info.value)
        assert "required-plugin@shared" in str(exc_info.value)
        assert "shared" in str(exc_info.value)

    def test_inherit_true_with_org_marketplace_defaults_passes(self) -> None:
        """inherit_org_marketplaces=true works when defaults need org marketplaces."""
        from unittest.mock import patch

        from scc_cli.marketplace.resolve import resolve_effective_config
        from scc_cli.marketplace.schema import (
            ConfigSourceGitHub,
            DefaultsConfig,
            MarketplaceSourceGitHub,
            TeamConfig,
            TrustGrant,
        )

        config = make_org_config(
            defaults=DefaultsConfig(
                enabled_plugins=[
                    "required-plugin@shared",  # References org marketplace
                ],
            ),
            profiles={
                "standard": make_team_profile(
                    config_source=ConfigSourceGitHub(
                        source="github",
                        owner="team-standard",
                        repo="config",
                    ),
                    trust=TrustGrant(
                        inherit_org_marketplaces=True,  # Inherits org marketplaces
                    ),
                ),
            },
            marketplaces={
                "shared": MarketplaceSourceGitHub(
                    source="github",
                    owner="company",
                    repo="plugins",
                ),
            },
        )

        team_config = TeamConfig(
            schema_version="1.0.0",
            enabled_plugins=["team-plugin@claude-plugins-official"],
        )

        with patch("scc_cli.marketplace.resolve.fetch_team_config_with_fallback") as mock_fetch:
            from unittest.mock import MagicMock

            mock_result = MagicMock()
            mock_result.success = True
            mock_result.result.team_config = team_config.model_dump()
            mock_result.result.source_type = "github"
            mock_result.result.source_url = "github.com/team-standard/config"
            mock_result.result.commit_sha = "abc123"
            mock_result.result.etag = None
            mock_result.used_cache = False
            mock_result.is_stale = False
            mock_result.staleness_warning = None
            mock_fetch.return_value = mock_result

            # Should pass - inherit=true means org marketplace available
            result = resolve_effective_config(config, "standard")

        assert result.is_federated is True
        assert "shared" in result.marketplaces  # Org marketplace inherited

    def test_inherit_false_multiple_conflicting_plugins_all_reported(self) -> None:
        """When multiple defaults reference org marketplaces, all are reported."""
        from unittest.mock import patch

        from scc_cli.marketplace.resolve import resolve_effective_config
        from scc_cli.marketplace.schema import (
            ConfigSourceGitHub,
            DefaultsConfig,
            MarketplaceSourceGitHub,
            TeamConfig,
            TrustGrant,
        )
        from scc_cli.marketplace.trust import TrustViolationError

        config = make_org_config(
            defaults=DefaultsConfig(
                enabled_plugins=[
                    "plugin-a@shared",  # References org marketplace 'shared'
                    "plugin-b@internal",  # References org marketplace 'internal'
                    "plugin-c@shared",  # Another @shared reference
                ],
            ),
            profiles={
                "isolated": make_team_profile(
                    config_source=ConfigSourceGitHub(
                        source="github",
                        owner="team-isolated",
                        repo="config",
                    ),
                    trust=TrustGrant(
                        inherit_org_marketplaces=False,
                    ),
                ),
            },
            marketplaces={
                "shared": MarketplaceSourceGitHub(
                    source="github",
                    owner="company",
                    repo="plugins-shared",
                ),
                "internal": MarketplaceSourceGitHub(
                    source="github",
                    owner="company",
                    repo="plugins-internal",
                ),
            },
        )

        team_config = TeamConfig(
            schema_version="1.0.0",
            enabled_plugins=["team-plugin@claude-plugins-official"],
        )

        with patch("scc_cli.marketplace.resolve.fetch_team_config_with_fallback") as mock_fetch:
            from unittest.mock import MagicMock

            mock_result = MagicMock()
            mock_result.success = True
            mock_result.result.team_config = team_config.model_dump()
            mock_result.result.source_type = "github"
            mock_result.result.source_url = "github.com/team-isolated/config"
            mock_result.result.commit_sha = "abc123"
            mock_result.result.etag = None
            mock_result.used_cache = False
            mock_result.is_stale = False
            mock_result.staleness_warning = None
            mock_fetch.return_value = mock_result

            with pytest.raises(TrustViolationError) as exc_info:
                resolve_effective_config(config, "isolated")

        error_message = str(exc_info.value)
        # All conflicting plugins should be mentioned
        assert "plugin-a@shared" in error_message
        assert "plugin-b@internal" in error_message
        assert "plugin-c@shared" in error_message
        # Both conflicting marketplaces should be mentioned
        assert "shared" in error_message
        assert "internal" in error_message
