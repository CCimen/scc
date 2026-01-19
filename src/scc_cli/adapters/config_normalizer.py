"""Config normalization - converts raw dicts to typed config models.

Parse and validate configuration at load edges, then pass normalized
models inward to the application layer. This reduces stringly-typed
access and schema drift risk.
"""

from __future__ import annotations

from typing import Any

from scc_cli.ports.config_models import (
    DefaultsConfig,
    DelegationConfig,
    MarketplaceConfig,
    MCPServerConfig,
    NormalizedOrgConfig,
    NormalizedProjectConfig,
    NormalizedTeamConfig,
    NormalizedUserConfig,
    OrganizationInfo,
    OrganizationSource,
    ProjectsDelegation,
    SecurityConfig,
    SessionSettings,
    TeamDelegation,
    TeamsDelegation,
)


def normalize_user_config(raw: dict[str, Any]) -> NormalizedUserConfig:
    """Normalize a raw user config dict to typed model.

    Args:
        raw: Raw user config dict from JSON.

    Returns:
        NormalizedUserConfig with typed fields.
    """
    org_source = None
    raw_source = raw.get("organization_source")
    if raw_source and isinstance(raw_source, dict):
        org_source = OrganizationSource(
            url=raw_source.get("url", ""),
            auth=raw_source.get("auth"),
            auth_header=raw_source.get("auth_header"),
        )

    workspace_map = raw.get("workspace_team_map", {})
    if not isinstance(workspace_map, dict):
        workspace_map = {}

    return NormalizedUserConfig(
        selected_profile=raw.get("selected_profile"),
        standalone=bool(raw.get("standalone", False)),
        organization_source=org_source,
        workspace_team_map=workspace_map,
        onboarding_seen=bool(raw.get("onboarding_seen", False)),
    )


def _normalize_session_settings(raw: dict[str, Any] | None) -> SessionSettings:
    """Normalize session settings from raw dict."""
    if not raw:
        return SessionSettings()
    return SessionSettings(
        timeout_hours=raw.get("timeout_hours"),
        auto_resume=bool(raw.get("auto_resume", False)),
    )


def _normalize_mcp_server(raw: dict[str, Any]) -> MCPServerConfig:
    """Normalize a single MCP server config."""
    return MCPServerConfig(
        name=raw.get("name", ""),
        type=raw.get("type", "sse"),
        url=raw.get("url"),
        command=raw.get("command"),
        args=list(raw.get("args", [])),
        env=dict(raw.get("env", {})),
        headers=dict(raw.get("headers", {})),
    )


def _normalize_team_config(name: str, raw: dict[str, Any]) -> NormalizedTeamConfig:
    """Normalize a single team/profile config."""
    mcp_servers = tuple(_normalize_mcp_server(s) for s in raw.get("additional_mcp_servers", []))

    delegation_raw = raw.get("delegation", {})
    delegation = TeamDelegation(
        allow_project_overrides=bool(delegation_raw.get("allow_project_overrides", False)),
    )

    return NormalizedTeamConfig(
        name=name,
        description=raw.get("description", ""),
        plugin=raw.get("plugin"),
        marketplace=raw.get("marketplace"),
        additional_plugins=tuple(raw.get("additional_plugins", [])),
        additional_mcp_servers=mcp_servers,
        session=_normalize_session_settings(raw.get("session")),
        delegation=delegation,
    )


def _normalize_security(raw: dict[str, Any] | None) -> SecurityConfig:
    """Normalize security config."""
    if not raw:
        return SecurityConfig()
    return SecurityConfig(
        blocked_plugins=tuple(raw.get("blocked_plugins", [])),
        blocked_mcp_servers=tuple(raw.get("blocked_mcp_servers", [])),
        allow_stdio_mcp=bool(raw.get("allow_stdio_mcp", False)),
        allowed_stdio_prefixes=tuple(raw.get("allowed_stdio_prefixes", [])),
    )


def _normalize_defaults(raw: dict[str, Any] | None) -> DefaultsConfig:
    """Normalize defaults config."""
    if not raw:
        return DefaultsConfig()

    allowed_plugins = raw.get("allowed_plugins")
    allowed_mcp = raw.get("allowed_mcp_servers")

    return DefaultsConfig(
        enabled_plugins=tuple(raw.get("enabled_plugins", [])),
        disabled_plugins=tuple(raw.get("disabled_plugins", [])),
        allowed_plugins=tuple(allowed_plugins) if allowed_plugins is not None else None,
        allowed_mcp_servers=tuple(allowed_mcp) if allowed_mcp is not None else None,
        network_policy=raw.get("network_policy"),
        session=_normalize_session_settings(raw.get("session")),
    )


def _normalize_delegation(raw: dict[str, Any] | None) -> DelegationConfig:
    """Normalize delegation config."""
    if not raw:
        return DelegationConfig()

    teams_raw = raw.get("teams", {})
    projects_raw = raw.get("projects", {})

    return DelegationConfig(
        teams=TeamsDelegation(
            allow_additional_plugins=tuple(teams_raw.get("allow_additional_plugins", [])),
            allow_additional_mcp_servers=tuple(teams_raw.get("allow_additional_mcp_servers", [])),
        ),
        projects=ProjectsDelegation(
            inherit_team_delegation=bool(projects_raw.get("inherit_team_delegation", False)),
        ),
    )


def _normalize_marketplace(name: str, raw: dict[str, Any]) -> MarketplaceConfig:
    """Normalize a single marketplace config."""
    return MarketplaceConfig(
        name=name,
        source=raw.get("source", ""),
        owner=raw.get("owner"),
        repo=raw.get("repo"),
        branch=raw.get("branch"),
        url=raw.get("url"),
        host=raw.get("host"),
        path=raw.get("path"),
        headers=dict(raw.get("headers", {})),
    )


def normalize_org_config(raw: dict[str, Any]) -> NormalizedOrgConfig:
    """Normalize a raw organization config dict to typed model.

    Args:
        raw: Raw org config dict from JSON/cache.

    Returns:
        NormalizedOrgConfig with typed fields.
    """
    org_raw = raw.get("organization", {})
    org_info = OrganizationInfo(name=org_raw.get("name", ""))

    profiles_raw = raw.get("profiles", {})
    profiles = {name: _normalize_team_config(name, config) for name, config in profiles_raw.items()}

    marketplaces_raw = raw.get("marketplaces", {})
    marketplaces = {
        name: _normalize_marketplace(name, config) for name, config in marketplaces_raw.items()
    }

    return NormalizedOrgConfig(
        organization=org_info,
        security=_normalize_security(raw.get("security")),
        defaults=_normalize_defaults(raw.get("defaults")),
        delegation=_normalize_delegation(raw.get("delegation")),
        profiles=profiles,
        marketplaces=marketplaces,
    )


def normalize_project_config(raw: dict[str, Any] | None) -> NormalizedProjectConfig | None:
    """Normalize a raw project config dict to typed model.

    Args:
        raw: Raw project config dict from .scc.yaml, or None.

    Returns:
        NormalizedProjectConfig with typed fields, or None if no config.
    """
    if raw is None:
        return None

    mcp_servers = tuple(_normalize_mcp_server(s) for s in raw.get("additional_mcp_servers", []))

    return NormalizedProjectConfig(
        additional_plugins=tuple(raw.get("additional_plugins", [])),
        additional_mcp_servers=mcp_servers,
        session=_normalize_session_settings(raw.get("session")),
    )
