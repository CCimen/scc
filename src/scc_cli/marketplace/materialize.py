"""
Marketplace materialization for SCC.

This module provides marketplace source materialization:
- MaterializedMarketplace: Dataclass tracking materialized marketplace state
- load_manifest/save_manifest: Manifest management for cache tracking
- materialize_*: Handlers for different source types (github, git, directory, url)
- materialize_marketplace: Dispatcher for source-type routing

Materialization Process:
    1. Check manifest for existing cache
    2. Determine if refresh needed (TTL, force)
    3. Clone/copy/download based on source type
    4. Validate .claude-plugin/marketplace.json exists
    5. Update manifest with new state
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from scc_cli.marketplace.constants import (
    DEFAULT_ORG_CONFIG_TTL_SECONDS,
    MANIFEST_FILE,
    MARKETPLACE_CACHE_DIR,
)

# Re-export extracted functions and dataclasses for backward compatibility.
# These were moved to materialize_git.py to keep this module under 800 lines.
from scc_cli.marketplace.materialize_git import (  # noqa: F401
    CloneResult,
    DiscoveryResult,
    DownloadResult,
    _discover_plugins,
    download_and_extract,
    run_git_clone,
)
from scc_cli.marketplace.schema import (
    MarketplaceSource,
    MarketplaceSourceDirectory,
    MarketplaceSourceGit,
    MarketplaceSourceGitHub,
    MarketplaceSourceURL,
)
from scc_cli.ports.remote_fetcher import RemoteFetcher

# ─────────────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────────────


class MaterializationError(Exception):
    """Base exception for materialization failures."""

    def __init__(self, message: str, marketplace_name: str | None = None) -> None:
        self.marketplace_name = marketplace_name
        super().__init__(message)


class GitNotAvailableError(MaterializationError):
    """Raised when git is not installed but required."""

    def __init__(self) -> None:
        super().__init__(
            "git is required for cloning marketplace repositories but was not found. "
            "Please install git: https://git-scm.com/downloads"
        )


class InvalidMarketplaceError(MaterializationError):
    """Raised when marketplace structure is invalid."""

    def __init__(self, marketplace_name: str, reason: str) -> None:
        super().__init__(
            f"Invalid marketplace '{marketplace_name}': {reason}. "
            "A valid marketplace must contain .claude-plugin/marketplace.json",
            marketplace_name,
        )


def _validate_marketplace_name(name: str) -> None:
    """Validate marketplace name for safe filesystem usage."""
    if not name or not name.strip():
        raise InvalidMarketplaceError(name, "marketplace name cannot be empty")
    if name in {".", ".."}:
        raise InvalidMarketplaceError(name, "marketplace name cannot be '.' or '..'")
    if "/" in name or "\\" in name:
        raise InvalidMarketplaceError(name, "marketplace name cannot contain path separators")
    if "\x00" in name:
        raise InvalidMarketplaceError(name, "marketplace name cannot contain null bytes")


# ─────────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class MaterializedMarketplace:
    """A marketplace that has been materialized to local filesystem.

    Attributes:
        name: Marketplace identifier (matches org config key - the "alias")
        canonical_name: The actual name from marketplace.json (what Claude Code sees)
        relative_path: Path relative to project root (for Docker compatibility)
        source_type: Source type (github, git, directory, url)
        source_url: Original source URL or path
        source_ref: Git branch/tag or None for non-git sources
        materialization_mode: How content was fetched (full, metadata_only, etc)
        materialized_at: When the marketplace was last materialized
        commit_sha: Git commit SHA (for git sources) or None
        etag: HTTP ETag (for URL sources) or None
        plugins_available: List of plugin names discovered in marketplace
    """

    name: str
    canonical_name: str  # Name from marketplace.json - used by Claude Code
    relative_path: str
    source_type: str
    source_url: str
    source_ref: str | None
    materialization_mode: str
    materialized_at: datetime
    commit_sha: str | None
    etag: str | None
    plugins_available: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON storage."""
        return {
            "name": self.name,
            "canonical_name": self.canonical_name,
            "relative_path": self.relative_path,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "source_ref": self.source_ref,
            "materialization_mode": self.materialization_mode,
            "materialized_at": self.materialized_at.isoformat(),
            "commit_sha": self.commit_sha,
            "etag": self.etag,
            "plugins_available": self.plugins_available,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MaterializedMarketplace:
        """Deserialize from dictionary loaded from JSON."""
        materialized_at = data.get("materialized_at")
        if isinstance(materialized_at, str):
            materialized_at = datetime.fromisoformat(materialized_at)
        else:
            materialized_at = datetime.now(timezone.utc)

        # canonical_name defaults to name for backward compatibility with old manifests
        name = data["name"]
        canonical_name = data.get("canonical_name", name)

        return cls(
            name=name,
            canonical_name=canonical_name,
            relative_path=data["relative_path"],
            source_type=data["source_type"],
            source_url=data["source_url"],
            source_ref=data.get("source_ref"),
            materialization_mode=data.get("materialization_mode", "full"),
            materialized_at=materialized_at,
            commit_sha=data.get("commit_sha"),
            etag=data.get("etag"),
            plugins_available=data.get("plugins_available", []),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Manifest Management
# ─────────────────────────────────────────────────────────────────────────────


def _get_manifest_path(project_dir: Path) -> Path:
    """Get path to manifest file."""
    return project_dir / ".claude" / MARKETPLACE_CACHE_DIR / MANIFEST_FILE


def load_manifest(project_dir: Path) -> dict[str, MaterializedMarketplace]:
    """Load manifest from project's .claude/.scc-marketplaces/.manifest.json.

    Args:
        project_dir: Project root directory

    Returns:
        Dict mapping marketplace names to MaterializedMarketplace instances
        Empty dict if manifest doesn't exist
    """
    manifest_path = _get_manifest_path(project_dir)

    if not manifest_path.exists():
        return {}

    try:
        data = json.loads(manifest_path.read_text())
        return {name: MaterializedMarketplace.from_dict(entry) for name, entry in data.items()}
    except (json.JSONDecodeError, KeyError):
        return {}


def save_manifest(
    project_dir: Path,
    marketplaces: dict[str, MaterializedMarketplace],
) -> None:
    """Save manifest to project's .claude/.scc-marketplaces/.manifest.json.

    Args:
        project_dir: Project root directory
        marketplaces: Dict mapping marketplace names to instances
    """
    manifest_path = _get_manifest_path(project_dir)

    # Ensure directory exists
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    data = {name: mp.to_dict() for name, mp in marketplaces.items()}
    manifest_path.write_text(json.dumps(data, indent=2))


# ─────────────────────────────────────────────────────────────────────────────
# Cache Freshness
# ─────────────────────────────────────────────────────────────────────────────


def is_cache_fresh(
    marketplace: MaterializedMarketplace,
    ttl_seconds: int = DEFAULT_ORG_CONFIG_TTL_SECONDS,
) -> bool:
    """Check if cached marketplace is fresh enough to skip re-materialization.

    Args:
        marketplace: Existing materialized marketplace
        ttl_seconds: Time-to-live in seconds

    Returns:
        True if cache is fresh, False if stale
    """
    age = datetime.now(timezone.utc) - marketplace.materialized_at
    return age.total_seconds() < ttl_seconds


# ─────────────────────────────────────────────────────────────────────────────
# Git Operations
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# Materialization Handlers
# ─────────────────────────────────────────────────────────────────────────────


def _get_relative_path(name: str) -> str:
    """Get relative path for a marketplace."""
    _validate_marketplace_name(name)
    return f".claude/{MARKETPLACE_CACHE_DIR}/{name}"


def _get_absolute_path(project_dir: Path, name: str) -> Path:
    """Get absolute path for a marketplace."""
    _validate_marketplace_name(name)
    return project_dir / ".claude" / MARKETPLACE_CACHE_DIR / name


def materialize_github(
    name: str,
    source: dict[str, Any] | MarketplaceSourceGitHub,
    project_dir: Path,
) -> MaterializedMarketplace:
    """Materialize a GitHub marketplace source.

    Args:
        name: Marketplace name (key in org config) - the "alias"
        source: GitHub source configuration
        project_dir: Project root directory

    Returns:
        MaterializedMarketplace with materialization details including canonical_name

    Raises:
        MaterializationError: On clone failure
        GitNotAvailableError: When git is not installed
        InvalidMarketplaceError: When marketplace structure is invalid
    """
    # Normalize source to dict
    if hasattr(source, "model_dump"):
        source_dict = source.model_dump()
    else:
        source_dict = dict(source)

    owner = source_dict.get("owner", "")
    repo = source_dict.get("repo", "")
    branch = source_dict.get("branch", "main")
    # Note: path is parsed but not used yet - could be used for subdir cloning later
    _ = source_dict.get("path", "/")

    url = f"https://github.com/{owner}/{repo}.git"
    target_dir = _get_absolute_path(project_dir, name)

    try:
        # Pass name as fallback in case marketplace.json doesn't specify one
        result = run_git_clone(url, target_dir, branch=branch, depth=1, fallback_name=name)
    except FileNotFoundError:
        raise GitNotAvailableError()

    if not result.success:
        if result.error and "marketplace.json" in result.error:
            raise InvalidMarketplaceError(name, result.error)
        raise MaterializationError(result.error or "Clone failed", name)

    # canonical_name comes from marketplace.json, fallback to alias name
    canonical_name = result.canonical_name or name

    return MaterializedMarketplace(
        name=name,
        canonical_name=canonical_name,
        relative_path=_get_relative_path(name),
        source_type="github",
        source_url=url,
        source_ref=branch,
        materialization_mode="full",
        materialized_at=datetime.now(timezone.utc),
        commit_sha=result.commit_sha,
        etag=None,
        plugins_available=result.plugins or [],
    )


def materialize_git(
    name: str,
    source: dict[str, Any] | MarketplaceSourceGit,
    project_dir: Path,
) -> MaterializedMarketplace:
    """Materialize a generic git marketplace source.

    Args:
        name: Marketplace name (key in org config) - the "alias"
        source: Git source configuration
        project_dir: Project root directory

    Returns:
        MaterializedMarketplace with materialization details including canonical_name

    Raises:
        MaterializationError: On clone failure
        GitNotAvailableError: When git is not installed
    """
    if hasattr(source, "model_dump"):
        source_dict = source.model_dump()
    else:
        source_dict = dict(source)

    url = source_dict.get("url", "")
    branch = source_dict.get("branch", "main")

    target_dir = _get_absolute_path(project_dir, name)

    # Pass name as fallback in case marketplace.json doesn't specify one
    result = run_git_clone(url, target_dir, branch=branch, depth=1, fallback_name=name)

    if not result.success:
        if result.error and "marketplace.json" in result.error:
            raise InvalidMarketplaceError(name, result.error)
        raise MaterializationError(result.error or "Clone failed", name)

    # canonical_name comes from marketplace.json, fallback to alias name
    canonical_name = result.canonical_name or name

    return MaterializedMarketplace(
        name=name,
        canonical_name=canonical_name,
        relative_path=_get_relative_path(name),
        source_type="git",
        source_url=url,
        source_ref=branch,
        materialization_mode="full",
        materialized_at=datetime.now(timezone.utc),
        commit_sha=result.commit_sha,
        etag=None,
        plugins_available=result.plugins or [],
    )


def materialize_directory(
    name: str,
    source: dict[str, Any] | MarketplaceSourceDirectory,
    project_dir: Path,
) -> MaterializedMarketplace:
    """Materialize a local directory marketplace source.

    Creates a symlink to the local directory for Docker visibility.

    Args:
        name: Marketplace name (key in org config) - the "alias"
        source: Directory source configuration
        project_dir: Project root directory

    Returns:
        MaterializedMarketplace with materialization details including canonical_name

    Raises:
        InvalidMarketplaceError: When marketplace structure is invalid
    """
    if hasattr(source, "model_dump"):
        source_dict = source.model_dump()
    else:
        source_dict = dict(source)

    source_path = Path(source_dict.get("path", ""))

    # Resolve relative paths from project_dir
    if not source_path.is_absolute():
        source_path = project_dir / source_path

    # Validate marketplace structure and discover canonical name
    discovery = _discover_plugins(source_path, fallback_name=name)
    if discovery is None:
        raise InvalidMarketplaceError(
            name,
            "Missing .claude-plugin/marketplace.json",
        )

    # Create symlink in cache directory
    target_dir = _get_absolute_path(project_dir, name)
    target_dir.parent.mkdir(parents=True, exist_ok=True)

    # Remove existing symlink/directory
    if target_dir.exists() or target_dir.is_symlink():
        if target_dir.is_symlink():
            target_dir.unlink()
        else:
            shutil.rmtree(target_dir)

    # Create symlink
    os.symlink(source_path, target_dir)

    return MaterializedMarketplace(
        name=name,
        canonical_name=discovery.canonical_name,
        relative_path=_get_relative_path(name),
        source_type="directory",
        source_url=str(source_path),
        source_ref=None,
        materialization_mode="full",
        materialized_at=datetime.now(timezone.utc),
        commit_sha=None,
        etag=None,
        plugins_available=discovery.plugins,
    )


def materialize_url(
    name: str,
    source: dict[str, Any] | MarketplaceSourceURL,
    project_dir: Path,
    fetcher: RemoteFetcher | None = None,
) -> MaterializedMarketplace:
    """Materialize a URL marketplace source.

    Args:
        name: Marketplace name (key in org config) - the "alias"
        source: URL source configuration
        project_dir: Project root directory
        fetcher: Optional RemoteFetcher for URL downloads

    Returns:
        MaterializedMarketplace with materialization details including canonical_name

    Raises:
        MaterializationError: On download failure or HTTP URL (security)
    """
    if hasattr(source, "model_dump"):
        source_dict = source.model_dump()
    else:
        source_dict = dict(source)

    url = source_dict.get("url", "")
    headers = source_dict.get("headers")
    mode = source_dict.get("materialization_mode", "self_contained")

    # Security: Require HTTPS
    if not url.startswith("https://"):
        raise MaterializationError(
            f"URL must use HTTPS for security. Got: {url}",
            name,
        )

    target_dir = _get_absolute_path(project_dir, name)

    # Expand environment variables in headers
    if headers:
        headers = {k: os.path.expandvars(v) for k, v in headers.items()}

    # Pass name as fallback in case marketplace.json doesn't specify one
    result = download_and_extract(
        url,
        target_dir,
        headers=headers,
        fallback_name=name,
        fetcher=fetcher,
    )

    if not result.success:
        raise MaterializationError(result.error or "Download failed", name)

    # canonical_name comes from marketplace.json, fallback to alias name
    canonical_name = result.canonical_name or name

    return MaterializedMarketplace(
        name=name,
        canonical_name=canonical_name,
        relative_path=_get_relative_path(name),
        source_type="url",
        source_url=url,
        source_ref=None,
        materialization_mode=mode,
        materialized_at=datetime.now(timezone.utc),
        commit_sha=None,
        etag=result.etag,
        plugins_available=result.plugins or [],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────────────────────────────────────


def materialize_marketplace(
    name: str,
    source: MarketplaceSource,
    project_dir: Path,
    force_refresh: bool = False,
    fetcher: RemoteFetcher | None = None,
) -> MaterializedMarketplace:
    """Materialize a marketplace source to local filesystem.

    Routes to appropriate handler based on source type. Uses cached
    version if fresh and force_refresh is False.

    Args:
        name: Marketplace name (key in org config)
        source: Marketplace source configuration (discriminated union)
        project_dir: Project root directory
        force_refresh: Skip cache freshness check
        fetcher: Optional RemoteFetcher for URL sources

    Returns:
        MaterializedMarketplace with materialization details

    Raises:
        MaterializationError: On materialization failure
    """
    # Check cache unless force refresh
    if not force_refresh:
        manifest = load_manifest(project_dir)
        if name in manifest:
            existing = manifest[name]
            target_path = _get_absolute_path(project_dir, name)

            if target_path.exists() and is_cache_fresh(existing):
                # CRITICAL FIX: Re-read canonical_name from marketplace.json if it's
                # missing or equals the alias name (indicating an old manifest entry)
                # This ensures alias→canonical translation works with cached marketplaces
                if existing.canonical_name == existing.name:
                    discovery = _discover_plugins(target_path, fallback_name=name)
                    if discovery and discovery.canonical_name != existing.name:
                        # Update the cached entry with the correct canonical name
                        existing = MaterializedMarketplace(
                            name=existing.name,
                            canonical_name=discovery.canonical_name,
                            relative_path=existing.relative_path,
                            source_type=existing.source_type,
                            source_url=existing.source_url,
                            source_ref=existing.source_ref,
                            materialization_mode=existing.materialization_mode,
                            materialized_at=existing.materialized_at,
                            commit_sha=existing.commit_sha,
                            etag=existing.etag,
                            plugins_available=existing.plugins_available,
                        )
                        # Persist the updated canonical_name for future runs
                        manifest[name] = existing
                        save_manifest(project_dir, manifest)
                return existing

    # Route to appropriate handler using isinstance for proper type narrowing
    if isinstance(source, MarketplaceSourceGitHub):
        result = materialize_github(name, source, project_dir)
    elif isinstance(source, MarketplaceSourceGit):
        result = materialize_git(name, source, project_dir)
    elif isinstance(source, MarketplaceSourceDirectory):
        result = materialize_directory(name, source, project_dir)
    elif isinstance(source, MarketplaceSourceURL):
        result = materialize_url(name, source, project_dir, fetcher=fetcher)
    else:
        raise MaterializationError(f"Unknown source type: {source.source}", name)

    # Update manifest
    manifest = load_manifest(project_dir)
    manifest[name] = result
    save_manifest(project_dir, manifest)

    return result
