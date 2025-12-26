"""Team config caching for federated configurations (Phase 2).

This module provides:
- TeamCacheMeta: Metadata about cached team configurations
- DEFAULT_TTL: How long cached configs are considered fresh (24h)
- MAX_STALE_AGE: Maximum age for fallback to stale cache (7d)
- Cache path utilities for team config storage

Cache Design:
    Team configs are cached under ~/.cache/scc/team_configs/
    Each team has two files:
    - {team_name}.json: The actual team config
    - {team_name}.meta.json: Metadata (source, timestamps, SHA)

Freshness Model:
    - Fresh (age < DEFAULT_TTL): Use cached config directly
    - Stale (TTL < age < MAX_STALE_AGE): Try refresh, fallback to cache
    - Expired (age > MAX_STALE_AGE): Must fetch, no fallback allowed
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# How long cached team configs are considered fresh
DEFAULT_TTL: timedelta = timedelta(hours=24)

# Maximum age for fallback to stale cache when fetch fails
MAX_STALE_AGE: timedelta = timedelta(days=7)


# ─────────────────────────────────────────────────────────────────────────────
# Cache Metadata
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class TeamCacheMeta:
    """Metadata about a cached team configuration.

    Tracks when and how a team config was fetched, enabling:
    - Cache freshness decisions (is_fresh)
    - Fallback policy (is_within_max_stale_age)
    - Conditional fetching with ETags/commit SHAs

    Attributes:
        team_name: Team identifier
        source_type: How config was fetched (github, git, url)
        source_url: Where config was fetched from
        fetched_at: When config was last fetched
        commit_sha: Git commit SHA (for git/github sources)
        etag: HTTP ETag (for URL sources)
        branch: Git branch (for git/github sources)
    """

    team_name: str
    source_type: str
    source_url: str
    fetched_at: datetime
    commit_sha: str | None = None
    etag: str | None = None
    branch: str | None = None

    @property
    def age(self) -> timedelta:
        """Calculate how old this cached config is.

        Returns:
            Time elapsed since fetched_at
        """
        now = datetime.now(timezone.utc)
        # Handle timezone-naive datetimes
        fetched = self.fetched_at
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        return now - fetched

    def is_fresh(self, ttl: timedelta = DEFAULT_TTL) -> bool:
        """Check if cached config is still fresh.

        Args:
            ttl: Time-to-live threshold

        Returns:
            True if age < ttl, meaning cache can be used without refresh
        """
        return self.age < ttl

    def is_within_max_stale_age(self, max_age: timedelta = MAX_STALE_AGE) -> bool:
        """Check if stale cache can be used as fallback.

        Args:
            max_age: Maximum acceptable age for fallback

        Returns:
            True if age < max_age, meaning cache can be used when fetch fails
        """
        return self.age < max_age

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage.

        Returns:
            Dict with all fields, datetime as ISO format string
        """
        return {
            "team_name": self.team_name,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "fetched_at": self.fetched_at.isoformat(),
            "commit_sha": self.commit_sha,
            "etag": self.etag,
            "branch": self.branch,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TeamCacheMeta:
        """Deserialize from dictionary loaded from JSON.

        Args:
            data: Dict with serialized cache metadata

        Returns:
            Restored TeamCacheMeta instance
        """
        fetched_at = data.get("fetched_at")
        if isinstance(fetched_at, str):
            fetched_at = datetime.fromisoformat(fetched_at)
        else:
            fetched_at = datetime.now(timezone.utc)

        return cls(
            team_name=data["team_name"],
            source_type=data["source_type"],
            source_url=data["source_url"],
            fetched_at=fetched_at,
            commit_sha=data.get("commit_sha"),
            etag=data.get("etag"),
            branch=data.get("branch"),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Cache Paths
# ─────────────────────────────────────────────────────────────────────────────


def get_team_cache_dir(cache_root: Path | None = None) -> Path:
    """Get the directory for team config caches.

    Args:
        cache_root: Base cache directory (defaults to XDG cache path)

    Returns:
        Path to team_configs subdirectory
    """
    if cache_root is None:
        from scc_cli.config import get_cache_dir

        cache_root = get_cache_dir()

    return cache_root / "team_configs"


def get_team_config_cache_path(team_name: str, cache_root: Path | None = None) -> Path:
    """Get the cache file path for a team's config.

    Args:
        team_name: Team identifier
        cache_root: Base cache directory

    Returns:
        Path to {team_name}.json file
    """
    return get_team_cache_dir(cache_root) / f"{team_name}.json"


def get_team_meta_cache_path(team_name: str, cache_root: Path | None = None) -> Path:
    """Get the cache metadata file path for a team.

    Args:
        team_name: Team identifier
        cache_root: Base cache directory

    Returns:
        Path to {team_name}.meta.json file
    """
    return get_team_cache_dir(cache_root) / f"{team_name}.meta.json"
