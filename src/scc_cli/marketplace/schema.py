"""
Pydantic models for marketplace organization configuration.

This module defines the data models for:
- MarketplaceSource: Discriminated union for GitHub, Git, URL, Directory sources
- OrganizationConfig: Complete org config with marketplaces, defaults, profiles, security
- TeamProfile: Team-specific plugin configuration
- SecurityConfig: Organization security policies
- DefaultsConfig: Organization-wide defaults

All models support JSON serialization/deserialization via Pydantic v2.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

# ─────────────────────────────────────────────────────────────────────────────
# Marketplace Source Models
# ─────────────────────────────────────────────────────────────────────────────


class MarketplaceSourceGitHub(BaseModel):
    """GitHub repository marketplace source.

    Example:
        >>> source = MarketplaceSourceGitHub(
        ...     source="github",
        ...     owner="sundsvall",
        ...     repo="claude-plugins",
        ...     branch="main",
        ... )
    """

    source: Literal["github"]
    owner: Annotated[
        str,
        Field(
            pattern=r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?$",
            description="GitHub organization or user name",
        ),
    ]
    repo: Annotated[
        str,
        Field(
            pattern=r"^[a-zA-Z0-9._-]+$",
            description="GitHub repository name",
        ),
    ]
    branch: str = Field(default="main", description="Git branch to use")
    path: str = Field(default="/", description="Path within repository to marketplace root")
    headers: dict[str, str] | None = Field(
        default=None,
        description="HTTP headers for authentication (supports ${VAR} expansion)",
    )


class MarketplaceSourceGit(BaseModel):
    """Generic Git repository marketplace source.

    Supports both HTTPS and SSH URLs.

    Example:
        >>> source = MarketplaceSourceGit(
        ...     source="git",
        ...     url="https://gitlab.example.se/ai/plugins.git",
        ... )
    """

    source: Literal["git"]
    url: Annotated[
        str,
        Field(
            pattern=r"^(https://|git@)",
            description="Git clone URL (HTTPS or SSH)",
        ),
    ]
    branch: str = Field(default="main", description="Git branch to use")
    path: str = Field(default="/", description="Path within repository to marketplace root")


class MarketplaceSourceURL(BaseModel):
    """URL-based marketplace source.

    Downloads marketplace from HTTPS URL. HTTP is forbidden for security.

    Example:
        >>> source = MarketplaceSourceURL(
        ...     source="url",
        ...     url="https://plugins.sundsvall.se/marketplace.json",
        ... )
    """

    source: Literal["url"]
    url: Annotated[
        str,
        Field(
            pattern=r"^https://",
            description="HTTPS URL to marketplace manifest (HTTP forbidden)",
        ),
    ]
    headers: dict[str, str] | None = Field(
        default=None,
        description="HTTP headers for authentication (supports ${VAR} expansion)",
    )
    materialization_mode: Literal["self_contained", "metadata_only", "best_effort"] = Field(
        default="self_contained",
        description="How to fetch marketplace content",
    )


class MarketplaceSourceDirectory(BaseModel):
    """Local directory marketplace source.

    Points to a local filesystem path containing marketplace plugins.

    Example:
        >>> source = MarketplaceSourceDirectory(
        ...     source="directory",
        ...     path="/opt/scc/marketplaces/internal",
        ... )
    """

    source: Literal["directory"]
    path: str = Field(description="Local filesystem path (absolute or relative to org config)")


# Discriminated union for all marketplace source types
MarketplaceSource = Annotated[
    MarketplaceSourceGitHub
    | MarketplaceSourceGit
    | MarketplaceSourceURL
    | MarketplaceSourceDirectory,
    Field(discriminator="source"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Config Source Models (Phase 2: Federation)
# ─────────────────────────────────────────────────────────────────────────────


class ConfigSourceGitHub(BaseModel):
    """GitHub repository config source for team config files.

    Similar to MarketplaceSourceGitHub but with path defaulting to ""
    (empty string) instead of "/" to avoid path join issues.

    Example:
        >>> source = ConfigSourceGitHub(
        ...     source="github",
        ...     owner="sundsvall-backend",
        ...     repo="team-config",
        ... )
    """

    source: Literal["github"]
    owner: Annotated[
        str,
        Field(
            pattern=r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?$",
            description="GitHub organization or user name",
        ),
    ]
    repo: Annotated[
        str,
        Field(
            pattern=r"^[a-zA-Z0-9._-]+$",
            description="GitHub repository name",
        ),
    ]
    branch: str = Field(default="main", description="Git branch to use")
    path: str = Field(default="", description="Path within repository to config file")
    headers: dict[str, str] | None = Field(
        default=None,
        description="HTTP headers for authentication (supports ${VAR} expansion)",
    )


class ConfigSourceGit(BaseModel):
    """Generic Git repository config source for team config files.

    Similar to MarketplaceSourceGit but with path defaulting to ""
    (empty string) instead of "/" to avoid path join issues.

    Example:
        >>> source = ConfigSourceGit(
        ...     source="git",
        ...     url="https://gitlab.sundsvall.se/teams/backend-config.git",
        ... )
    """

    source: Literal["git"]
    url: Annotated[
        str,
        Field(
            pattern=r"^(https://|git@)",
            description="Git clone URL (HTTPS or SSH)",
        ),
    ]
    branch: str = Field(default="main", description="Git branch to use")
    path: str = Field(default="", description="Path within repository to config file")


class ConfigSourceURL(BaseModel):
    """URL-based config source for team config files.

    Downloads team config from HTTPS URL. HTTP is forbidden for security.

    Example:
        >>> source = ConfigSourceURL(
        ...     source="url",
        ...     url="https://teams.sundsvall.se/backend/team-config.json",
        ... )
    """

    source: Literal["url"]
    url: Annotated[
        str,
        Field(
            pattern=r"^https://",
            description="HTTPS URL to team config (HTTP forbidden)",
        ),
    ]
    headers: dict[str, str] | None = Field(
        default=None,
        description="HTTP headers for authentication (supports ${VAR} expansion)",
    )


# Discriminated union for all config source types
# Note: No directory source for security (teams can't reference local paths)
ConfigSource = Annotated[
    ConfigSourceGitHub | ConfigSourceGit | ConfigSourceURL,
    Field(discriminator="source"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Trust Grant Model (Phase 2: Federation)
# ─────────────────────────────────────────────────────────────────────────────


class TrustGrant(BaseModel):
    """Trust delegation from org to team.

    Controls what marketplaces a federated team can use:
    - inherit_org_marketplaces: Whether team can use org-defined marketplaces
    - allow_additional_marketplaces: Whether team can define own marketplaces
    - marketplace_source_patterns: URL patterns allowed for team marketplaces

    Example:
        >>> trust = TrustGrant(
        ...     inherit_org_marketplaces=True,
        ...     allow_additional_marketplaces=True,
        ...     marketplace_source_patterns=["github.com/sundsvall-*/**"],
        ... )
    """

    inherit_org_marketplaces: bool = Field(
        default=True,
        description="Whether team inherits org-level marketplace definitions",
    )
    allow_additional_marketplaces: bool = Field(
        default=False,
        description="Whether team can define additional marketplaces",
    )
    marketplace_source_patterns: list[str] = Field(
        default_factory=list,
        description="URL patterns (with globstar) allowed for team marketplaces",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Configuration Models
# ─────────────────────────────────────────────────────────────────────────────


class DefaultsConfig(BaseModel):
    """Organization-wide default settings.

    These settings apply to all teams unless overridden.

    Semantics for allowed_plugins:
        - None (missing): Unrestricted - all plugins allowed
        - []: Deny all - no plugins allowed
        - ["*"]: Explicit unrestricted via wildcard
        - ["pattern@marketplace"]: Specific whitelist with fnmatch patterns

    Example:
        >>> defaults = DefaultsConfig(
        ...     enabled_plugins=["code-review@internal"],
        ...     disabled_plugins=["debug-*"],
        ...     allowed_plugins=["*@internal"],  # Only internal marketplace
        ... )
    """

    # Governance field
    allowed_plugins: list[str] | None = Field(
        default=None,
        description="Allowed plugins (None=unrestricted, []=deny all, ['*']=explicit unrestricted)",
    )
    # Activation fields
    enabled_plugins: list[str] = Field(
        default_factory=list,
        description="Plugins enabled for all teams by default",
    )
    disabled_plugins: list[str] = Field(
        default_factory=list,
        description="Glob patterns for plugins disabled by default",
    )
    extra_marketplaces: list[str] = Field(
        default_factory=list,
        description="Marketplaces exposed to all teams (for browsing, not auto-enabling)",
    )


class TeamConfig(BaseModel):
    """External team configuration file (Phase 2: Federation).

    This is the schema for team-config.json files stored in team repos.
    Teams define their own plugins and marketplaces here.

    Example:
        >>> config = TeamConfig(
        ...     schema_version=1,
        ...     enabled_plugins=["custom-tool@team-mp"],
        ...     marketplaces={"team-mp": github_source},
        ... )
    """

    schema_version: Annotated[
        int,
        Field(description="Schema version for forward compatibility"),
    ]
    enabled_plugins: list[str] = Field(
        default_factory=list,
        description="Plugins enabled by this team config",
    )
    disabled_plugins: list[str] = Field(
        default_factory=list,
        description="Glob patterns for plugins to disable",
    )
    marketplaces: dict[str, MarketplaceSource] = Field(
        default_factory=dict,
        description="Team-defined marketplace sources",
    )

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, v: int) -> int:
        """Ensure schema version is supported."""
        if v != 1:
            msg = f"Unsupported schema_version: {v}. Only version 1 is supported."
            raise ValueError(msg)
        return v


class TeamProfile(BaseModel):
    """Team-specific configuration.

    Teams inherit org defaults and can add/disable plugins.
    allowed_plugins provides an allowlist filter (null = allow all).

    Phase 2 adds optional federation fields:
    - config_source: External config location (if set, team is federated)
    - trust: Trust delegation controls for federated teams

    Example:
        >>> profile = TeamProfile(
        ...     name="Backend Team",
        ...     additional_plugins=["api-tools@internal"],
        ... )
    """

    name: Annotated[str, Field(min_length=1, description="Team display name")]
    description: str = Field(default="", description="Team description for UI display")
    additional_plugins: list[str] = Field(
        default_factory=list,
        description="Plugins to add beyond org defaults",
    )
    disabled_plugins: list[str] = Field(
        default_factory=list,
        description="Glob patterns for plugins to remove from defaults",
    )
    allowed_plugins: list[str] | None = Field(
        default=None,
        description="Allowlist (null = allow all, [] = allow none)",
    )
    extra_marketplaces: list[str] = Field(
        default_factory=list,
        description="Additional marketplaces for this team",
    )
    # Phase 2: Federation fields
    config_source: ConfigSource | None = Field(
        default=None,
        description="External config source (if set, team is federated)",
    )
    trust: TrustGrant | None = Field(
        default=None,
        description="Trust delegation controls for federated teams",
    )


class SecurityConfig(BaseModel):
    """Organization security policies.

    Blocked plugins are enforced org-wide and cannot be overridden by teams.

    Example:
        >>> security = SecurityConfig(
        ...     blocked_plugins=["risky-tool@*"],
        ...     blocked_reason="Security review pending",
        ... )
    """

    blocked_plugins: list[str] = Field(
        default_factory=list,
        description="Glob patterns for plugins blocked org-wide",
    )
    blocked_reason: str = Field(
        default="Blocked by organization policy",
        description="Message shown when plugin is blocked",
    )
    allow_implicit_marketplaces: bool = Field(
        default=True,
        description="Whether to allow claude-plugins-official",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Organization Configuration
# ─────────────────────────────────────────────────────────────────────────────


class OrganizationConfig(BaseModel):
    """Complete organization configuration.

    This is the top-level model representing an org.json configuration file.

    Example:
        >>> config = OrganizationConfig(
        ...     name="Sundsvall Municipality",
        ...     schema_version=1,
        ...     marketplaces={"internal": source},
        ...     profiles={"backend": profile},
        ... )
    """

    name: Annotated[str, Field(min_length=1, description="Organization display name")]
    schema_version: Annotated[
        int,
        Field(
            description="Schema version for forward compatibility",
        ),
    ]
    marketplaces: dict[str, MarketplaceSource] = Field(
        default_factory=dict,
        description="Named marketplace sources (key = marketplace name)",
    )
    defaults: DefaultsConfig = Field(
        default_factory=DefaultsConfig,
        description="Organization-wide default settings",
    )
    profiles: dict[str, TeamProfile] = Field(
        default_factory=dict,
        description="Team profiles (key = profile name)",
    )
    security: SecurityConfig = Field(
        default_factory=SecurityConfig,
        description="Organization security policies",
    )

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, v: int) -> int:
        """Ensure schema version is supported."""
        if v != 1:
            msg = f"Unsupported schema_version: {v}. Only version 1 is supported."
            raise ValueError(msg)
        return v

    def get_team(self, team_id: str) -> TeamProfile | None:
        """Get a team profile by ID.

        Args:
            team_id: The profile key (not display name)

        Returns:
            TeamProfile if found, None otherwise
        """
        return self.profiles.get(team_id)

    def list_teams(self) -> list[str]:
        """List all team profile IDs.

        Returns:
            List of profile keys (not display names)
        """
        return list(self.profiles.keys())
