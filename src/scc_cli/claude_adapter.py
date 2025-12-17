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
from typing import TYPE_CHECKING

from scc_cli.auth import is_remote_command_allowed, resolve_auth as _resolve_auth_impl
from scc_cli.profiles import get_marketplace_url

if TYPE_CHECKING:
    pass


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
    marketplace: dict,
    allow_command: bool = False,
) -> AuthResult | None:
    """Resolve marketplace auth spec to AuthResult.

    SECURITY: Command execution is disabled by default to prevent arbitrary
    code execution from untrusted remote org configs.

    Determines which standard env vars to also set based on marketplace type:
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


def build_claude_settings(
    profile: dict, marketplace: dict, org_id: str | None
) -> dict:
    """Build Claude Code settings payload.

    This is the ONLY function that knows Claude Code's settings format.

    Args:
        profile: Resolved profile with 'plugin' key
        marketplace: Resolved marketplace with URL info
        org_id: Organization ID for namespacing (falls back to marketplace name)

    Returns:
        Settings dict to inject into Claude Code
    """
    # Key is org_id if provided, otherwise marketplace name
    marketplace_key = org_id or marketplace.get("name", "default")
    marketplace_url = get_marketplace_url(marketplace)

    # Build enabled plugins list
    plugin_name = profile.get("plugin")
    enabled_plugins = []
    if plugin_name:
        enabled_plugins.append(f"{plugin_name}@{marketplace_key}")

    return {
        "extraKnownMarketplaces": {
            marketplace_key: {
                "name": marketplace.get("name", marketplace_key),
                "url": marketplace_url,
            }
        },
        "enabledPlugins": enabled_plugins,
    }


def get_settings_file_content(settings: dict) -> str:
    """Serialize settings for injection into container.

    Args:
        settings: Settings dict from build_claude_settings()

    Returns:
        Formatted JSON string
    """
    return json.dumps(settings, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# Credential Injection
# ═══════════════════════════════════════════════════════════════════════════════


def inject_credentials(
    marketplace: dict,
    docker_env: MutableMapping[str, str],
    allow_command: bool | None = None,
) -> None:
    """Inject marketplace credentials into Docker environment.

    SECURITY: By default, checks SCC_ALLOW_REMOTE_COMMANDS env var to determine
    if command: auth is allowed. This prevents arbitrary code execution from
    untrusted remote org configs.

    Uses setdefault to preserve any user-provided overrides.

    Args:
        marketplace: Marketplace config dict
        docker_env: Mutable dict to inject credentials into
        allow_command: Whether to allow command: auth specs. If None (default),
            uses is_remote_command_allowed() to check env var. Pass True/False
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
