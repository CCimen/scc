"""
Unit tests for marketplace schema models.

Tests cover:
- MarketplaceSource discriminated union (GitHub, Git, URL, Directory)
- OrganizationConfig validation and federation
- DefaultsConfig allowlist and defaults behavior
- TeamProfile core fields and federation settings
- SecurityConfig policy fields

TDD: These tests are written BEFORE implementation.
"""

import pytest
from pydantic import ValidationError


def make_org_config(**kwargs):
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


def make_team_profile(**kwargs):
    from scc_cli.marketplace.schema import TeamProfile

    return TeamProfile(**kwargs)


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
        """Team profile with default fields only."""
        profile = make_team_profile()
        assert profile.description == ""
        assert profile.additional_plugins == []
        assert profile.additional_mcp_servers == []
        assert profile.network_policy is None
        assert profile.session.timeout_hours is None
        assert profile.session.auto_resume is None
        assert profile.delegation is None
        assert profile.config_source is None
        assert profile.trust is None

    def test_team_profile_with_fields(self) -> None:
        """Team profile with optional overrides."""
        from scc_cli.marketplace.schema import (
            MCPServerConfig,
            SessionConfig,
            TeamDelegationConfig,
        )

        profile = make_team_profile(
            description="High-security environment",
            additional_plugins=["security-scanner@internal"],
            additional_mcp_servers=[
                MCPServerConfig(
                    name="audit",
                    type="sse",
                    url="https://mcp.example.com",
                )
            ],
            network_policy="isolated",
            session=SessionConfig(timeout_hours=4, auto_resume=False),
            delegation=TeamDelegationConfig(allow_project_overrides=True),
        )
        assert profile.description == "High-security environment"
        assert profile.additional_plugins == ["security-scanner@internal"]
        assert profile.additional_mcp_servers[0].name == "audit"
        assert profile.network_policy == "isolated"
        assert profile.session.timeout_hours == 4
        assert profile.delegation is not None
        assert profile.delegation.allow_project_overrides is True


class TestSecurityConfig:
    """Tests for organization security configuration."""

    def test_empty_security(self) -> None:
        """Security config with defaults."""
        from scc_cli.marketplace.schema import SecurityConfig

        security = SecurityConfig()
        assert security.blocked_plugins == []
        assert security.blocked_mcp_servers == []
        assert security.allow_stdio_mcp is False
        assert security.allowed_stdio_prefixes == []
        assert security.safety_net is None

    def test_security_with_blocked_patterns(self) -> None:
        """Security config with explicit policy fields."""
        from scc_cli.marketplace.schema import SafetyNetConfig, SecurityConfig

        security = SecurityConfig(
            blocked_plugins=["risky-*@*", "*-deprecated@internal"],
            blocked_mcp_servers=["internal-*"],
            allow_stdio_mcp=True,
            allowed_stdio_prefixes=["/usr/local/bin"],
            safety_net=SafetyNetConfig(action="warn", block_reset_hard=False),
        )
        assert len(security.blocked_plugins) == 2
        assert "internal-*" in security.blocked_mcp_servers
        assert security.allow_stdio_mcp is True
        assert security.allowed_stdio_prefixes == ["/usr/local/bin"]
        assert security.safety_net is not None
        assert security.safety_net.action == "warn"


class TestOrganizationConfig:
    """Tests for complete organization configuration."""

    def test_minimal_org_config(self) -> None:
        """Minimal valid org config with required fields only."""
        from scc_cli.marketplace.schema import OrganizationInfo

        config = make_org_config(
            organization=OrganizationInfo(name="Sundsvall Municipality", id="sundsvall")
        )
        assert config.organization.name == "Sundsvall Municipality"
        assert config.organization.id == "sundsvall"
        assert config.schema_version == "1.0.0"
        assert config.marketplaces == {}
        assert config.profiles == {}

    def test_full_org_config(self) -> None:
        """Complete org config with all sections."""
        from scc_cli.marketplace.schema import (
            DefaultsConfig,
            MarketplaceSourceGitHub,
            OrganizationInfo,
            SecurityConfig,
            TeamProfile,
        )

        config = make_org_config(
            organization=OrganizationInfo(name="Sundsvall Municipality", id="sundsvall"),
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
                    description="Backend Team",
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
            "schema_version": "1.0.0",
            "organization": {
                "name": "Test Org",
                "id": "test-org",
            },
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
                    "description": "Backend Team",
                    "additional_plugins": ["api-tools@internal-plugins"],
                }
            },
        }
        config = OrganizationConfig.model_validate(data)
        assert config.organization.name == "Test Org"
        assert "internal-plugins" in config.marketplaces
        assert config.marketplaces["internal-plugins"].source == "github"

    def test_invalid_schema_version(self) -> None:
        """Schema version must match current schema."""
        from scc_cli.marketplace.schema import OrganizationConfig, OrganizationInfo

        with pytest.raises(ValidationError) as exc_info:
            OrganizationConfig(
                schema_version="2.0.0",
                organization=OrganizationInfo(name="Test", id="test"),
            )
        assert "schema_version" in str(exc_info.value)

    def test_org_config_to_dict(self) -> None:
        """Org config can be serialized back to dict."""
        from scc_cli.marketplace.schema import OrganizationInfo

        config = make_org_config(organization=OrganizationInfo(name="Test", id="test"))
        data = config.model_dump()
        assert data["organization"]["name"] == "Test"
        assert data["organization"]["id"] == "test"
        assert data["schema_version"] == "1.0.0"


# ─────────────────────────────────────────────────────────────────────────────
# Federation Models (ConfigSource, TrustGrant, TeamConfig)
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

        config = TeamConfig(schema_version="1.0.0")
        assert config.schema_version == "1.0.0"
        assert config.enabled_plugins == []
        assert config.disabled_plugins == []
        assert config.marketplaces == {}

    def test_team_config_with_plugins(self) -> None:
        """Team config with plugin lists."""
        from scc_cli.marketplace.schema import TeamConfig

        config = TeamConfig(
            schema_version="1.0.0",
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
            schema_version="1.0.0",
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
            "schema_version": "1.0.0",
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
        assert config.schema_version == "1.0.0"
        assert "team-mp" in config.marketplaces

    def test_team_config_invalid_schema_version(self) -> None:
        """Team config schema version must match current schema."""
        from scc_cli.marketplace.schema import TeamConfig

        with pytest.raises(ValidationError):
            TeamConfig(schema_version="2.0.0")


class TestTeamProfileWithFederation:
    """Tests for TeamProfile with federation fields."""

    def test_team_profile_with_config_source(self) -> None:
        """TeamProfile with external config source (federated)."""
        from scc_cli.marketplace.schema import (
            ConfigSourceGitHub,
            TeamProfile,
        )

        profile = TeamProfile(
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
        """TeamProfile without config_source uses inline config."""
        from scc_cli.marketplace.schema import TeamProfile

        profile = TeamProfile(
            description="Simple Team",
            additional_plugins=["tool@internal"],
        )
        assert profile.config_source is None
        assert profile.trust is None

    def test_org_config_with_federated_team(self) -> None:
        """OrganizationConfig with a federated team profile."""
        from scc_cli.marketplace.schema import (
            ConfigSourceGitHub,
            OrganizationInfo,
            TeamProfile,
            TrustGrant,
        )

        config = make_org_config(
            organization=OrganizationInfo(name="Sundsvall Municipality", id="sundsvall"),
            profiles={
                "backend": TeamProfile(
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
