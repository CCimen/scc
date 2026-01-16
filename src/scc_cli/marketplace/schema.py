"""
Pydantic models for marketplace organization configuration.

These models mirror the org-v1 JSON schema and provide typed access for:
- Marketplace sources (github/git/url/directory)
- Federation config sources (github/git/url)
- Organization defaults, security, delegation, and profiles
- Federated team config files
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from scc_cli.core.constants import CURRENT_SCHEMA_VERSION


class StrictModel(BaseModel):
    """Base model with strict field validation."""

    model_config = ConfigDict(extra="forbid")


def normalize_org_config_data(config: dict[str, Any]) -> dict[str, Any]:
    """Normalize org config data for Pydantic validation.

    Removes JSON Schema metadata keys that are not part of the Pydantic models.
    """
    if "$schema" not in config:
        return config
    normalized = dict(config)
    normalized.pop("$schema", None)
    return normalized


# ─────────────────────────────────────────────────────────────────────────────
# Marketplace Source Models
# ─────────────────────────────────────────────────────────────────────────────


class MarketplaceSourceGitHub(StrictModel):
    """GitHub repository marketplace source."""

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


class MarketplaceSourceGit(StrictModel):
    """Generic Git repository marketplace source."""

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


class MarketplaceSourceURL(StrictModel):
    """URL-based marketplace source (HTTPS only)."""

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


class MarketplaceSourceDirectory(StrictModel):
    """Local directory marketplace source."""

    source: Literal["directory"]
    path: str = Field(description="Local filesystem path (absolute or relative to org config)")


MarketplaceSource = Annotated[
    MarketplaceSourceGitHub
    | MarketplaceSourceGit
    | MarketplaceSourceURL
    | MarketplaceSourceDirectory,
    Field(discriminator="source"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Config Source Models (Federation)
# ─────────────────────────────────────────────────────────────────────────────


class ConfigSourceGitHub(StrictModel):
    """GitHub repository config source for external team config files."""

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


class ConfigSourceGit(StrictModel):
    """Generic Git repository config source for external team config files."""

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


class ConfigSourceURL(StrictModel):
    """URL-based config source for external team config files (HTTPS only)."""

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


ConfigSource = Annotated[
    ConfigSourceGitHub | ConfigSourceGit | ConfigSourceURL,
    Field(discriminator="source"),
]


class TrustGrant(StrictModel):
    """Trust delegation from org to team."""

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


class SafetyNetConfig(StrictModel):
    """Configuration for the scc-safety-net plugin."""

    action: Literal["block", "warn", "allow"] = Field(
        default="block",
        description="Action mode: block (stop execution), warn (show warning but allow), allow (no checks)",
    )
    block_force_push: bool = Field(default=True, description="Block git push --force")
    block_reset_hard: bool = Field(default=True, description="Block git reset --hard")
    block_branch_force_delete: bool = Field(default=True, description="Block git branch -D")
    block_checkout_restore: bool = Field(default=True, description="Block git checkout/restore")
    block_clean: bool = Field(default=True, description="Block git clean -f")
    block_stash_destructive: bool = Field(default=True, description="Block git stash drop/clear")


class SecurityConfig(StrictModel):
    """Organization security policies."""

    blocked_plugins: list[str] = Field(
        default_factory=list,
        description="Glob patterns for plugins blocked org-wide",
    )
    blocked_mcp_servers: list[str] = Field(
        default_factory=list,
        description="Glob patterns for MCP servers blocked org-wide",
    )
    allow_stdio_mcp: bool = Field(
        default=False,
        description="Whether stdio-type MCP servers are allowed",
    )
    allowed_stdio_prefixes: list[str] = Field(
        default_factory=list,
        description="Absolute path prefixes where stdio commands must reside",
    )
    safety_net: SafetyNetConfig | None = Field(
        default=None,
        description="Safety net settings for the scc-safety-net plugin",
    )


class SessionConfig(StrictModel):
    """Session defaults and overrides."""

    timeout_hours: int | None = Field(
        default=None,
        description="Session timeout in hours",
        ge=1,
        le=24,
    )
    auto_resume: bool | None = Field(
        default=None,
        description="Whether sessions can be automatically resumed",
    )


class DefaultsConfig(StrictModel):
    """Organization-wide default settings."""

    allowed_plugins: list[str] | None = Field(
        default=None,
        description="Allowlist for plugins teams/projects can add",
    )
    allowed_mcp_servers: list[str] | None = Field(
        default=None,
        description="Allowlist patterns for MCP servers teams/projects can add",
    )
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
    cache_ttl_hours: int = Field(
        default=24,
        description="Organization config cache TTL in hours",
        ge=1,
        le=168,
    )
    network_policy: Literal["corp-proxy-only", "unrestricted", "isolated"] | None = Field(
        default=None,
        description="Network access policy",
    )
    session: SessionConfig = Field(
        default_factory=SessionConfig,
        description="Default session settings",
    )


class MCPServerConfig(StrictModel):
    """MCP server definition."""

    name: str = Field(description="MCP server name")
    type: Literal["sse", "stdio", "http"] = Field(description="MCP server connection type")
    url: str | None = Field(default=None, description="MCP server URL (sse/http)")
    command: str | None = Field(default=None, description="Command to run (stdio)")
    args: list[str] | None = Field(default=None, description="Command arguments (stdio)")
    env: dict[str, str] | None = Field(
        default=None,
        description="Environment variables for stdio servers",
    )
    headers: dict[str, str] | None = Field(
        default=None,
        description="HTTP headers for sse/http servers",
    )


class TeamDelegationConfig(StrictModel):
    """Team-level delegation to projects."""

    allow_project_overrides: bool = Field(
        default=False,
        description="Whether projects can add to this team's config",
    )


class TeamProfile(StrictModel):
    """Team-specific configuration."""

    description: str = Field(default="", description="Team description for UI display")
    additional_plugins: list[str] = Field(
        default_factory=list,
        description="Plugins to add beyond org defaults",
    )
    additional_mcp_servers: list[MCPServerConfig] = Field(
        default_factory=list,
        description="Additional MCP servers for this team",
    )
    network_policy: Literal["corp-proxy-only", "unrestricted", "isolated"] | None = Field(
        default=None,
        description="Override network policy for this team",
    )
    session: SessionConfig = Field(
        default_factory=SessionConfig,
        description="Team session overrides",
    )
    delegation: TeamDelegationConfig | None = Field(
        default=None,
        description="Team-level delegation to projects",
    )
    config_source: ConfigSource | None = Field(
        default=None,
        description="External config source (if set, team is federated)",
    )
    trust: TrustGrant | None = Field(
        default=None,
        description="Trust delegation controls for federated teams",
    )


class DelegationTeamsConfig(StrictModel):
    """Delegation rules for teams."""

    allow_additional_plugins: list[str] = Field(
        default_factory=list,
        description="Team names or patterns allowed to add plugins",
    )
    allow_additional_mcp_servers: list[str] = Field(
        default_factory=list,
        description="Team names or patterns allowed to add MCP servers",
    )


class DelegationProjectsConfig(StrictModel):
    """Project-level delegation settings."""

    inherit_team_delegation: bool = Field(
        default=False,
        description="Whether teams can delegate to projects (master switch)",
    )


class DelegationConfig(StrictModel):
    """Delegation rules controlling what teams/projects can add."""

    teams: DelegationTeamsConfig = Field(default_factory=DelegationTeamsConfig)
    projects: DelegationProjectsConfig = Field(default_factory=DelegationProjectsConfig)


class StatsConfig(StrictModel):
    """Usage statistics configuration."""

    enabled: bool | None = Field(
        default=None,
        description="Whether to collect usage statistics",
    )
    user_identity_mode: Literal["hash", "clear", "anonymous"] | None = Field(
        default=None,
        description="How to identify users in stats",
    )
    retention_days: int | None = Field(
        default=None,
        description="Number of days to retain stats",
        ge=1,
        le=365,
    )


class OrganizationInfo(StrictModel):
    """Organization identification."""

    name: str = Field(min_length=1, description="Display name of the organization")
    id: str = Field(pattern=r"^[a-z0-9-]+$", description="URL-safe organization identifier")
    contact: str | None = Field(default=None, description="Contact email or URL")


class OrganizationConfig(StrictModel):
    """Complete organization configuration."""

    schema_version: str = Field(description="Semantic version of the schema")
    min_cli_version: str | None = Field(
        default=None,
        description="Minimum SCC CLI version required",
    )
    organization: OrganizationInfo
    marketplaces: dict[str, MarketplaceSource] = Field(
        default_factory=dict,
        description="Named marketplace sources (key = marketplace name)",
    )
    defaults: DefaultsConfig = Field(
        default_factory=DefaultsConfig,
        description="Organization-wide default settings",
    )
    delegation: DelegationConfig = Field(
        default_factory=DelegationConfig,
        description="Delegation rules",
    )
    profiles: dict[str, TeamProfile] = Field(
        default_factory=dict,
        description="Team profiles (key = profile name)",
    )
    security: SecurityConfig = Field(
        default_factory=SecurityConfig,
        description="Organization security policies",
    )
    stats: StatsConfig | None = Field(
        default=None,
        description="Usage statistics configuration",
    )

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, v: str) -> str:
        if v != CURRENT_SCHEMA_VERSION:
            msg = f"Unsupported schema_version: {v}. Expected {CURRENT_SCHEMA_VERSION}."
            raise ValueError(msg)
        return v

    def get_team(self, team_id: str) -> TeamProfile | None:
        return self.profiles.get(team_id)

    def list_teams(self) -> list[str]:
        return list(self.profiles.keys())


class TeamConfig(StrictModel):
    """External team configuration file (federation)."""

    schema_version: Annotated[
        str,
        Field(description="Schema version (must match org schema version)"),
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
    def validate_schema_version(cls, v: str) -> str:
        if v != CURRENT_SCHEMA_VERSION:
            msg = f"Unsupported schema_version: {v}. Expected {CURRENT_SCHEMA_VERSION}."
            raise ValueError(msg)
        return v
