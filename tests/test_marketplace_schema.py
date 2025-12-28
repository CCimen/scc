"""
Unit tests for marketplace schema models.

Tests cover:
- MarketplaceSource discriminated union (GitHub, Git, URL, Directory)
- OrganizationConfig validation
- TeamProfile with allowed_plugins null/array semantics
- SecurityConfig with blocked patterns
- DefaultsConfig with plugin lists

TDD: These tests are written BEFORE implementation.
"""

import pytest
from pydantic import ValidationError


class TestMarketplaceSourceGitHub:
    """Tests for GitHub marketplace source model."""

    def test_valid_github_source(self) -> None:
        """Valid GitHub source with required fields."""
        from scc_cli.marketplace.schema import MarketplaceSourceGitHub

        source = MarketplaceSourceGitHub(
            source="github",
            owner="sundsvall",
            repo="claude-plugins",
        )
        assert source.source == "github"
        assert source.owner == "sundsvall"
        assert source.repo == "claude-plugins"
        assert source.branch == "main"  # default
        assert source.path == "/"  # default

    def test_github_with_optional_fields(self) -> None:
        """GitHub source with all optional fields."""
        from scc_cli.marketplace.schema import MarketplaceSourceGitHub

        source = MarketplaceSourceGitHub(
            source="github",
            owner="sundsvall-kommun",
            repo="claude-plugins",
            branch="develop",
            path="/marketplaces/backend",
            headers={"Authorization": "Bearer ${GITHUB_TOKEN}"},
        )
        assert source.branch == "develop"
        assert source.path == "/marketplaces/backend"
        assert source.headers == {"Authorization": "Bearer ${GITHUB_TOKEN}"}

    def test_github_invalid_owner_pattern(self) -> None:
        """Owner must match GitHub username pattern."""
        from scc_cli.marketplace.schema import MarketplaceSourceGitHub

        with pytest.raises(ValidationError) as exc_info:
            MarketplaceSourceGitHub(
                source="github",
                owner="-invalid-",  # Can't start/end with hyphen
                repo="plugins",
            )
        assert "owner" in str(exc_info.value)

    def test_github_missing_required_fields(self) -> None:
        """GitHub source requires owner and repo."""
        from scc_cli.marketplace.schema import MarketplaceSourceGitHub

        with pytest.raises(ValidationError):
            MarketplaceSourceGitHub(source="github", owner="sundsvall")  # missing repo


class TestMarketplaceSourceGit:
    """Tests for generic Git marketplace source model."""

    def test_valid_git_https_url(self) -> None:
        """Git source with HTTPS URL."""
        from scc_cli.marketplace.schema import MarketplaceSourceGit

        source = MarketplaceSourceGit(
            source="git",
            url="https://gitlab.sundsvall.se/ai/plugins.git",
        )
        assert source.source == "git"
        assert source.url == "https://gitlab.sundsvall.se/ai/plugins.git"
        assert source.branch == "main"

    def test_valid_git_ssh_url(self) -> None:
        """Git source with SSH URL."""
        from scc_cli.marketplace.schema import MarketplaceSourceGit

        source = MarketplaceSourceGit(
            source="git",
            url="git@github.com:org/repo.git",
            branch="feature/new",
        )
        assert source.url == "git@github.com:org/repo.git"
        assert source.branch == "feature/new"

    def test_git_invalid_url_scheme(self) -> None:
        """Git URL must start with https:// or git@."""
        from scc_cli.marketplace.schema import MarketplaceSourceGit

        with pytest.raises(ValidationError) as exc_info:
            MarketplaceSourceGit(
                source="git",
                url="http://insecure.example.com/repo.git",
            )
        assert "url" in str(exc_info.value)


class TestMarketplaceSourceURL:
    """Tests for URL-based marketplace source model."""

    def test_valid_url_source(self) -> None:
        """Valid HTTPS URL source."""
        from scc_cli.marketplace.schema import MarketplaceSourceURL

        source = MarketplaceSourceURL(
            source="url",
            url="https://plugins.sundsvall.se/marketplace.json",
        )
        assert source.source == "url"
        assert source.url == "https://plugins.sundsvall.se/marketplace.json"
        assert source.materialization_mode == "self_contained"  # default

    def test_url_with_auth_headers(self) -> None:
        """URL source with authentication headers."""
        from scc_cli.marketplace.schema import MarketplaceSourceURL

        source = MarketplaceSourceURL(
            source="url",
            url="https://private.example.se/plugins.json",
            headers={"X-API-Key": "${PLUGINS_API_KEY}"},
            materialization_mode="metadata_only",
        )
        assert source.headers == {"X-API-Key": "${PLUGINS_API_KEY}"}
        assert source.materialization_mode == "metadata_only"

    def test_url_rejects_http(self) -> None:
        """URL source must use HTTPS, not HTTP."""
        from scc_cli.marketplace.schema import MarketplaceSourceURL

        with pytest.raises(ValidationError) as exc_info:
            MarketplaceSourceURL(
                source="url",
                url="http://insecure.example.com/plugins.json",
            )
        assert "url" in str(exc_info.value)


class TestMarketplaceSourceDirectory:
    """Tests for local directory marketplace source model."""

    def test_valid_directory_source(self) -> None:
        """Valid directory source with path."""
        from scc_cli.marketplace.schema import MarketplaceSourceDirectory

        source = MarketplaceSourceDirectory(
            source="directory",
            path="/opt/scc/marketplaces/internal",
        )
        assert source.source == "directory"
        assert source.path == "/opt/scc/marketplaces/internal"

    def test_directory_relative_path(self) -> None:
        """Directory source allows relative paths."""
        from scc_cli.marketplace.schema import MarketplaceSourceDirectory

        source = MarketplaceSourceDirectory(
            source="directory",
            path="./local-plugins",
        )
        assert source.path == "./local-plugins"


class TestMarketplaceSourceUnion:
    """Tests for discriminated union of marketplace sources."""

    def test_parse_github_source(self) -> None:
        """Parse dict to GitHub source via discriminated union."""
        from pydantic import TypeAdapter

        from scc_cli.marketplace.schema import MarketplaceSource

        adapter = TypeAdapter(MarketplaceSource)
        data = {
            "source": "github",
            "owner": "sundsvall",
            "repo": "plugins",
        }
        source = adapter.validate_python(data)
        assert source.source == "github"

    def test_parse_git_source(self) -> None:
        """Parse dict to Git source via discriminated union."""
        from pydantic import TypeAdapter

        from scc_cli.marketplace.schema import MarketplaceSource

        adapter = TypeAdapter(MarketplaceSource)
        data = {
            "source": "git",
            "url": "https://gitlab.example.se/ai/plugins.git",
        }
        source = adapter.validate_python(data)
        assert source.source == "git"

    def test_parse_url_source(self) -> None:
        """Parse dict to URL source via discriminated union."""
        from pydantic import TypeAdapter

        from scc_cli.marketplace.schema import MarketplaceSource

        adapter = TypeAdapter(MarketplaceSource)
        data = {
            "source": "url",
            "url": "https://plugins.example.se/marketplace.json",
        }
        source = adapter.validate_python(data)
        assert source.source == "url"

    def test_parse_directory_source(self) -> None:
        """Parse dict to directory source via discriminated union."""
        from pydantic import TypeAdapter

        from scc_cli.marketplace.schema import MarketplaceSource

        adapter = TypeAdapter(MarketplaceSource)
        data = {
            "source": "directory",
            "path": "/local/plugins",
        }
        source = adapter.validate_python(data)
        assert source.source == "directory"

    def test_unknown_source_type_fails(self) -> None:
        """Unknown source type should fail validation."""
        from pydantic import TypeAdapter

        from scc_cli.marketplace.schema import MarketplaceSource

        adapter = TypeAdapter(MarketplaceSource)
        with pytest.raises(ValidationError):
            adapter.validate_python({"source": "unknown", "path": "/x"})


class TestDefaultsConfig:
    """Tests for organization defaults configuration."""

    def test_empty_defaults(self) -> None:
        """Defaults can be empty (all optional fields)."""
        from scc_cli.marketplace.schema import DefaultsConfig

        defaults = DefaultsConfig()
        assert defaults.enabled_plugins == []
        assert defaults.disabled_plugins == []
        assert defaults.extra_marketplaces == []
        assert defaults.allowed_plugins is None  # None = unrestricted

    def test_defaults_with_plugins(self) -> None:
        """Defaults with enabled and disabled plugins."""
        from scc_cli.marketplace.schema import DefaultsConfig

        defaults = DefaultsConfig(
            enabled_plugins=["code-review@internal", "linter@internal"],
            disabled_plugins=["debug-*"],
            extra_marketplaces=["experimental"],
        )
        assert len(defaults.enabled_plugins) == 2
        assert "debug-*" in defaults.disabled_plugins

    # ─────────────────────────────────────────────────────────────────────────
    # Task 7: Targeted field tests for allowed_plugins governance semantics
    # ─────────────────────────────────────────────────────────────────────────

    def test_allowed_plugins_none_means_unrestricted(self) -> None:
        """None allowed_plugins means no restrictions (runtime default).

        Semantic: Missing/None = all plugins are allowed (unrestricted).
        This is the most permissive setting.
        """
        from scc_cli.marketplace.schema import DefaultsConfig

        defaults = DefaultsConfig(allowed_plugins=None)
        assert defaults.allowed_plugins is None

    def test_allowed_plugins_empty_list_means_deny_all(self) -> None:
        """Empty allowed_plugins list means no plugins are allowed (deny all).

        Semantic: [] = explicit deny-all, blocks all plugins.
        This is the most restrictive setting.
        """
        from scc_cli.marketplace.schema import DefaultsConfig

        defaults = DefaultsConfig(allowed_plugins=[])
        assert defaults.allowed_plugins == []

    def test_allowed_plugins_wildcard_means_explicit_unrestricted(self) -> None:
        """Wildcard ["*"] means explicit unrestricted (allow all).

        Semantic: ["*"] = explicit allow-all via fnmatch pattern.
        Functionally equivalent to None but explicitly configured.
        """
        from scc_cli.marketplace.schema import DefaultsConfig

        defaults = DefaultsConfig(allowed_plugins=["*"])
        assert defaults.allowed_plugins == ["*"]

    def test_allowed_plugins_specific_patterns(self) -> None:
        """Allowed plugins can contain specific patterns.

        Semantic: Specific patterns create a whitelist filter.
        Only plugins matching at least one pattern are allowed.
        """
        from scc_cli.marketplace.schema import DefaultsConfig

        defaults = DefaultsConfig(
            allowed_plugins=["*@internal", "code-review@*", "approved-tool@official"]
        )
        assert defaults.allowed_plugins is not None
        assert len(defaults.allowed_plugins) == 3
        assert "*@internal" in defaults.allowed_plugins

    def test_extra_marketplaces_is_list_of_strings(self) -> None:
        """extra_marketplaces accepts list of marketplace names (not dicts).

        Semantic: List of marketplace name references (strings).
        These reference marketplaces defined at org level - prevents shadow IT.
        """
        from scc_cli.marketplace.schema import DefaultsConfig

        defaults = DefaultsConfig(extra_marketplaces=["official", "internal", "experimental"])
        assert defaults.extra_marketplaces == ["official", "internal", "experimental"]
        assert all(isinstance(mp, str) for mp in defaults.extra_marketplaces)


class TestTeamProfile:
    """Tests for team profile model."""

    def test_minimal_team_profile(self) -> None:
        """Team profile with only required name."""
        from scc_cli.marketplace.schema import TeamProfile

        profile = TeamProfile(name="Backend Team")
        assert profile.name == "Backend Team"
        assert profile.description == ""
        assert profile.additional_plugins == []
        assert profile.allowed_plugins is None  # null means allow all

    def test_team_profile_with_all_fields(self) -> None:
        """Team profile with all optional fields."""
        from scc_cli.marketplace.schema import TeamProfile

        profile = TeamProfile(
            name="Security Team",
            description="High-security environment with strict plugin allowlist",
            additional_plugins=["security-scanner@internal"],
            disabled_plugins=["*debug*"],
            allowed_plugins=["security-scanner@internal", "code-review@internal"],
            extra_marketplaces=["security-tools"],
        )
        assert profile.name == "Security Team"
        assert profile.allowed_plugins is not None
        assert len(profile.allowed_plugins) == 2

    def test_allowed_plugins_null_means_allow_all(self) -> None:
        """null allowed_plugins means no restrictions."""
        from scc_cli.marketplace.schema import TeamProfile

        profile = TeamProfile(name="Open Team", allowed_plugins=None)
        assert profile.allowed_plugins is None

    def test_allowed_plugins_empty_list_means_allow_none(self) -> None:
        """Empty allowed_plugins list means block all additional."""
        from scc_cli.marketplace.schema import TeamProfile

        profile = TeamProfile(name="Locked Team", allowed_plugins=[])
        assert profile.allowed_plugins == []

    def test_allowed_plugins_wildcard_means_allow_all(self) -> None:
        """Wildcard ["*"] means explicit unrestricted (allow all).

        Semantic: ["*"] = explicit allow-all via fnmatch pattern.
        Functionally equivalent to None but explicitly configured.
        """
        from scc_cli.marketplace.schema import TeamProfile

        profile = TeamProfile(name="Open Team", allowed_plugins=["*"])
        assert profile.allowed_plugins == ["*"]


class TestSecurityConfig:
    """Tests for organization security configuration."""

    def test_empty_security(self) -> None:
        """Security config with defaults."""
        from scc_cli.marketplace.schema import SecurityConfig

        security = SecurityConfig()
        assert security.blocked_plugins == []
        assert security.blocked_reason == "Blocked by organization policy"
        assert security.allow_implicit_marketplaces is True

    def test_security_with_blocked_patterns(self) -> None:
        """Security config with blocked plugin patterns."""
        from scc_cli.marketplace.schema import SecurityConfig

        security = SecurityConfig(
            blocked_plugins=["risky-*@*", "*-deprecated@internal"],
            blocked_reason="Security review pending - see ticket SEC-123",
            allow_implicit_marketplaces=False,
        )
        assert len(security.blocked_plugins) == 2
        assert "SEC-123" in security.blocked_reason
        assert security.allow_implicit_marketplaces is False


class TestOrganizationConfig:
    """Tests for complete organization configuration."""

    def test_minimal_org_config(self) -> None:
        """Minimal valid org config with required fields only."""
        from scc_cli.marketplace.schema import OrganizationConfig

        config = OrganizationConfig(
            name="Sundsvall Municipality",
            schema_version=1,
        )
        assert config.name == "Sundsvall Municipality"
        assert config.schema_version == 1
        assert config.marketplaces == {}
        assert config.profiles == {}

    def test_full_org_config(self) -> None:
        """Complete org config with all sections."""
        from scc_cli.marketplace.schema import (
            DefaultsConfig,
            MarketplaceSourceGitHub,
            OrganizationConfig,
            SecurityConfig,
            TeamProfile,
        )

        config = OrganizationConfig(
            name="Sundsvall Municipality",
            schema_version=1,
            marketplaces={
                "internal": MarketplaceSourceGitHub(
                    source="github",
                    owner="sundsvall",
                    repo="claude-plugins",
                )
            },
            defaults=DefaultsConfig(
                enabled_plugins=["code-review@internal"],
            ),
            profiles={
                "backend": TeamProfile(
                    name="Backend Team",
                    additional_plugins=["api-tools@internal"],
                ),
            },
            security=SecurityConfig(
                blocked_plugins=["risky-tool@*"],
            ),
        )
        assert "internal" in config.marketplaces
        assert "backend" in config.profiles
        assert len(config.security.blocked_plugins) == 1

    def test_org_config_from_json(self) -> None:
        """Parse org config from JSON dict."""
        from scc_cli.marketplace.schema import OrganizationConfig

        data = {
            "name": "Test Org",
            "schema_version": 1,
            "marketplaces": {
                "internal-plugins": {
                    "source": "github",
                    "owner": "test-org",
                    "repo": "plugins",
                }
            },
            "defaults": {
                "enabled_plugins": ["code-review@internal-plugins"],
            },
            "profiles": {
                "backend": {
                    "name": "Backend Team",
                    "additional_plugins": ["api-tools@internal-plugins"],
                }
            },
        }
        config = OrganizationConfig.model_validate(data)
        assert config.name == "Test Org"
        assert "internal-plugins" in config.marketplaces
        assert config.marketplaces["internal-plugins"].source == "github"

    def test_invalid_schema_version(self) -> None:
        """Schema version must be 1."""
        from scc_cli.marketplace.schema import OrganizationConfig

        with pytest.raises(ValidationError) as exc_info:
            OrganizationConfig(
                name="Test",
                schema_version=2,  # Not supported yet
            )
        assert "schema_version" in str(exc_info.value)

    def test_org_config_to_dict(self) -> None:
        """Org config can be serialized back to dict."""
        from scc_cli.marketplace.schema import OrganizationConfig

        config = OrganizationConfig(
            name="Test",
            schema_version=1,
        )
        data = config.model_dump()
        assert data["name"] == "Test"
        assert data["schema_version"] == 1


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: Federation Models (ConfigSource, TrustGrant, TeamConfig)
# ─────────────────────────────────────────────────────────────────────────────


class TestConfigSourceGitHub:
    """Tests for GitHub config source (for team config files)."""

    def test_valid_github_config_source(self) -> None:
        """Valid GitHub config source with required fields."""
        from scc_cli.marketplace.schema import ConfigSourceGitHub

        source = ConfigSourceGitHub(
            source="github",
            owner="sundsvall",
            repo="team-configs",
        )
        assert source.source == "github"
        assert source.owner == "sundsvall"
        assert source.repo == "team-configs"
        assert source.branch == "main"  # default
        assert source.path == ""  # default is empty, not "/"

    def test_github_config_with_path(self) -> None:
        """GitHub config source with subdirectory path."""
        from scc_cli.marketplace.schema import ConfigSourceGitHub

        source = ConfigSourceGitHub(
            source="github",
            owner="sundsvall",
            repo="team-configs",
            branch="develop",
            path="teams/backend",
        )
        assert source.path == "teams/backend"
        assert source.branch == "develop"

    def test_github_config_with_headers(self) -> None:
        """GitHub config source with auth headers."""
        from scc_cli.marketplace.schema import ConfigSourceGitHub

        source = ConfigSourceGitHub(
            source="github",
            owner="sundsvall",
            repo="team-configs",
            headers={"Authorization": "Bearer ${GITHUB_TOKEN}"},
        )
        assert source.headers == {"Authorization": "Bearer ${GITHUB_TOKEN}"}


class TestConfigSourceGit:
    """Tests for generic Git config source."""

    def test_valid_git_config_source(self) -> None:
        """Valid Git config source."""
        from scc_cli.marketplace.schema import ConfigSourceGit

        source = ConfigSourceGit(
            source="git",
            url="https://gitlab.sundsvall.se/ai/team-configs.git",
        )
        assert source.source == "git"
        assert source.branch == "main"
        assert source.path == ""  # default is empty

    def test_git_config_ssh_url(self) -> None:
        """Git config source with SSH URL."""
        from scc_cli.marketplace.schema import ConfigSourceGit

        source = ConfigSourceGit(
            source="git",
            url="git@github.com:org/team-configs.git",
            branch="main",
            path="backend",
        )
        assert source.url == "git@github.com:org/team-configs.git"
        assert source.path == "backend"


class TestConfigSourceURL:
    """Tests for URL-based config source."""

    def test_valid_url_config_source(self) -> None:
        """Valid HTTPS URL config source."""
        from scc_cli.marketplace.schema import ConfigSourceURL

        source = ConfigSourceURL(
            source="url",
            url="https://teams.sundsvall.se/backend/team-config.json",
        )
        assert source.source == "url"
        assert source.url == "https://teams.sundsvall.se/backend/team-config.json"

    def test_url_config_rejects_http(self) -> None:
        """URL config source must use HTTPS."""
        from scc_cli.marketplace.schema import ConfigSourceURL

        with pytest.raises(ValidationError) as exc_info:
            ConfigSourceURL(
                source="url",
                url="http://insecure.example.com/config.json",
            )
        assert "url" in str(exc_info.value)


class TestConfigSourceUnion:
    """Tests for discriminated union of config sources."""

    def test_parse_github_config_source(self) -> None:
        """Parse dict to GitHub config source."""
        from pydantic import TypeAdapter

        from scc_cli.marketplace.schema import ConfigSource

        adapter = TypeAdapter(ConfigSource)
        data = {
            "source": "github",
            "owner": "sundsvall",
            "repo": "team-configs",
        }
        source = adapter.validate_python(data)
        assert source.source == "github"

    def test_parse_git_config_source(self) -> None:
        """Parse dict to Git config source."""
        from pydantic import TypeAdapter

        from scc_cli.marketplace.schema import ConfigSource

        adapter = TypeAdapter(ConfigSource)
        data = {
            "source": "git",
            "url": "https://gitlab.example.se/team-configs.git",
        }
        source = adapter.validate_python(data)
        assert source.source == "git"

    def test_parse_url_config_source(self) -> None:
        """Parse dict to URL config source."""
        from pydantic import TypeAdapter

        from scc_cli.marketplace.schema import ConfigSource

        adapter = TypeAdapter(ConfigSource)
        data = {
            "source": "url",
            "url": "https://config.example.se/team.json",
        }
        source = adapter.validate_python(data)
        assert source.source == "url"


class TestTrustGrant:
    """Tests for TrustGrant model (org's trust delegation to teams)."""

    def test_default_trust_grant(self) -> None:
        """Default TrustGrant allows inheritance but no additions."""
        from scc_cli.marketplace.schema import TrustGrant

        trust = TrustGrant()
        assert trust.inherit_org_marketplaces is True
        assert trust.allow_additional_marketplaces is False
        assert trust.marketplace_source_patterns == []

    def test_trust_grant_with_patterns(self) -> None:
        """TrustGrant with marketplace source patterns."""
        from scc_cli.marketplace.schema import TrustGrant

        trust = TrustGrant(
            inherit_org_marketplaces=True,
            allow_additional_marketplaces=True,
            marketplace_source_patterns=[
                "github.com/sundsvall/**",
                "gitlab.sundsvall.se/**",
            ],
        )
        assert trust.allow_additional_marketplaces is True
        assert len(trust.marketplace_source_patterns) == 2

    def test_trust_grant_deny_inheritance(self) -> None:
        """TrustGrant can deny org marketplace inheritance."""
        from scc_cli.marketplace.schema import TrustGrant

        trust = TrustGrant(
            inherit_org_marketplaces=False,
            allow_additional_marketplaces=True,
        )
        assert trust.inherit_org_marketplaces is False


class TestTeamConfig:
    """Tests for TeamConfig model (external team config file)."""

    def test_minimal_team_config(self) -> None:
        """Minimal valid team config."""
        from scc_cli.marketplace.schema import TeamConfig

        config = TeamConfig(schema_version=1)
        assert config.schema_version == 1
        assert config.enabled_plugins == []
        assert config.disabled_plugins == []
        assert config.marketplaces == {}

    def test_team_config_with_plugins(self) -> None:
        """Team config with plugin lists."""
        from scc_cli.marketplace.schema import TeamConfig

        config = TeamConfig(
            schema_version=1,
            enabled_plugins=["custom-tool@team-plugins"],
            disabled_plugins=["debug-*"],
        )
        assert "custom-tool@team-plugins" in config.enabled_plugins
        assert "debug-*" in config.disabled_plugins

    def test_team_config_with_marketplaces(self) -> None:
        """Team config with own marketplace definitions."""
        from scc_cli.marketplace.schema import (
            MarketplaceSourceGitHub,
            TeamConfig,
        )

        config = TeamConfig(
            schema_version=1,
            marketplaces={
                "team-plugins": MarketplaceSourceGitHub(
                    source="github",
                    owner="sundsvall-backend",
                    repo="claude-plugins",
                )
            },
            enabled_plugins=["api-utils@team-plugins"],
        )
        assert "team-plugins" in config.marketplaces
        assert config.marketplaces["team-plugins"].source == "github"

    def test_team_config_from_json(self) -> None:
        """Parse team config from JSON dict."""
        from scc_cli.marketplace.schema import TeamConfig

        data = {
            "schema_version": 1,
            "enabled_plugins": ["tool-a@team-mp"],
            "marketplaces": {
                "team-mp": {
                    "source": "github",
                    "owner": "backend-team",
                    "repo": "plugins",
                }
            },
        }
        config = TeamConfig.model_validate(data)
        assert config.schema_version == 1
        assert "team-mp" in config.marketplaces

    def test_team_config_invalid_schema_version(self) -> None:
        """Team config schema version must be 1."""
        from scc_cli.marketplace.schema import TeamConfig

        with pytest.raises(ValidationError):
            TeamConfig(schema_version=2)


class TestTeamProfileWithFederation:
    """Tests for TeamProfile with federation fields."""

    def test_team_profile_with_config_source(self) -> None:
        """TeamProfile with external config source (federated)."""
        from scc_cli.marketplace.schema import (
            ConfigSourceGitHub,
            TeamProfile,
        )

        profile = TeamProfile(
            name="Backend Team",
            config_source=ConfigSourceGitHub(
                source="github",
                owner="sundsvall-backend",
                repo="team-config",
            ),
        )
        assert profile.config_source is not None
        assert profile.config_source.source == "github"

    def test_team_profile_with_trust_grant(self) -> None:
        """TeamProfile with trust grant configuration."""
        from scc_cli.marketplace.schema import TeamProfile, TrustGrant

        profile = TeamProfile(
            name="Backend Team",
            trust=TrustGrant(
                inherit_org_marketplaces=True,
                allow_additional_marketplaces=True,
                marketplace_source_patterns=["github.com/sundsvall/**"],
            ),
        )
        assert profile.trust is not None
        assert profile.trust.allow_additional_marketplaces is True

    def test_team_profile_federated_with_trust(self) -> None:
        """Federated team profile with both config_source and trust."""
        from scc_cli.marketplace.schema import (
            ConfigSourceGitHub,
            TeamProfile,
            TrustGrant,
        )

        profile = TeamProfile(
            name="Backend Team",
            description="Team manages own config with org oversight",
            config_source=ConfigSourceGitHub(
                source="github",
                owner="sundsvall-backend",
                repo="team-config",
            ),
            trust=TrustGrant(
                inherit_org_marketplaces=True,
                allow_additional_marketplaces=True,
                marketplace_source_patterns=["github.com/sundsvall-*/**"],
            ),
        )
        assert profile.config_source is not None
        assert profile.trust is not None

    def test_team_profile_inline_without_federation(self) -> None:
        """TeamProfile without config_source uses inline config (Phase 1)."""
        from scc_cli.marketplace.schema import TeamProfile

        profile = TeamProfile(
            name="Simple Team",
            additional_plugins=["tool@internal"],
        )
        # No config_source = inline/Phase 1 mode
        assert profile.config_source is None
        assert profile.trust is None

    def test_org_config_with_federated_team(self) -> None:
        """OrganizationConfig with a federated team profile."""
        from scc_cli.marketplace.schema import (
            ConfigSourceGitHub,
            OrganizationConfig,
            TeamProfile,
            TrustGrant,
        )

        config = OrganizationConfig(
            name="Sundsvall Municipality",
            schema_version=1,
            profiles={
                "backend": TeamProfile(
                    name="Backend Team",
                    config_source=ConfigSourceGitHub(
                        source="github",
                        owner="sundsvall-backend",
                        repo="team-config",
                    ),
                    trust=TrustGrant(
                        allow_additional_marketplaces=True,
                        marketplace_source_patterns=["github.com/sundsvall-*/**"],
                    ),
                ),
            },
        )
        backend = config.get_team("backend")
        assert backend is not None
        assert backend.config_source is not None
