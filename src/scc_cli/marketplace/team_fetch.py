"""Team config fetching for federated configurations (Phase 2).

This module provides:
- TeamFetchResult: Result of fetching a team configuration
- fetch_team_config(): Main entry point with ConfigSource dispatch
- save_team_config_cache(): Save fetched config to cache
- load_team_config_cache(): Load config from cache

Fetching Flow:
    1. Dispatch to appropriate fetcher based on ConfigSource type
    2. Clone/fetch the config from remote source
    3. Validate against team-config schema
    4. Save to cache with metadata
    5. Return TeamFetchResult with config and version info

Source Types:
    - GitHub: Clone repo, read config file from path
    - Git: Clone generic git repo, read config file
    - URL: HTTP GET request with ETag support
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import requests

from scc_cli.marketplace.team_cache import (
    DEFAULT_TTL,
    MAX_STALE_AGE,
    TeamCacheMeta,
    get_team_config_cache_path,
    get_team_meta_cache_path,
)

if TYPE_CHECKING:
    from scc_cli.marketplace.schema import (
        ConfigSource,
        ConfigSourceGit,
        ConfigSourceGitHub,
        ConfigSourceURL,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Result Types
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class TeamFetchResult:
    """Result of fetching a team configuration.

    Attributes:
        success: Whether fetch was successful
        team_config: Parsed team config dict (None if failed)
        source_type: Type of source (github, git, url)
        source_url: Normalized source URL
        commit_sha: Git commit SHA (for git/github sources)
        etag: HTTP ETag (for URL sources)
        branch: Git branch (for git/github sources)
        error: Error message (if failed)
    """

    success: bool
    source_type: str
    source_url: str
    team_config: dict[str, Any] | None = None
    commit_sha: str | None = None
    etag: str | None = None
    branch: str | None = None
    error: str | None = None


@dataclass
class FallbackFetchResult:
    """Result of fetching with cache fallback support.

    Extends TeamFetchResult with additional metadata about cache usage
    and staleness warnings to inform the user.

    Attributes:
        result: The underlying TeamFetchResult
        used_cache: True if result came from cache (not fresh fetch)
        is_stale: True if cache is past TTL but within MAX_STALE_AGE
        staleness_warning: Human-readable warning about stale data
        cache_meta: Metadata about the cached config (if used)
    """

    result: TeamFetchResult
    used_cache: bool = False
    is_stale: bool = False
    staleness_warning: str | None = None
    cache_meta: TeamCacheMeta | None = None

    @property
    def success(self) -> bool:
        """Delegate to underlying result."""
        return self.result.success

    @property
    def team_config(self) -> dict[str, Any] | None:
        """Delegate to underlying result."""
        return self.result.team_config

    @property
    def error(self) -> str | None:
        """Delegate to underlying result."""
        return self.result.error


# ─────────────────────────────────────────────────────────────────────────────
# Main Entry Point
# ─────────────────────────────────────────────────────────────────────────────


def fetch_team_config(
    source: ConfigSource,
    team_name: str,
    cache_root: Path | None = None,
) -> TeamFetchResult:
    """Fetch team config from ConfigSource with dispatch.

    Dispatches to appropriate fetcher based on source type:
    - github: Clone GitHub repo and read config
    - git: Clone generic git repo and read config
    - url: HTTP GET with ETag support

    Args:
        source: ConfigSource defining where to fetch from
        team_name: Team name for cache key
        cache_root: Cache directory (defaults to XDG cache)

    Returns:
        TeamFetchResult with config data or error
    """
    # Import here to avoid circular imports
    from scc_cli.marketplace.schema import (
        ConfigSourceGit,
        ConfigSourceGitHub,
        ConfigSourceURL,
    )

    # Dispatch based on source type
    if isinstance(source, ConfigSourceGitHub):
        result = _fetch_from_github(source, team_name)
    elif isinstance(source, ConfigSourceGit):
        result = _fetch_from_git(source, team_name)
    elif isinstance(source, ConfigSourceURL):
        result = _fetch_from_url(source, team_name)
    else:
        return TeamFetchResult(
            success=False,
            source_type="unknown",
            source_url="",
            error=f"Unknown source type: {type(source).__name__}",
        )

    # Save to cache on success
    if result.success:
        save_team_config_cache(result, team_name, cache_root)

    return result


def fetch_team_config_with_fallback(
    source: ConfigSource,
    team_name: str,
    cache_root: Path | None = None,
) -> FallbackFetchResult:
    """Fetch team config with graceful degradation to cache.

    Implements the freshness model:
    - Fresh (age < DEFAULT_TTL): Use cached config directly, skip fetch
    - Stale (TTL < age < MAX_STALE_AGE): Try fetch, fallback to cache on failure
    - Expired (age > MAX_STALE_AGE): Must fetch, no fallback allowed

    This is the recommended entry point for production use as it provides
    resilience against network failures while maintaining freshness guarantees.

    Args:
        source: ConfigSource defining where to fetch from
        team_name: Team name for cache key
        cache_root: Cache directory (defaults to XDG cache)

    Returns:
        FallbackFetchResult with config, cache status, and staleness warnings
    """
    # Step 1: Check if we have cached config
    cached = load_team_config_cache(team_name, cache_root)

    if cached is not None:
        config, meta = cached

        # Case A: Cache is fresh - use directly, no fetch needed
        if meta.is_fresh(DEFAULT_TTL):
            return FallbackFetchResult(
                result=TeamFetchResult(
                    success=True,
                    source_type=meta.source_type,
                    source_url=meta.source_url,
                    team_config=config,
                    commit_sha=meta.commit_sha,
                    etag=meta.etag,
                    branch=meta.branch,
                ),
                used_cache=True,
                is_stale=False,
                cache_meta=meta,
            )

        # Case B: Cache is stale but within MAX_STALE_AGE - try fetch, fallback on failure
        if meta.is_within_max_stale_age(MAX_STALE_AGE):
            # Try to fetch fresh config
            result = fetch_team_config(source, team_name, cache_root)

            if result.success:
                # Fresh fetch succeeded - return it
                return FallbackFetchResult(
                    result=result,
                    used_cache=False,
                    is_stale=False,
                )
            else:
                # Fetch failed - fallback to stale cache with warning
                age_hours = int(meta.age.total_seconds() / 3600)
                staleness_warning = (
                    f"Using cached config from {age_hours}h ago (fetch failed: {result.error}). "
                    f"Cache will expire in {int((MAX_STALE_AGE - meta.age).total_seconds() / 3600)}h."
                )

                return FallbackFetchResult(
                    result=TeamFetchResult(
                        success=True,
                        source_type=meta.source_type,
                        source_url=meta.source_url,
                        team_config=config,
                        commit_sha=meta.commit_sha,
                        etag=meta.etag,
                        branch=meta.branch,
                    ),
                    used_cache=True,
                    is_stale=True,
                    staleness_warning=staleness_warning,
                    cache_meta=meta,
                )

        # Case C: Cache is expired (> MAX_STALE_AGE) - fall through to force fetch

    # Step 2: No usable cache - must fetch
    result = fetch_team_config(source, team_name, cache_root)

    if not result.success and cached is not None:
        # We had an expired cache but fetch also failed
        _, meta = cached
        age_days = int(meta.age.total_seconds() / 86400)
        result = TeamFetchResult(
            success=False,
            source_type=result.source_type,
            source_url=result.source_url,
            error=(
                f"{result.error}. "
                f"Cached config ({age_days}d old) has expired beyond MAX_STALE_AGE ({MAX_STALE_AGE.days}d) "
                f"and cannot be used as fallback."
            ),
        )

    return FallbackFetchResult(
        result=result,
        used_cache=False,
        is_stale=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
# GitHub Fetching
# ─────────────────────────────────────────────────────────────────────────────


def _fetch_from_github(
    source: ConfigSourceGitHub,
    team_name: str,
) -> TeamFetchResult:
    """Fetch team config from GitHub repository.

    Constructs HTTPS clone URL and delegates to _clone_and_read_config.

    Args:
        source: GitHub config source
        team_name: Team name for logging

    Returns:
        TeamFetchResult with config or error
    """
    # Construct GitHub clone URL
    clone_url = f"https://github.com/{source.owner}/{source.repo}.git"
    source_url = f"github.com/{source.owner}/{source.repo}"

    # Determine branch and path
    branch = source.branch if source.branch else "main"
    config_path = source.path if source.path else "team-config.json"

    try:
        config, commit_sha, error = _clone_and_read_config(
            clone_url,
            branch=branch,
            path=config_path,
        )

        if error:
            return TeamFetchResult(
                success=False,
                source_type="github",
                source_url=source_url,
                error=error,
            )

        return TeamFetchResult(
            success=True,
            team_config=config,
            source_type="github",
            source_url=source_url,
            commit_sha=commit_sha,
            branch=branch,
        )

    except Exception as e:
        return TeamFetchResult(
            success=False,
            source_type="github",
            source_url=source_url,
            error=str(e),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Generic Git Fetching
# ─────────────────────────────────────────────────────────────────────────────


def _fetch_from_git(
    source: ConfigSourceGit,
    team_name: str,
) -> TeamFetchResult:
    """Fetch team config from generic Git repository.

    Uses provided URL directly for cloning.

    Args:
        source: Git config source
        team_name: Team name for logging

    Returns:
        TeamFetchResult with config or error
    """
    clone_url = source.url

    # Normalize source URL for display (remove protocol, .git suffix)
    source_url = clone_url
    if source_url.startswith("https://"):
        source_url = source_url[8:]
    elif source_url.startswith("git@"):
        source_url = source_url[4:].replace(":", "/", 1)
    if source_url.endswith(".git"):
        source_url = source_url[:-4]

    # Determine branch and path
    branch = source.branch if source.branch else "main"
    config_path = source.path if source.path else "team-config.json"

    try:
        config, commit_sha, error = _clone_and_read_config(
            clone_url,
            branch=branch,
            path=config_path,
        )

        if error:
            return TeamFetchResult(
                success=False,
                source_type="git",
                source_url=source_url,
                error=error,
            )

        return TeamFetchResult(
            success=True,
            team_config=config,
            source_type="git",
            source_url=source_url,
            commit_sha=commit_sha,
            branch=branch,
        )

    except Exception as e:
        return TeamFetchResult(
            success=False,
            source_type="git",
            source_url=source_url,
            error=str(e),
        )


# ─────────────────────────────────────────────────────────────────────────────
# URL Fetching
# ─────────────────────────────────────────────────────────────────────────────


def _fetch_from_url(
    source: ConfigSourceURL,
    team_name: str,
) -> TeamFetchResult:
    """Fetch team config from HTTPS URL.

    Supports ETag for cache validation and custom headers.

    Args:
        source: URL config source
        team_name: Team name for logging

    Returns:
        TeamFetchResult with config or error
    """
    url = source.url

    # Normalize source URL for display
    source_url = url
    if source_url.startswith("https://"):
        source_url = source_url[8:]

    # Build headers
    headers: dict[str, str] = {}
    if source.headers:
        headers.update(source.headers)

    try:
        response = requests.get(url, headers=headers, timeout=30)

        # Handle error status codes
        if response.status_code == 404:
            return TeamFetchResult(
                success=False,
                source_type="url",
                source_url=source_url,
                error=(
                    f"HTTP 404: Team config not found at {url}. "
                    "Verify the URL is correct and the config file exists."
                ),
            )

        if response.status_code == 401:
            return TeamFetchResult(
                success=False,
                source_type="url",
                source_url=source_url,
                error=(
                    f"HTTP 401: Unauthorized access to {url}. "
                    "Add authentication headers in config_source or check credentials."
                ),
            )

        if response.status_code == 403:
            return TeamFetchResult(
                success=False,
                source_type="url",
                source_url=source_url,
                error=(
                    f"HTTP 403: Access denied to {url}. Check permissions or firewall settings."
                ),
            )

        if response.status_code != 200:
            return TeamFetchResult(
                success=False,
                source_type="url",
                source_url=source_url,
                error=(
                    f"HTTP {response.status_code}: Failed to fetch team config from {url}. "
                    "Check if the server is reachable and the URL is correct."
                ),
            )

        # Parse JSON response
        try:
            config = response.json()
        except json.JSONDecodeError as e:
            return TeamFetchResult(
                success=False,
                source_type="url",
                source_url=source_url,
                error=(
                    f"Invalid JSON in team config: {e}. "
                    "Check that the file contains valid JSON (try a JSON validator)."
                ),
            )

        # Extract ETag
        etag = response.headers.get("ETag")

        return TeamFetchResult(
            success=True,
            team_config=config,
            source_type="url",
            source_url=source_url,
            etag=etag,
        )

    except requests.RequestException as e:
        return TeamFetchResult(
            success=False,
            source_type="url",
            source_url=source_url,
            error=(
                f"Network error fetching team config: {e}. "
                "Check network connection, VPN status, and firewall settings."
            ),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Git Clone Helper
# ─────────────────────────────────────────────────────────────────────────────


def _clone_and_read_config(
    clone_url: str,
    branch: str = "main",
    path: str = "team-config.json",
    cache_dir: Path | None = None,
) -> tuple[dict[str, Any] | None, str | None, str | None]:
    """Clone git repo and read config file.

    Args:
        clone_url: Git clone URL
        branch: Branch to checkout
        path: Path to config file within repo
        cache_dir: Cache directory for clone (uses temp if None)

    Returns:
        Tuple of (config_dict, commit_sha, error_message)
    """
    # Use temp directory for clone
    with tempfile.TemporaryDirectory(prefix="scc_team_") as tmp_dir:
        target_dir = Path(tmp_dir) / "repo"

        # Clone with shallow depth
        cmd = [
            "git",
            "clone",
            "--depth",
            "1",
            "--branch",
            branch,
            clone_url,
            str(target_dir),
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                return (None, None, f"Git clone failed: {result.stderr}")

        except FileNotFoundError:
            return (None, None, "Git not available")
        except subprocess.TimeoutExpired:
            return (None, None, "Git clone timed out")

        # Get commit SHA
        sha_result = subprocess.run(
            ["git", "-C", str(target_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        )
        commit_sha = sha_result.stdout.strip() if sha_result.returncode == 0 else None

        # Read config file
        config_path = target_dir / path

        if not config_path.exists():
            return (None, commit_sha, f"Config file not found: {path}")

        try:
            config_text = config_path.read_text(encoding="utf-8")
            config = json.loads(config_text)
            return (config, commit_sha, None)
        except json.JSONDecodeError as e:
            return (None, commit_sha, f"Invalid JSON in config: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Cache Operations
# ─────────────────────────────────────────────────────────────────────────────


def save_team_config_cache(
    result: TeamFetchResult,
    team_name: str,
    cache_root: Path | None = None,
) -> None:
    """Save fetched team config to cache.

    Creates two files:
    - {team_name}.json: The team config
    - {team_name}.meta.json: Metadata about the fetch

    Args:
        result: Successful fetch result
        team_name: Team name for cache key
        cache_root: Cache root directory
    """
    if not result.success or result.team_config is None:
        return

    config_path = get_team_config_cache_path(team_name, cache_root)
    meta_path = get_team_meta_cache_path(team_name, cache_root)

    # Ensure directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Save config
    config_path.write_text(
        json.dumps(result.team_config, indent=2),
        encoding="utf-8",
    )

    # Save metadata
    meta = TeamCacheMeta(
        team_name=team_name,
        source_type=result.source_type,
        source_url=result.source_url,
        fetched_at=datetime.now(timezone.utc),
        commit_sha=result.commit_sha,
        etag=result.etag,
        branch=result.branch,
    )

    meta_path.write_text(
        json.dumps(meta.to_dict(), indent=2),
        encoding="utf-8",
    )


def load_team_config_cache(
    team_name: str,
    cache_root: Path | None = None,
) -> tuple[dict[str, Any], TeamCacheMeta] | None:
    """Load team config from cache.

    Args:
        team_name: Team name to load
        cache_root: Cache root directory

    Returns:
        Tuple of (config_dict, cache_meta) or None if not cached
    """
    config_path = get_team_config_cache_path(team_name, cache_root)
    meta_path = get_team_meta_cache_path(team_name, cache_root)

    # Check if both files exist
    if not config_path.exists() or not meta_path.exists():
        return None

    try:
        # Load config
        config_text = config_path.read_text(encoding="utf-8")
        config = json.loads(config_text)

        # Load metadata
        meta_text = meta_path.read_text(encoding="utf-8")
        meta_dict = json.loads(meta_text)
        meta = TeamCacheMeta.from_dict(meta_dict)

        return (config, meta)

    except (json.JSONDecodeError, KeyError):
        return None
