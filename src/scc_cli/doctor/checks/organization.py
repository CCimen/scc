"""Organization and marketplace health checks for doctor module.

Checks for org config reachability, marketplace auth, and credential injection.
"""

from __future__ import annotations

import json
from typing import Any, cast

from ..types import CheckResult


def load_cached_org_config() -> dict[str, Any] | None:
    """Load cached organization config from cache directory.

    Returns:
        Cached org config dict if valid, None otherwise.
    """
    from ... import config

    cache_file = config.CACHE_DIR / "org_config.json"

    if not cache_file.exists():
        return None

    try:
        content = cache_file.read_text()
        return cast(dict[str, Any], json.loads(content))
    except (json.JSONDecodeError, OSError):
        return None


def check_org_config_reachable() -> CheckResult | None:
    """Check if organization config URL is reachable.

    Returns:
        CheckResult if org config is configured, None for standalone mode.
    """
    from ... import config
    from ...remote import fetch_org_config

    user_config = config.load_user_config()

    # Skip for standalone mode
    if user_config.get("standalone"):
        return None

    # Skip if no org source configured
    org_source = user_config.get("organization_source")
    if not org_source:
        return None

    url = org_source.get("url")
    if not url:
        return None

    auth = org_source.get("auth")

    # Try to fetch org config
    try:
        org_config, etag, status = fetch_org_config(url, auth=auth, etag=None)
    except Exception as e:
        return CheckResult(
            name="Org Config",
            passed=False,
            message=f"Failed to fetch org config: {e}",
            fix_hint="Check network connection and URL",
            severity="error",
        )

    if status == 401:
        return CheckResult(
            name="Org Config",
            passed=False,
            message=f"Authentication required (401) for {url}",
            fix_hint="Configure auth with: scc setup",
            severity="error",
        )

    if status == 403:
        return CheckResult(
            name="Org Config",
            passed=False,
            message=f"Access denied (403) for {url}",
            fix_hint="Check your access permissions",
            severity="error",
        )

    if status != 200 or org_config is None:
        return CheckResult(
            name="Org Config",
            passed=False,
            message=f"Failed to fetch org config (status: {status})",
            fix_hint="Check URL and network connection",
            severity="error",
        )

    org_name = org_config.get("organization", {}).get("name", "Unknown")
    return CheckResult(
        name="Org Config",
        passed=True,
        message=f"Connected to: {org_name}",
    )


def check_marketplace_auth_available() -> CheckResult | None:
    """Check if marketplace authentication token is available.

    Returns:
        CheckResult if marketplace is configured, None otherwise.
    """
    from ... import config
    from ...remote import resolve_auth

    user_config = config.load_user_config()
    org_config = load_cached_org_config()

    # Skip if no org config
    if org_config is None:
        return None

    # Skip if no profile selected
    profile_name = user_config.get("selected_profile")
    if not profile_name:
        return None

    # Find the profile
    profiles = org_config.get("profiles", {})
    profile = profiles.get(profile_name)
    if not profile:
        return None

    # Find the marketplace (dict-based schema)
    marketplace_name = profile.get("marketplace")
    marketplaces = org_config.get("marketplaces", {})
    marketplace = marketplaces.get(marketplace_name)

    if marketplace is None:
        return CheckResult(
            name="Marketplace Auth",
            passed=False,
            message=f"Marketplace '{marketplace_name}' not found in org config",
            severity="error",
        )

    # Check auth requirement
    auth_spec = marketplace.get("auth")

    if auth_spec is None:
        return CheckResult(
            name="Marketplace Auth",
            passed=True,
            message="Public marketplace (no auth needed)",
        )

    # Try to resolve auth
    try:
        token = resolve_auth(auth_spec)
        if token:
            return CheckResult(
                name="Marketplace Auth",
                passed=True,
                message=f"{auth_spec} is set",
            )
        else:
            # Provide helpful hint based on auth type
            if auth_spec.startswith("env:"):
                var_name = auth_spec.split(":", 1)[1]
                hint = f"Set with: export {var_name}=your-token"
            else:
                cmd = auth_spec.split(":", 1)[1] if ":" in auth_spec else auth_spec
                hint = f"Run manually to debug: {cmd}"

            return CheckResult(
                name="Marketplace Auth",
                passed=False,
                message=f"{auth_spec} not set or invalid",
                fix_hint=hint,
                severity="error",
            )
    except Exception as e:
        return CheckResult(
            name="Marketplace Auth",
            passed=False,
            message=f"Auth resolution failed: {e}",
            severity="error",
        )


def check_credential_injection() -> CheckResult | None:
    """Check what credentials will be injected into Docker container.

    Shows env var NAMES only, never values. Prevents confusion about
    whether tokens are being passed to the container.

    Returns:
        CheckResult showing injection status, None if no profile.
    """
    from ... import config

    user_config = config.load_user_config()
    org_config = load_cached_org_config()

    # Skip if no org config
    if org_config is None:
        return None

    # Skip if no profile selected
    profile_name = user_config.get("selected_profile")
    if not profile_name:
        return None

    # Find the profile
    profiles = org_config.get("profiles", {})
    profile = profiles.get(profile_name)
    if not profile:
        return None

    # Find the marketplace (dict-based schema)
    marketplace_name = profile.get("marketplace")
    marketplaces = org_config.get("marketplaces", {})
    marketplace = marketplaces.get(marketplace_name)

    if marketplace is None:
        return None

    # Check auth requirement
    auth_spec = marketplace.get("auth")

    if auth_spec is None:
        return CheckResult(
            name="Container Injection",
            passed=True,
            message="No credentials needed (public marketplace)",
        )

    # Determine what env vars will be injected
    env_vars = []

    if auth_spec.startswith("env:"):
        var_name = auth_spec.split(":", 1)[1]
        env_vars.append(var_name)

        # Add standard vars based on marketplace type
        marketplace_type = marketplace.get("type")
        if marketplace_type == "gitlab" and var_name != "GITLAB_TOKEN":
            env_vars.append("GITLAB_TOKEN")
        elif marketplace_type == "github" and var_name != "GITHUB_TOKEN":
            env_vars.append("GITHUB_TOKEN")

    if env_vars:
        env_list = ", ".join(env_vars)
        return CheckResult(
            name="Container Injection",
            passed=True,
            message=f"Will inject [{env_list}] into Docker env",
        )
    else:
        return CheckResult(
            name="Container Injection",
            passed=True,
            message="Command-based auth (resolved at runtime)",
        )
