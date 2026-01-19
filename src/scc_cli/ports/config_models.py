"""Normalized typed config models for application layer.

These models provide type-safe access to configuration data. They are:
- Parsed/validated at config load edges (adapters/services)
- Passed inward to application code
- Used instead of raw dict[str, Any] access

The models are minimal - only fields that use cases need are included.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OrganizationSource:
    """Source configuration for fetching org config."""

    url: str
    auth: str | None = None
    auth_header: str | None = None


@dataclass(frozen=True)
class NormalizedUserConfig:
    """Normalized user configuration.

    Represents the local user's SCC configuration.
    """

    selected_profile: str | None = None
    standalone: bool = False
    organization_source: OrganizationSource | None = None
    workspace_team_map: dict[str, str] = field(default_factory=dict)
    onboarding_seen: bool = False


@dataclass(frozen=True)
class SessionSettings:
    """Session configuration settings."""

    timeout_hours: int | None = None
    auto_resume: bool = False


@dataclass(frozen=True)
class MCPServerConfig:
    """MCP server configuration."""

    name: str
    type: str = "sse"
    url: str | None = None
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TeamDelegation:
    """Team-level delegation settings."""

    allow_project_overrides: bool = False


@dataclass(frozen=True)
class NormalizedTeamConfig:
    """Normalized team/profile configuration.

    Represents a single team profile from the org config.
    """

    name: str
    description: str = ""
    plugin: str | None = None
    marketplace: str | None = None
    additional_plugins: tuple[str, ...] = ()
    additional_mcp_servers: tuple[MCPServerConfig, ...] = ()
    session: SessionSettings = field(default_factory=SessionSettings)
    delegation: TeamDelegation = field(default_factory=TeamDelegation)


@dataclass(frozen=True)
class SecurityConfig:
    """Organization security configuration."""

    blocked_plugins: tuple[str, ...] = ()
    blocked_mcp_servers: tuple[str, ...] = ()
    allow_stdio_mcp: bool = False
    allowed_stdio_prefixes: tuple[str, ...] = ()


@dataclass(frozen=True)
class DefaultsConfig:
    """Organization default configuration."""

    enabled_plugins: tuple[str, ...] = ()
    disabled_plugins: tuple[str, ...] = ()
    allowed_plugins: tuple[str, ...] | None = None
    allowed_mcp_servers: tuple[str, ...] | None = None
    network_policy: str | None = None
    session: SessionSettings = field(default_factory=SessionSettings)


@dataclass(frozen=True)
class TeamsDelegation:
    """Delegation rules for teams."""

    allow_additional_plugins: tuple[str, ...] = ()
    allow_additional_mcp_servers: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectsDelegation:
    """Delegation rules for projects."""

    inherit_team_delegation: bool = False


@dataclass(frozen=True)
class DelegationConfig:
    """Organization delegation configuration."""

    teams: TeamsDelegation = field(default_factory=TeamsDelegation)
    projects: ProjectsDelegation = field(default_factory=ProjectsDelegation)


@dataclass(frozen=True)
class MarketplaceConfig:
    """Marketplace source configuration."""

    name: str
    source: str
    owner: str | None = None
    repo: str | None = None
    branch: str | None = None
    url: str | None = None
    host: str | None = None
    path: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class OrganizationInfo:
    """Basic organization information."""

    name: str


@dataclass(frozen=True)
class NormalizedOrgConfig:
    """Normalized organization configuration.

    Represents the full organization config with all sections normalized.
    This is the primary config type used by application-layer use cases.
    """

    organization: OrganizationInfo
    security: SecurityConfig = field(default_factory=SecurityConfig)
    defaults: DefaultsConfig = field(default_factory=DefaultsConfig)
    delegation: DelegationConfig = field(default_factory=DelegationConfig)
    profiles: dict[str, NormalizedTeamConfig] = field(default_factory=dict)
    marketplaces: dict[str, MarketplaceConfig] = field(default_factory=dict)

    def get_profile(self, name: str) -> NormalizedTeamConfig | None:
        """Get a team profile by name."""
        return self.profiles.get(name)

    def list_profile_names(self) -> list[str]:
        """List all available profile names."""
        return list(self.profiles.keys())


@dataclass(frozen=True)
class NormalizedProjectConfig:
    """Normalized project configuration from .scc.yaml."""

    additional_plugins: tuple[str, ...] = ()
    additional_mcp_servers: tuple[MCPServerConfig, ...] = ()
    session: SessionSettings = field(default_factory=SessionSettings)
