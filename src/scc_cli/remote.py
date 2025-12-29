"""
Remote config fetching with auth and caching.

Handle all HTTP concerns for fetching org config:
- URL validation (HTTPS only)
- Auth resolution (env:VAR, command:CMD)
- ETag-based conditional fetching
- Local cache with TTL

Module Separation: This module does HTTP only, no business logic.
Business logic is in profiles.py, format knowledge is in claude_adapter.py.
"""

from __future__ import annotations

import hashlib
import json
import stat
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import requests

from scc_cli.auth import is_remote_command_allowed
from scc_cli.auth import resolve_auth as _resolve_auth_impl
from scc_cli.output_mode import print_human
from scc_cli.utils.locks import file_lock, lock_path

if TYPE_CHECKING:
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# XDG Base Directory Paths
# ═══════════════════════════════════════════════════════════════════════════════

# Cache directory: ~/.cache/scc/ (regenerable, safe to delete)
CACHE_DIR = Path.home() / ".cache" / "scc"


# ═══════════════════════════════════════════════════════════════════════════════
# Exceptions
# ═══════════════════════════════════════════════════════════════════════════════


class CacheNotFoundError(Exception):
    """Raised when cache is required but not available."""

    pass


class ConfigValidationError(Exception):
    """Raised when org config fails validation.

    This is raised when either:
    - Structural validation fails (JSON Schema errors)
    - Semantic validation fails (governance invariant violations)

    Invalid configs are never cached to prevent polluting the cache.
    """

    pass


# ═══════════════════════════════════════════════════════════════════════════════
# URL Validation
# ═══════════════════════════════════════════════════════════════════════════════


def validate_org_config_url(url: str) -> str:
    """Validate and normalize org config URL. HTTPS only.

    Args:
        url: URL to validate

    Returns:
        Validated and normalized URL

    Raises:
        ValueError for:
        - http:// URLs (security risk)
        - git@ or ssh:// URLs (not supported)
        - Non-URL formats
    """
    url = url.strip()

    # Reject SSH URLs early
    if url.startswith("git@") or url.startswith("ssh://"):
        raise ValueError(f"SSH URL not supported for org config: {url}")

    parsed = urlparse(url)

    # HTTPS only - reject http:// for security
    if parsed.scheme == "http":
        raise ValueError(f"HTTP not allowed (use HTTPS): {url}")

    if parsed.scheme != "https":
        raise ValueError(f"Invalid URL scheme (HTTPS required): {url}")

    return url


# ═══════════════════════════════════════════════════════════════════════════════
# Auth Resolution
# ═══════════════════════════════════════════════════════════════════════════════


def resolve_auth(auth_spec: str | None, *, from_remote: bool = False) -> str | None:
    """Resolve auth from 'env:VAR' or 'command:CMD' syntax.

    SECURITY: Uses auth.py module with shell=False to prevent shell injection.

    Args:
        auth_spec: Auth specification string or None
        from_remote: If True, applies trust model restrictions for remote org config.
                    command: auth requires SCC_ALLOW_REMOTE_COMMANDS=1 when from_remote=True.

    Returns:
        Token string or None if not available/configured

    Raises:
        ValueError: If command: auth is used from remote config without opt-in
    """
    if not auth_spec:
        return None

    # Determine if command: auth is allowed based on source
    # User config (from_remote=False): Always allow command: auth
    # Remote org config (from_remote=True): Require explicit opt-in
    allow_command = not from_remote or is_remote_command_allowed()

    try:
        result = _resolve_auth_impl(auth_spec, allow_command=allow_command)
        return result.token if result else None
    except RuntimeError:
        # Command execution failed - return None for backward compatibility
        # (old behavior: failed commands returned None)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# HTTP Fetching
# ═══════════════════════════════════════════════════════════════════════════════


def fetch_org_config(
    url: str, auth: str | None, etag: str | None = None
) -> tuple[dict[str, Any] | None, str | None, int]:
    """Fetch org config from URL with ETag support.

    Args:
        url: HTTPS URL to fetch from (validated)
        auth: Auth token for Authorization header
        etag: Previous ETag for conditional request

    Returns:
        Tuple of (config_dict, new_etag, status_code)
        - 200: new config returned
        - 304: not modified, config is None (use cache)
        - 401/403: auth error, config is None
        - Other errors: config is None
    """
    # Validate URL (HTTPS enforcement)
    url = validate_org_config_url(url)

    headers = {}

    # Add Authorization header if auth provided
    if auth:
        headers["Authorization"] = f"Bearer {auth}"

    # Add If-None-Match header for conditional request
    if etag:
        headers["If-None-Match"] = etag

    try:
        response = requests.get(url, headers=headers, timeout=30)
        status = response.status_code

        # 304 Not Modified - use cached version
        if status == 304:
            return (None, etag, 304)

        # Error responses
        if status != 200:
            return (None, None, status)

        # Parse JSON response
        try:
            config = response.json()
        except json.JSONDecodeError:
            return (None, None, -1)  # Invalid JSON

        # Extract new ETag
        new_etag = response.headers.get("ETag")

        return (config, new_etag, 200)

    except requests.RequestException:
        return (None, None, -2)  # Network error


# ═══════════════════════════════════════════════════════════════════════════════
# Cache Operations
# ═══════════════════════════════════════════════════════════════════════════════


def save_to_cache(
    org_config: dict[str, Any], source_url: str, etag: str | None, ttl_hours: int
) -> None:
    """Save org config to cache with metadata.

    Args:
        org_config: Organization config dict to cache
        source_url: URL the config was fetched from
        etag: ETag from server response
        ttl_hours: Cache time-to-live in hours
    """
    lock_file = lock_path("org-config-cache")
    with file_lock(lock_file):
        # Ensure cache directory exists
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        # Save org config with restrictive permissions (owner read/write only)
        config_file = CACHE_DIR / "org_config.json"
        config_content = json.dumps(org_config, indent=2)
        config_file.write_text(config_content)
        config_file.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600 - owner read/write only

        # Calculate fingerprint (SHA256 of cached bytes)
        fingerprint = hashlib.sha256(config_file.read_bytes()).hexdigest()

        # Calculate expiry time
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=ttl_hours)

        # Save metadata
        meta = {
            "org_config": {
                "source_url": source_url,
                "fetched_at": now.isoformat(),
                "expires_at": expires_at.isoformat(),
                "etag": etag,
                "fingerprint": fingerprint,
            }
        }
        meta_file = CACHE_DIR / "cache_meta.json"
        meta_file.write_text(json.dumps(meta, indent=2))
        meta_file.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600 - owner read/write only


def load_from_cache() -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Load cached org config and metadata.

    Returns:
        Tuple of (config_dict, metadata_dict)
        Both are None if cache doesn't exist or is corrupted
    """
    config_file = CACHE_DIR / "org_config.json"
    meta_file = CACHE_DIR / "cache_meta.json"

    if not config_file.exists() or not meta_file.exists():
        return (None, None)

    lock_file = lock_path("org-config-cache")
    with file_lock(lock_file):
        try:
            config = json.loads(config_file.read_text())
            meta = json.loads(meta_file.read_text())
            return (config, meta)
        except (json.JSONDecodeError, OSError):
            return (None, None)


def is_cache_valid(meta: dict[str, Any] | None) -> bool:
    """Check if cache is within TTL.

    Args:
        meta: Cache metadata dict

    Returns:
        True if cache is valid and within TTL
    """
    if not meta:
        return False

    org_config_meta = meta.get("org_config", {})
    expires_at_str = org_config_meta.get("expires_at")

    if not expires_at_str:
        return False

    try:
        expires_at = datetime.fromisoformat(expires_at_str)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return now < expires_at
    except (ValueError, TypeError):
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Validation Gate
# ═══════════════════════════════════════════════════════════════════════════════


def _validate_org_config(config: dict[str, Any]) -> None:
    """Validate org config structurally and semantically.

    This is the Validation Gate pattern - called BEFORE caching to ensure
    invalid configs never pollute the cache.

    Two-step validation:
    1. Structural: JSON Schema validation (required fields, types, patterns)
    2. Semantic: Governance invariants (enabled ⊆ allowed, enabled ∩ blocked = ∅)

    Args:
        config: Organization config dict to validate

    Raises:
        ConfigValidationError: If either validation step fails
    """
    # Import here to avoid circular dependencies at module load time
    from scc_cli.validate import InvariantViolation, validate_config_invariants
    from scc_cli.validate import validate_org_config as validate_schema

    # Step 1: Structural validation (JSON Schema)
    schema_errors = validate_schema(config)
    if schema_errors:
        # Format errors for user-friendly message
        error_summary = "; ".join(schema_errors[:3])  # Show first 3 errors
        if len(schema_errors) > 3:
            error_summary += f" (+{len(schema_errors) - 3} more)"
        raise ConfigValidationError(
            f"Organization config failed schema validation: {error_summary}"
        )

    # Step 2: Semantic validation (governance invariants)
    violations: list[InvariantViolation] = validate_config_invariants(config)
    errors = [v for v in violations if v.severity == "error"]
    if errors:
        # Format violations for user-friendly message
        error_messages = [v.message for v in errors[:3]]  # Show first 3
        error_summary = "; ".join(error_messages)
        if len(errors) > 3:
            error_summary += f" (+{len(errors) - 3} more)"
        raise ConfigValidationError(
            f"Organization config failed invariant validation: {error_summary}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Main Entry Point
# ═══════════════════════════════════════════════════════════════════════════════


def load_org_config(
    user_config: dict[str, Any], force_refresh: bool = False, offline: bool = False
) -> dict[str, Any] | None:
    """Load organization config from cache or remote.

    This is the main entry point for getting org config.

    Args:
        user_config: User config dict with organization_source
        force_refresh: Bypass TTL check and always fetch from remote
        offline: Use cache only, error if no cache available

    Returns:
        Organization config dict, or None for standalone mode

    Raises:
        CacheNotFoundError: In offline mode when no cache is available
    """
    # Standalone mode - no org config
    if user_config.get("standalone"):
        return None

    # No organization source configured
    org_source = user_config.get("organization_source")
    if not org_source:
        return None

    url = org_source.get("url")
    if not url:
        return None

    auth_spec = org_source.get("auth")

    # Try to load from cache
    cached_config, meta = load_from_cache()

    # Offline mode: cache only
    if offline:
        if cached_config is not None:
            return cached_config
        raise CacheNotFoundError(f"No cached config available for offline mode. URL: {url}")

    # Check if cache is valid and we don't need to refresh
    if not force_refresh and cached_config is not None and is_cache_valid(meta):
        return cached_config

    # Need to fetch from remote
    auth = resolve_auth(auth_spec)
    etag = meta.get("org_config", {}).get("etag") if meta else None

    config, new_etag, status = fetch_org_config(url, auth=auth, etag=etag)

    # 304 Not Modified - use cached version
    if status == 304 and cached_config is not None:
        return cached_config

    # Success - validate BEFORE caching (Validation Gate pattern)
    if status == 200 and config is not None:
        # Validate config - raises ConfigValidationError if invalid
        # This prevents invalid configs from polluting the cache
        _validate_org_config(config)
        from scc_cli.validate import check_version_compatibility

        compatibility = check_version_compatibility(config)
        if not compatibility.compatible:
            raise ConfigValidationError(compatibility.blocking_error or "Config incompatible")

        # Only cache after validation passes
        ttl_hours = config.get("defaults", {}).get("cache_ttl_hours", 24)
        save_to_cache(config, url, new_etag, ttl_hours)
        return config

    # Fetch failed - return stale cache if available (with warning)
    if cached_config is not None:
        print_human(
            "[yellow]Warning:[/yellow] Failed to refresh org config; using cached config.",
            file=sys.stderr,
            highlight=False,
        )
        return cached_config

    # No cache and fetch failed - return None
    return None
