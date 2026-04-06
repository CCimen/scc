"""
Git clone, URL download, and plugin discovery for marketplace materialization.

Extracted from materialize.py to keep modules under 800 lines.
Contains low-level operations: git clone, tarball download/extract, and
marketplace plugin discovery.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

from scc_cli.ports.remote_fetcher import RemoteFetcher

# ─────────────────────────────────────────────────────────────────────────────
# Result Dataclasses
# ─────────────────────────────────────────────────────────────────────────────


@dataclass
class CloneResult:
    """Result of a git clone operation."""

    success: bool
    commit_sha: str | None = None
    plugins: list[str] | None = None
    canonical_name: str | None = None  # Name from marketplace.json
    error: str | None = None


@dataclass
class DownloadResult:
    """Result of a URL download operation."""

    success: bool
    etag: str | None = None
    plugins: list[str] | None = None
    canonical_name: str | None = None  # Name from marketplace.json
    error: str | None = None


@dataclass
class DiscoveryResult:
    """Result of discovering plugins and metadata from a marketplace."""

    plugins: list[str]
    canonical_name: str  # The 'name' field from marketplace.json


# ─────────────────────────────────────────────────────────────────────────────
# Exceptions (imported from parent for type usage)
# ─────────────────────────────────────────────────────────────────────────────

# We import the error lazily to avoid circular imports; callers already
# import GitNotAvailableError from materialize.py which re-exports it.


# ─────────────────────────────────────────────────────────────────────────────
# Plugin Discovery
# ─────────────────────────────────────────────────────────────────────────────


def _discover_plugins(marketplace_dir: Path, fallback_name: str = "") -> DiscoveryResult | None:
    """Discover plugins and canonical name from a marketplace directory.

    Args:
        marketplace_dir: Root of the marketplace
        fallback_name: Name to use if marketplace.json doesn't specify one

    Returns:
        DiscoveryResult with plugins and canonical name, or None if structure is invalid
    """
    manifest_path = marketplace_dir / ".claude-plugin" / "marketplace.json"

    if not manifest_path.exists():
        return None

    try:
        data = json.loads(manifest_path.read_text())
        plugins = data.get("plugins", [])
        plugin_names = [p.get("name", "") for p in plugins if isinstance(p, dict)]

        # Get canonical name from marketplace.json - this is what Claude Code uses
        canonical_name = data.get("name", fallback_name)
        if not canonical_name:
            canonical_name = fallback_name

        return DiscoveryResult(plugins=plugin_names, canonical_name=canonical_name)
    except (json.JSONDecodeError, KeyError):
        return DiscoveryResult(plugins=[], canonical_name=fallback_name)


# ─────────────────────────────────────────────────────────────────────────────
# Git Operations
# ─────────────────────────────────────────────────────────────────────────────


def run_git_clone(
    url: str,
    target_dir: Path,
    branch: str = "main",
    depth: int = 1,
    fallback_name: str = "",
) -> CloneResult:
    """Clone a git repository to target directory.

    Args:
        url: Git clone URL
        target_dir: Directory to clone into
        branch: Branch to checkout
        depth: Clone depth (1 for shallow)
        fallback_name: Fallback name if marketplace.json doesn't specify one

    Returns:
        CloneResult with success status, commit SHA, and canonical name
    """
    # Import here to avoid circular dependency at module level
    from scc_cli.marketplace.materialize import GitNotAvailableError

    try:
        # Clean target directory if exists
        if target_dir.exists():
            shutil.rmtree(target_dir)

        # Clone with shallow depth for efficiency
        cmd = [
            "git",
            "clone",
            "--depth",
            str(depth),
            "--branch",
            branch,
            "--",
            url,
            str(target_dir),
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            return CloneResult(
                success=False,
                error=result.stderr or "Clone failed",
            )

        # Get commit SHA
        sha_result = subprocess.run(
            ["git", "-C", str(target_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
        )
        commit_sha = sha_result.stdout.strip() if sha_result.returncode == 0 else None

        # Discover plugins and canonical name
        discovery = _discover_plugins(target_dir, fallback_name=fallback_name)

        if discovery is None:
            return CloneResult(
                success=False,
                commit_sha=commit_sha,
                error="Missing .claude-plugin/marketplace.json",
            )

        return CloneResult(
            success=True,
            commit_sha=commit_sha,
            plugins=discovery.plugins,
            canonical_name=discovery.canonical_name,
        )

    except FileNotFoundError:
        raise GitNotAvailableError()
    except subprocess.TimeoutExpired:
        return CloneResult(
            success=False,
            error="Clone operation timed out",
        )


# ─────────────────────────────────────────────────────────────────────────────
# URL Operations
# ─────────────────────────────────────────────────────────────────────────────


def download_and_extract(
    url: str,
    target_dir: Path,
    headers: dict[str, str] | None = None,
    fallback_name: str = "",
    fetcher: RemoteFetcher | None = None,
) -> DownloadResult:
    """Download and extract marketplace from URL.

    Args:
        url: HTTPS URL to download
        target_dir: Directory to extract into
        headers: Optional HTTP headers
        fallback_name: Fallback name if marketplace.json doesn't specify one
        fetcher: Optional RemoteFetcher for HTTP downloads

    Returns:
        DownloadResult with success status, ETag, and canonical name
    """
    import tarfile
    import tempfile

    remote_fetcher = fetcher
    if remote_fetcher is None:
        from scc_cli.bootstrap import get_default_adapters

        remote_fetcher = get_default_adapters().remote_fetcher

    try:
        response = remote_fetcher.get(url, headers=headers, timeout=60)
    except Exception as exc:
        return DownloadResult(
            success=False,
            error=str(exc),
        )

    if response.status_code != 200:
        return DownloadResult(
            success=False,
            error=f"HTTP {response.status_code}: Failed to download marketplace",
        )

    etag = response.headers.get("ETag")

    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz") as tmp:
        tmp.write(response.content)
        tmp_path = Path(tmp.name)

    try:
        # Clean target directory if exists
        if target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True)

        # Extract archive (path-safe)
        with tarfile.open(tmp_path, "r:*") as tar:
            safe_members: list[tarfile.TarInfo] = []
            for member in tar.getmembers():
                member_path = PurePosixPath(member.name)
                windows_member_path = PureWindowsPath(member.name)
                if member_path.is_absolute() or windows_member_path.is_absolute():
                    return DownloadResult(
                        success=False,
                        error=f"Unsafe archive member (absolute path): {member.name}",
                    )
                if ".." in member_path.parts or ".." in windows_member_path.parts:
                    return DownloadResult(
                        success=False,
                        error=f"Unsafe archive member (path traversal): {member.name}",
                    )
                if "" in member_path.parts or "" in windows_member_path.parts:
                    return DownloadResult(
                        success=False,
                        error=f"Unsafe archive member (empty path segment): {member.name}",
                    )
                if "\\" in member.name or windows_member_path.drive:
                    return DownloadResult(
                        success=False,
                        error=f"Unsafe archive member (windows path): {member.name}",
                    )
                if (
                    member.islnk()
                    or member.issym()
                    or member.ischr()
                    or member.isblk()
                    or member.isfifo()
                ):
                    return DownloadResult(
                        success=False,
                        error=f"Unsafe archive member (link/device): {member.name}",
                    )
                safe_members.append(member)

            tar.extractall(target_dir, members=safe_members)

        # Discover plugins and canonical name
        discovery = _discover_plugins(target_dir, fallback_name=fallback_name)

        if discovery is None:
            return DownloadResult(
                success=False,
                error="Missing .claude-plugin/marketplace.json",
            )

        return DownloadResult(
            success=True,
            etag=etag,
            plugins=discovery.plugins,
            canonical_name=discovery.canonical_name,
        )
    finally:
        tmp_path.unlink(missing_ok=True)
