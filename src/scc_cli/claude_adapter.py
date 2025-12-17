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
import os
import subprocess
from collections.abc import MutableMapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

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


def resolve_auth_with_name(auth_spec: str | None) -> tuple[str | None, str | None]:
    """Resolve auth spec to (token, env_name) tuple.

    Supports:
    - env:VAR_NAME - read from environment variable
    - command:CMD - execute command and use output as token

    Args:
        auth_spec: Auth specification string or None

    Returns:
        Tuple of (token, env_name). Token is None if not available.
    """
    if not auth_spec:
        return (None, None)

    auth_spec = auth_spec.strip()
    if not auth_spec:
        return (None, None)

    # env:VAR_NAME format
    if auth_spec.startswith("env:"):
        env_name = auth_spec[4:]
        token = os.environ.get(env_name)
        if token:
            token = token.strip()
        return (token, env_name)

    # command:CMD format
    if auth_spec.startswith("command:"):
        cmd = auth_spec[8:]
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and result.stdout:
                token = result.stdout.strip()
                return (token, "SCC_AUTH_TOKEN")
            return (None, "SCC_AUTH_TOKEN")
        except (subprocess.TimeoutExpired, OSError):
            return (None, "SCC_AUTH_TOKEN")

    # Unknown format
    return (None, None)


def resolve_marketplace_auth(marketplace: dict) -> AuthResult | None:
    """Resolve marketplace auth spec to AuthResult.

    Determines which standard env vars to also set based on marketplace type:
    - gitlab: also set GITLAB_TOKEN
    - github: also set GITHUB_TOKEN

    Args:
        marketplace: Marketplace config dict

    Returns:
        AuthResult with token and env var names, or None if no auth needed
    """
    auth_spec = marketplace.get("auth")
    if not auth_spec:
        return None

    token, env_name = resolve_auth_with_name(auth_spec)
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
    marketplace: dict, docker_env: MutableMapping[str, str]
) -> None:
    """Inject marketplace credentials into Docker environment.

    Uses setdefault to preserve any user-provided overrides.

    Args:
        marketplace: Marketplace config dict
        docker_env: Mutable dict to inject credentials into
    """
    result = resolve_marketplace_auth(marketplace)
    if not result:
        return

    # Set the original env var name
    docker_env.setdefault(result.env_name, result.token)

    # Also set standard names for convenience
    for name in result.also_set:
        docker_env.setdefault(name, result.token)
