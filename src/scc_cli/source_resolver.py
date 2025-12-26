"""
Source resolver for organization config imports.

Resolves human-friendly source strings to fetchable URLs or file paths.
Supports GitHub/GitLab shorthands while keeping the runtime fetch-only (no git clone).

Resolution precedence (order matters to avoid collisions):
1. Local file: exists on disk OR starts with ./ ../ / ~ OR matches Windows drive
2. URL: starts with http:// or https://
3. Shorthand: github: / gitlab: / <host>: patterns
4. Error: unknown format with examples

Examples:
    # Direct HTTPS
    https://example.com/org-config.json

    # Local file
    ./org-config.json
    file:./org-config.json

    # GitHub shorthand
    github:sundsvall/scc-org:org.json           # default branch (floating)
    github:sundsvall/scc-org@v1.2.0:org.json    # tag (pinned)
    github:sundsvall/scc-org@abc1234:org.json   # SHA (pinned)

    # GitLab shorthand
    gitlab:myco/platform/scc@v1.0:org.json

    # Self-hosted
    gitlab.mycompany.com:team/config@main:org.json
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# ═══════════════════════════════════════════════════════════════════════════════
# Data Types
# ═══════════════════════════════════════════════════════════════════════════════

SourceProvider = Literal["file", "https", "github", "gitlab", "custom"]


@dataclass(frozen=True)
class ResolvedSource:
    """Result of resolving a source string.

    Attributes:
        original: The original source string as provided by user.
        resolved_url: The resolved HTTPS URL or file path for fetching.
        provider: The detected provider type.
        host: The host for custom providers (e.g., gitlab.mycompany.com).
        owner: Repository owner/org (for shorthand sources).
        repo: Repository name (for shorthand sources).
        ref: Git reference (tag, SHA, branch) if specified.
        path: Path within the repository.
        is_pinned: True if ref is a tag or SHA (not a branch or default).
        is_file: True if this is a local file path.
    """

    original: str
    resolved_url: str
    provider: SourceProvider
    host: str | None = None
    owner: str | None = None
    repo: str | None = None
    ref: str | None = None
    path: str | None = None
    is_pinned: bool = False
    is_file: bool = False


@dataclass(frozen=True)
class ResolveError:
    """Error during source resolution.

    Attributes:
        message: Human-readable error message.
        source: The source string that failed.
        suggestion: Suggested fix or examples.
    """

    message: str
    source: str
    suggestion: str | None = None


# ═══════════════════════════════════════════════════════════════════════════════
# Resolution Patterns
# ═══════════════════════════════════════════════════════════════════════════════

# Windows drive pattern: C:\ or D:/
WINDOWS_DRIVE_PATTERN = re.compile(r"^[A-Za-z]:[/\\]")

# GitHub shorthand: github:owner/repo@ref:path or github:owner/repo:path
GITHUB_PATTERN = re.compile(
    r"^github:(?P<owner>[^/@:]+)/(?P<repo>[^/@:]+)(?:@(?P<ref>[^:]+))?:(?P<path>.+)$"
)

# GitLab shorthand: gitlab:owner/repo@ref:path (supports nested groups)
GITLAB_PATTERN = re.compile(r"^gitlab:(?P<owner_repo>[^@:]+)(?:@(?P<ref>[^:]+))?:(?P<path>.+)$")

# Custom host shorthand: host.com:owner/repo@ref:path
# Must have at least one dot in host to distinguish from Windows paths
CUSTOM_HOST_PATTERN = re.compile(
    r"^(?P<host>[a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z0-9][-a-zA-Z0-9.]*)"
    r":(?P<owner_repo>[^@:]+)(?:@(?P<ref>[^:]+))?:(?P<path>.+)$"
)

# Pinned ref detection: starts with v followed by number, or is hex SHA
TAG_PATTERN = re.compile(r"^v?\d+")
SHA_PATTERN = re.compile(r"^[0-9a-f]{7,40}$", re.IGNORECASE)


# ═══════════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════════


def _is_pinned_ref(ref: str | None) -> bool:
    """Determine if a git ref is pinned (tag or SHA) vs floating (branch).

    Pinned refs are:
    - Tags: v1.0.0, v2, 1.0.0, etc.
    - SHAs: 7+ character hex strings

    Everything else (main, develop, feature/x) is considered floating.
    """
    if not ref:
        return False

    # Check if it's a SHA (7-40 hex characters)
    if SHA_PATTERN.match(ref):
        return True

    # Check if it looks like a version tag
    if TAG_PATTERN.match(ref):
        return True

    return False


def _is_local_file_path(source: str) -> bool:
    r"""Check if source looks like a local file path.

    Checks (in order):
    1. Starts with explicit file: prefix
    2. Starts with ./ or ../
    3. Starts with / (Unix absolute)
    4. Starts with ~ (home directory)
    5. Matches Windows drive pattern (C:\, D:/, etc.)
    6. Actually exists on disk
    """
    # Explicit file: prefix
    if source.startswith("file:"):
        return True

    # Relative paths
    if source.startswith("./") or source.startswith("../"):
        return True

    # Unix absolute path
    if source.startswith("/"):
        return True

    # Home directory
    if source.startswith("~"):
        return True

    # Windows drive pattern
    if WINDOWS_DRIVE_PATTERN.match(source):
        return True

    # Check if file actually exists (catches bare filenames like "org.json")
    try:
        path = Path(source).expanduser()
        if path.exists():
            return True
    except (OSError, ValueError):
        pass

    return False


def _resolve_file_source(source: str) -> ResolvedSource:
    """Resolve a local file source."""
    # Strip file: prefix if present
    path_str = source[5:] if source.startswith("file:") else source

    # Expand and resolve path
    path = Path(path_str).expanduser().resolve()

    return ResolvedSource(
        original=source,
        resolved_url=str(path),
        provider="file",
        path=str(path),
        is_pinned=True,  # Local files are considered "pinned" (deterministic)
        is_file=True,
    )


def _resolve_github_source(source: str) -> ResolvedSource | ResolveError:
    """Resolve a GitHub shorthand source."""
    match = GITHUB_PATTERN.match(source)
    if not match:
        return ResolveError(
            message="Invalid GitHub source format",
            source=source,
            suggestion="Use: github:owner/repo@ref:path (e.g., github:acme/config@v1.0:org.json)",
        )

    owner = match.group("owner")
    repo = match.group("repo")
    ref = match.group("ref") or "HEAD"  # Default to HEAD (main/master)
    path = match.group("path")

    # Build raw.githubusercontent.com URL
    resolved_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{ref}/{path}"

    return ResolvedSource(
        original=source,
        resolved_url=resolved_url,
        provider="github",
        host="github.com",
        owner=owner,
        repo=repo,
        ref=ref if match.group("ref") else None,
        path=path,
        is_pinned=_is_pinned_ref(match.group("ref")),
        is_file=False,
    )


def _resolve_gitlab_source(source: str) -> ResolvedSource | ResolveError:
    """Resolve a GitLab shorthand source."""
    match = GITLAB_PATTERN.match(source)
    if not match:
        return ResolveError(
            message="Invalid GitLab source format",
            source=source,
            suggestion="Use: gitlab:owner/repo@ref:path (e.g., gitlab:acme/config@v1.0:org.json)",
        )

    owner_repo = match.group("owner_repo")  # Can include nested groups
    ref = match.group("ref") or "main"
    path = match.group("path")

    # Split owner/repo (last segment is repo, rest is owner/group)
    parts = owner_repo.split("/")
    if len(parts) < 2:
        return ResolveError(
            message="GitLab source must include owner/repo",
            source=source,
            suggestion="Use: gitlab:owner/repo@ref:path",
        )

    owner = "/".join(parts[:-1])
    repo = parts[-1]

    # Build gitlab.com raw URL
    resolved_url = f"https://gitlab.com/{owner_repo}/-/raw/{ref}/{path}"

    return ResolvedSource(
        original=source,
        resolved_url=resolved_url,
        provider="gitlab",
        host="gitlab.com",
        owner=owner,
        repo=repo,
        ref=ref if match.group("ref") else None,
        path=path,
        is_pinned=_is_pinned_ref(match.group("ref")),
        is_file=False,
    )


def _resolve_custom_host_source(source: str) -> ResolvedSource | ResolveError:
    """Resolve a custom-hosted GitLab-style source."""
    match = CUSTOM_HOST_PATTERN.match(source)
    if not match:
        return ResolveError(
            message="Invalid custom host source format",
            source=source,
            suggestion="Use: host.com:owner/repo@ref:path",
        )

    host = match.group("host")
    owner_repo = match.group("owner_repo")
    ref = match.group("ref") or "main"
    path = match.group("path")

    # Split owner/repo
    parts = owner_repo.split("/")
    if len(parts) < 2:
        return ResolveError(
            message="Custom host source must include owner/repo",
            source=source,
            suggestion=f"Use: {host}:owner/repo@ref:path",
        )

    owner = "/".join(parts[:-1])
    repo = parts[-1]

    # Assume GitLab-style raw URL for custom hosts
    resolved_url = f"https://{host}/{owner_repo}/-/raw/{ref}/{path}"

    return ResolvedSource(
        original=source,
        resolved_url=resolved_url,
        provider="custom",
        host=host,
        owner=owner,
        repo=repo,
        ref=ref if match.group("ref") else None,
        path=path,
        is_pinned=_is_pinned_ref(match.group("ref")),
        is_file=False,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Main Resolution Function
# ═══════════════════════════════════════════════════════════════════════════════


def resolve_source(source: str) -> ResolvedSource | ResolveError:
    """Resolve a source string to a fetchable URL or file path.

    Resolution precedence (order matters to avoid collisions):
    1. Local file: exists on disk OR starts with ./ ../ / ~ OR Windows drive
    2. URL: starts with http:// or https://
    3. Shorthand: github: / gitlab: / <host>: patterns
    4. Error: unknown format with examples

    Args:
        source: The source string to resolve.

    Returns:
        ResolvedSource on success, ResolveError on failure.

    Examples:
        >>> resolve_source("./org.json")
        ResolvedSource(provider="file", is_file=True, ...)

        >>> resolve_source("github:acme/config@v1.0:org.json")
        ResolvedSource(provider="github", is_pinned=True, ...)

        >>> resolve_source("https://example.com/org.json")
        ResolvedSource(provider="https", ...)
    """
    source = source.strip()

    if not source:
        return ResolveError(
            message="Empty source string",
            source=source,
            suggestion="Provide a URL, file path, or shorthand (github:owner/repo@ref:path)",
        )

    # 1. Check for local file path FIRST (prevents collisions)
    if _is_local_file_path(source):
        return _resolve_file_source(source)

    # 2. Check for HTTPS URL
    if source.startswith("https://"):
        return ResolvedSource(
            original=source,
            resolved_url=source,
            provider="https",
            is_pinned=False,  # Can't determine pinning for raw URLs
            is_file=False,
        )

    # 2b. Reject HTTP (security)
    if source.startswith("http://"):
        return ResolveError(
            message="HTTP not allowed (security risk)",
            source=source,
            suggestion="Use HTTPS: " + source.replace("http://", "https://"),
        )

    # 3. Check for shorthands
    if source.startswith("github:"):
        return _resolve_github_source(source)

    if source.startswith("gitlab:"):
        return _resolve_gitlab_source(source)

    # 3b. Check for custom host shorthand (must have dot in host)
    if ":" in source and "." in source.split(":")[0]:
        result = _resolve_custom_host_source(source)
        if not isinstance(result, ResolveError):
            return result
        # Fall through to unknown format error with better examples

    # 4. Unknown format
    return ResolveError(
        message="Unknown source format",
        source=source,
        suggestion="""Valid formats:
  • Local file:  ./org.json, ~/config/org.json
  • HTTPS URL:   https://example.com/org.json
  • GitHub:      github:owner/repo@tag:path.json
  • GitLab:      gitlab:owner/repo@tag:path.json
  • Custom host: gitlab.company.com:owner/repo@tag:path.json""",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Auth Detection
# ═══════════════════════════════════════════════════════════════════════════════


def detect_auth_env_var(resolved: ResolvedSource) -> str | None:
    """Detect appropriate auth environment variable for a resolved source.

    Priority:
    1. SCC_ORG_TOKEN (SCC-specific, always checked first)
    2. GITHUB_TOKEN (for GitHub sources)
    3. GITLAB_TOKEN (for GitLab sources)

    Args:
        resolved: The resolved source to detect auth for.

    Returns:
        Environment variable name if found and set, None otherwise.
    """
    # SCC-specific token takes priority
    if os.environ.get("SCC_ORG_TOKEN"):
        return "SCC_ORG_TOKEN"

    # Provider-specific tokens
    if resolved.provider == "github" and os.environ.get("GITHUB_TOKEN"):
        return "GITHUB_TOKEN"

    if resolved.provider in ("gitlab", "custom") and os.environ.get("GITLAB_TOKEN"):
        return "GITLAB_TOKEN"

    return None


def build_auth_spec(resolved: ResolvedSource, explicit_auth: str | None = None) -> str | None:
    """Build auth specification for a resolved source.

    Args:
        resolved: The resolved source.
        explicit_auth: Explicitly provided auth spec (e.g., "env:MY_TOKEN").

    Returns:
        Auth spec string (e.g., "env:GITHUB_TOKEN") or None if no auth.
    """
    # Explicit auth takes priority
    if explicit_auth:
        return explicit_auth

    # Local files don't need auth
    if resolved.is_file:
        return None

    # Detect from environment
    env_var = detect_auth_env_var(resolved)
    if env_var:
        return f"env:{env_var}"

    return None
