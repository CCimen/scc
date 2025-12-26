"""
Claude Code Settings Adapter.

This module is the ONLY place that knows about Claude Code's settings format.
If Claude Code changes its format, update ONLY this file + test_claude_adapter.py.

Current known format (may change):
- extraKnownMarketplaces: dict of marketplace configs
- enabledPlugins: list of "plugin@marketplace" strings

MAINTENANCE RULE: If Claude Code changes format, update ONLY:
1. claude_adapter.py - this file
2. test_claude_adapter.py - adapter output shape tests

No other module should import or reference extraKnownMarketplaces or enabledPlugins.
"""

from __future__ import annotations

import json
from collections.abc import MutableMapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from scc_cli.auth import is_remote_command_allowed
from scc_cli.auth import resolve_auth as _resolve_auth_impl
from scc_cli.profiles import get_marketplace_url

if TYPE_CHECKING:
    from scc_cli.profiles import EffectiveConfig, MCPServer


# ═══════════════════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class AuthResult:
    """Result of resolving marketplace auth.

    Attributes:
        env_name: Environment variable name for the token
        token: The actual token value
        also_set: Additional standard env var names to set (e.g., GITLAB_TOKEN)
    """

    env_name: str
    token: str
    also_set: tuple[str, ...] = ()


# ═══════════════════════════════════════════════════════════════════════════════
# Auth Resolution
# ═══════════════════════════════════════════════════════════════════════════════


def resolve_auth_with_name(
    auth_spec: str | None,
    allow_command: bool = False,
) -> tuple[str | None, str | None]:
    """Resolve auth spec to (token, env_name) tuple.

    SECURITY: Uses auth.py module with shell=False to prevent shell injection.
    Command execution is disabled by default (secure by default).

    Supports:
    - env:VAR_NAME - read from environment variable (always allowed)
    - command:CMD - execute command (only if allow_command=True)

    Args:
        auth_spec: Auth specification string or None
        allow_command: Whether to allow command: auth specs. Default False
            for security (prevents arbitrary command execution from untrusted
            sources like remote org config). Set True only for trusted sources
            or when user explicitly opts in via SCC_ALLOW_REMOTE_COMMANDS=1.

    Returns:
        Tuple of (token, env_name). Token is None if not available.
        env_name is always returned for env: specs (useful for error messages).
    """
    if not auth_spec:
        return (None, None)

    auth_spec = auth_spec.strip()
    if not auth_spec:
        return (None, None)

    # Extract env_name for env: specs (even if token is missing - for error messages)
    # This preserves the old behavior where env_name was always returned
    env_name_fallback = None
    if auth_spec.startswith("env:"):
        env_name_fallback = auth_spec[4:]

    try:
        # Use secure auth.py implementation (shell=False, validated binary)
        # Pass through allow_command to enforce trust model
        result = _resolve_auth_impl(auth_spec, allow_command=allow_command)
        if result:
            # Use result.env_name if available, otherwise use our fallback
            env_name = result.env_name if result.env_name else "SCC_AUTH_TOKEN"
            return (result.token, env_name)
        # Auth failed but we have env name from spec - return it for error messages
        if env_name_fallback:
            return (None, env_name_fallback)
        return (None, None)
    except (ValueError, RuntimeError):
        # Auth resolution failed - return env_name for error messages if available
        # ValueError: invalid auth spec format
        # RuntimeError: command execution failed
        if env_name_fallback:
            return (None, env_name_fallback)
        return (None, None)


def resolve_marketplace_auth(
    marketplace: dict[str, Any],
    allow_command: bool = False,
) -> AuthResult | None:
    """Resolve marketplace auth spec to AuthResult.

    SECURITY: Command execution is disabled by default to prevent arbitrary
    code execution from untrusted remote org configs.

    Determine which standard env vars to also set based on marketplace type:
    - gitlab: also set GITLAB_TOKEN
    - github: also set GITHUB_TOKEN

    Args:
        marketplace: Marketplace config dict
        allow_command: Whether to allow command: auth specs. Default False
            for security. Use is_remote_command_allowed() to check if user
            has opted in via SCC_ALLOW_REMOTE_COMMANDS=1.

    Returns:
        AuthResult with token and env var names, or None if no auth needed
    """
    auth_spec = marketplace.get("auth")
    if not auth_spec:
        return None

    token, env_name = resolve_auth_with_name(auth_spec, allow_command=allow_command)
    if not token or not env_name:
        return None

    # Determine standard env vars to also set based on marketplace type
    marketplace_type = marketplace.get("type", "").lower()
    also_set: tuple[str, ...] = ()

    if marketplace_type == "gitlab":
        also_set = ("GITLAB_TOKEN",)
    elif marketplace_type == "github":
        also_set = ("GITHUB_TOKEN",)
    # https type: no standard vars to set

    return AuthResult(env_name=env_name, token=token, also_set=also_set)


# ═══════════════════════════════════════════════════════════════════════════════
# Claude Code Settings Building
# ═══════════════════════════════════════════════════════════════════════════════


def _build_source_object(marketplace: dict[str, Any]) -> dict[str, Any]:
    """Build Claude Code's source object from SCC marketplace config.

    Handle the translation from SCC's org-config format to Claude's
    extraKnownMarketplaces source format.

    SCC type -> Claude source type mapping:
    - github -> github (requires 'repo')
    - gitlab -> git (builds URL from 'host' and 'repo')
    - https -> url (requires 'url')

    Args:
        marketplace: SCC marketplace config dict with 'type' and type-specific fields

    Returns:
        Claude source object with 'source' type and appropriate fields

    Raises:
        ValueError: If required fields are missing for the marketplace type
    """
    marketplace_type = marketplace.get("type", "").lower()

    if marketplace_type == "github":
        # GitHub requires 'repo' field
        repo = marketplace.get("repo")
        if not repo:
            raise ValueError(
                f"GitHub marketplace '{marketplace.get('name', 'unknown')}' "
                "missing required 'repo' field"
            )
        source = {"source": "github", "repo": repo}
        # Optional ref field
        if marketplace.get("ref"):
            source["ref"] = marketplace["ref"]
        return source

    elif marketplace_type == "gitlab":
        # GitLab maps to 'git' source type with constructed URL
        repo = marketplace.get("repo")
        host = marketplace.get("host", "gitlab.com")
        if not repo:
            raise ValueError(
                f"GitLab marketplace '{marketplace.get('name', 'unknown')}' "
                "missing required 'repo' field"
            )
        # Build HTTPS URL from host and repo
        url = f"https://{host}/{repo}"
        source = {"source": "git", "url": url}
        # Optional ref field
        if marketplace.get("ref"):
            source["ref"] = marketplace["ref"]
        return source

    elif marketplace_type == "https":
        # HTTPS maps to 'url' source type
        https_url: str | None = marketplace.get("url")
        if not https_url:
            raise ValueError(
                f"HTTPS marketplace '{marketplace.get('name', 'unknown')}' "
                "missing required 'url' field"
            )
        return {"source": "url", "url": https_url}

    else:
        # Unknown type - try to build URL-based source as fallback
        url = get_marketplace_url(marketplace)
        if url:
            return {"source": "url", "url": url}
        raise ValueError(
            f"Marketplace '{marketplace.get('name', 'unknown')}' has "
            f"unknown type '{marketplace_type}' and no fallback URL"
        )


def build_claude_settings(
    profile: dict[str, Any], marketplace: dict[str, Any], org_id: str | None
) -> dict[str, Any]:
    """Build Claude Code settings payload.

    This is the ONLY function that knows Claude Code's settings format.

    Claude's extraKnownMarketplaces format (as of Dec 2024):
    {
        "marketplaceKey": {
            "source": {"source": "github", "repo": "owner/repo", "ref": "main"}
        }
    }

    Args:
        profile: Resolved profile with 'plugin' key
        marketplace: Resolved marketplace with URL info
        org_id: Organization ID for namespacing (falls back to marketplace name)

    Returns:
        Settings dict to inject into Claude Code

    Raises:
        ValueError: If marketplace is missing required fields for its type
    """
    # Key is org_id if provided, otherwise marketplace name
    marketplace_key = org_id or marketplace.get("name", "default")

    # Build Claude's nested source object from SCC marketplace config
    source_object = _build_source_object(marketplace)

    # Build enabled plugins list
    plugin_name = profile.get("plugin")
    enabled_plugins = []
    if plugin_name:
        enabled_plugins.append(f"{plugin_name}@{marketplace_key}")

    return {
        "extraKnownMarketplaces": {
            marketplace_key: {
                "source": source_object,
            }
        },
        "enabledPlugins": enabled_plugins,
    }


def get_settings_file_content(settings: dict[str, Any]) -> str:
    """Serialize settings for injection into container.

    Args:
        settings: Settings dict from build_claude_settings()

    Returns:
        Formatted JSON string
    """
    return json.dumps(settings, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# V2 Settings Builder (EffectiveConfig)
# ═══════════════════════════════════════════════════════════════════════════════


def build_settings_from_effective_config(
    effective_config: EffectiveConfig,
    org_id: str | None = None,
    marketplace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build Claude Code settings from EffectiveConfig.

    This function translates the governance-aware EffectiveConfig
    to Claude Code's settings format.

    Args:
        effective_config: The computed effective configuration with
            plugins, MCP servers, and session settings
        org_id: Organization ID for namespacing (optional)
        marketplace: Marketplace config for source info (optional,
            needed if extraKnownMarketplaces is required)

    Returns:
        Settings dict ready for injection into Claude Code
    """

    settings: dict[str, Any] = {}

    # Build enabled plugins list
    marketplace_key = org_id or "default"
    enabled_plugins = []
    for plugin in effective_config.plugins:
        enabled_plugins.append(f"{plugin}@{marketplace_key}")

    if enabled_plugins:
        settings["enabledPlugins"] = enabled_plugins

    # Build MCP servers config
    if effective_config.mcp_servers:
        mcp_servers: dict[str, Any] = {}
        for server in effective_config.mcp_servers:
            server_config = _build_mcp_server_config(server)
            if server_config:
                mcp_servers[server.name] = server_config
        if mcp_servers:
            settings["mcpServers"] = mcp_servers

    # Include marketplace if provided
    if marketplace:
        try:
            source_object = _build_source_object(marketplace)
            settings["extraKnownMarketplaces"] = {marketplace_key: {"source": source_object}}
        except ValueError:
            # Skip if marketplace is incomplete
            pass

    return settings


def _build_mcp_server_config(server: MCPServer) -> dict[str, Any] | None:
    """Build Claude Code MCP server config from MCPServer dataclass.

    Claude Code MCP format (Dec 2024):
    - HTTP: {"type": "http", "url": "...", "headers": {...}}
    - SSE: {"type": "sse", "url": "...", "headers": {...}}
    - Stdio: {"type": "stdio", "command": "...", "args": [...], "env": {...}}

    Args:
        server: MCPServer dataclass instance

    Returns:
        Dict in Claude Code's mcpServers format, or None if invalid
    """
    if server.type == "sse":
        if not server.url:
            return None
        config: dict[str, Any] = {
            "type": "sse",
            "url": server.url,
        }
        if server.headers:
            config["headers"] = server.headers
        return config

    elif server.type == "http":
        if not server.url:
            return None
        config = {
            "type": "http",
            "url": server.url,
        }
        if server.headers:
            config["headers"] = server.headers
        return config

    elif server.type == "stdio":
        if not server.command:
            return None
        config = {
            "type": "stdio",
            "command": server.command,
        }
        if server.args:
            config["args"] = server.args
        if server.env:
            config["env"] = server.env
        return config

    else:
        return None


def translate_mcp_server(server: MCPServer) -> tuple[str, dict[str, Any]] | tuple[None, None]:
    """Translate MCPServer to Claude Code format.

    Return a tuple of (server_name, config_dict) for use in
    Claude Code's mcpServers settings.

    Args:
        server: MCPServer dataclass instance

    Returns:
        Tuple of (name, config) or (None, None) if invalid
    """
    config = _build_mcp_server_config(server)
    if config is None:
        return None, None
    return server.name, config


def build_mcp_servers(effective_config: EffectiveConfig) -> dict[str, Any]:
    """Build MCP servers dict from EffectiveConfig.

    Return the mcpServers dict in Claude Code's format:
    {"server-name": {"type": "...", "url": "..."}, ...}

    Args:
        effective_config: The computed effective configuration

    Returns:
        Dict mapping server names to their configurations
    """
    mcp_servers: dict[str, Any] = {}
    for server in effective_config.mcp_servers:
        name, config = translate_mcp_server(server)
        if name and config:
            mcp_servers[name] = config
    return mcp_servers


# ═══════════════════════════════════════════════════════════════════════════════
# Credential Injection
# ═══════════════════════════════════════════════════════════════════════════════


def inject_credentials(
    marketplace: dict[str, Any],
    docker_env: MutableMapping[str, str],
    allow_command: bool | None = None,
) -> None:
    """Inject marketplace credentials into Docker environment.

    SECURITY: By default, check SCC_ALLOW_REMOTE_COMMANDS env var to determine
    if command: auth is allowed. This prevents arbitrary code execution from
    untrusted remote org configs.

    Use setdefault to preserve any user-provided overrides.

    Args:
        marketplace: Marketplace config dict
        docker_env: Mutable dict to inject credentials into
        allow_command: Whether to allow command: auth specs. If None (default),
            use is_remote_command_allowed() to check env var. Pass True/False
            to override.
    """
    # Determine if command auth is allowed
    if allow_command is None:
        allow_command = is_remote_command_allowed()

    result = resolve_marketplace_auth(marketplace, allow_command=allow_command)
    if not result:
        return

    # Set the original env var name
    docker_env.setdefault(result.env_name, result.token)

    # Also set standard names for convenience
    for name in result.also_set:
        docker_env.setdefault(name, result.token)
