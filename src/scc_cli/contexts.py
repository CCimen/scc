"""Work context tracking for multi-team, multi-project workflows.

A WorkContext represents the developer's "working unit": team + repo + worktree.
This module tracks recent contexts to enable quick switching between projects
without requiring multiple manual steps (team switch → worktree → session).

The contexts are stored in ~/.cache/scc/contexts.json with a versioned schema:
    {"version": 1, "contexts": [...]}

Writes are atomic (temp file + rename) for safety.

Note: Concurrent writes use "last writer wins" semantics. For most CLI usage
patterns, this is fine since operations are user-initiated and sequential.

Example usage:
    # Record a context when starting work
    ctx = WorkContext(
        team="platform",
        repo_root=Path("/code/api-service"),
        worktree_path=Path("/code/api-service"),
        worktree_name="main",
    )
    record_context(ctx)

    # Get recent contexts for display
    recent = load_recent_contexts(limit=10)
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .utils.locks import file_lock, lock_path

# Schema version for future migration support
SCHEMA_VERSION = 1

# Maximum number of contexts to keep in history
MAX_CONTEXTS = 30


def _parse_dt(s: str) -> datetime:
    """Parse ISO datetime string, with fallback for malformed values."""
    try:
        # Handle Z suffix and standard ISO format
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return datetime.fromtimestamp(0, tz=timezone.utc)


def normalize_path(p: str | Path) -> Path:
    """Normalize a path for consistent comparison.

    Uses strict=False to avoid errors on non-existent paths while still
    resolving symlinks. Falls back to absolute() on OSError.
    """
    path = Path(p).expanduser()
    try:
        return path.resolve(strict=False)
    except OSError:
        # Fall back to absolute without resolving symlinks
        return path.absolute()


@dataclass
class WorkContext:
    """A developer's working context (team + repo + worktree).

    This is the primary unit of work switching in SCC. Instead of thinking
    about "sessions" and "workspaces" separately, we track the full context
    that a developer was working in.

    Attributes:
        team: The team profile name (e.g., "platform", "data"), or None for standalone mode.
        repo_root: Absolute path to the repository root.
        worktree_path: Absolute path to the worktree (may equal repo_root for main).
        worktree_name: Directory name of the worktree (stable identifier).
        branch: Git branch name at time of last use (metadata, can change).
        last_session_id: Optional session ID from last work in this context.
        last_used: When this context was last used (ISO format string).
        pinned: Whether this context is pinned to the top of the list.

    Note:
        worktree_name is the directory name (stable), while branch is metadata
        that can change. Display uses branch (if available) with worktree_name
        as fallback. This prevents context records from becoming "lost" when
        a user switches branches within the same worktree.
    """

    team: str | None
    repo_root: Path
    worktree_path: Path
    worktree_name: str
    branch: str | None = None
    last_session_id: str | None = None
    last_used: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    pinned: bool = False

    @property
    def repo_name(self) -> str:
        """Extract repository name from path."""
        return self.repo_root.name

    @property
    def team_label(self) -> str:
        """Return team name or 'standalone' for display."""
        return self.team if self.team else "standalone"

    @property
    def display_label(self) -> str:
        """Format for display in lists: 'team · repo · branch/worktree'.

        Uses branch name if available, otherwise falls back to worktree directory name.
        This provides meaningful labels (branch names) while maintaining stability
        (directory names don't change when branches switch).
        """
        name = self.branch or self.worktree_name
        return f"{self.team_label} · {self.repo_name} · {name}"

    @property
    def unique_key(self) -> tuple[str | None, Path, Path]:
        """Unique identifier for deduplication: (team, repo_root, worktree_path)."""
        return (self.team, self.repo_root, self.worktree_path)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "team": self.team,
            "repo_root": str(self.repo_root),
            "worktree_path": str(self.worktree_path),
            "worktree_name": self.worktree_name,
            "branch": self.branch,
            "last_session_id": self.last_session_id,
            "last_used": self.last_used,
            "pinned": self.pinned,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkContext:
        """Create from dictionary (JSON deserialization).

        Handles backward compatibility for contexts without branch field.
        """
        return cls(
            team=data["team"],
            repo_root=normalize_path(data["repo_root"]),
            worktree_path=normalize_path(data["worktree_path"]),
            worktree_name=data["worktree_name"],
            branch=data.get("branch"),  # Optional, may not exist in old records
            last_session_id=data.get("last_session_id"),
            last_used=data.get("last_used", datetime.now(timezone.utc).isoformat()),
            pinned=data.get("pinned", False),
        )


def _get_contexts_path() -> Path:
    """Get path to contexts cache file."""
    cache_dir = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "scc"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "contexts.json"


def _load_contexts_raw() -> list[dict[str, Any]]:
    """Load raw context data from disk."""
    path = _get_contexts_path()
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
            # Handle versioned schema
            if isinstance(data, dict) and "contexts" in data:
                contexts = data["contexts"]
                if isinstance(contexts, list):
                    return contexts
                return []
            # Legacy: raw list (migrate on next write)
            if isinstance(data, list):
                return data
            return []
    except (json.JSONDecodeError, OSError):
        return []


def _save_contexts_raw(contexts: list[dict[str, Any]]) -> None:
    """Save context data to disk atomically (temp file + rename)."""
    path = _get_contexts_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    # Versioned schema
    data = {"version": SCHEMA_VERSION, "contexts": contexts}

    # Write to temp file then rename for atomicity
    fd, temp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(temp_path, path)
    except Exception:
        # Clean up temp file on failure
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def load_recent_contexts(limit: int = 10) -> list[WorkContext]:
    """Load recent contexts, sorted by pinned first then recency.

    Args:
        limit: Maximum number of contexts to return.

    Returns:
        List of WorkContext objects, pinned first, then by last_used descending.
    """
    raw_data = _load_contexts_raw()
    contexts = [WorkContext.from_dict(d) for d in raw_data]

    # Sort: pinned=True first (True > False with reverse=True),
    # then by timestamp descending (larger = more recent)
    contexts.sort(key=lambda c: (c.pinned, _parse_dt(c.last_used)), reverse=True)

    return contexts[:limit]


def _merge_contexts(existing: WorkContext, incoming: WorkContext) -> WorkContext:
    """Merge incoming context update with existing context.

    Preserves pinned status, updates timestamps, session info, and branch.
    """
    return WorkContext(
        team=incoming.team,
        repo_root=incoming.repo_root,
        worktree_path=incoming.worktree_path,
        worktree_name=incoming.worktree_name,
        branch=incoming.branch or existing.branch,  # Prefer new, fallback to existing
        last_session_id=incoming.last_session_id or existing.last_session_id,
        last_used=datetime.now(timezone.utc).isoformat(),
        pinned=existing.pinned,  # Preserve pinned status
    )


def record_context(context: WorkContext) -> None:
    """Record a context, updating if it already exists.

    If a context with the same (team, repo_root, worktree_path) exists,
    it's updated with new last_used and last_session_id.

    Note: This function does not mutate the input context.

    Args:
        context: The context to record.
    """
    lock_file = lock_path("contexts")
    with file_lock(lock_file):
        raw_data = _load_contexts_raw()
        existing = [WorkContext.from_dict(d) for d in raw_data]

        # Normalize the incoming context paths
        normalized = WorkContext(
            team=context.team,
            repo_root=normalize_path(context.repo_root),
            worktree_path=normalize_path(context.worktree_path),
            worktree_name=context.worktree_name,
            branch=context.branch,  # Preserve branch for Quick Resume display
            last_session_id=context.last_session_id,
            last_used=datetime.now(timezone.utc).isoformat(),
            pinned=context.pinned,
        )

        # Find and update or append
        key = normalized.unique_key
        found = False
        for i, ctx in enumerate(existing):
            if ctx.unique_key == key:
                existing[i] = _merge_contexts(ctx, normalized)
                found = True
                break

        if not found:
            existing.append(normalized)

        # Sort by recency and trim to MAX_CONTEXTS
        # Keep pinned contexts even if they're old
        pinned = [c for c in existing if c.pinned]
        unpinned = [c for c in existing if not c.pinned]

        # Sort both lists by recency for consistent ordering
        pinned.sort(key=lambda c: _parse_dt(c.last_used), reverse=True)
        unpinned.sort(key=lambda c: _parse_dt(c.last_used), reverse=True)

        # Trim unpinned to fit within MAX_CONTEXTS (minus pinned count)
        max_unpinned = MAX_CONTEXTS - len(pinned)
        if max_unpinned < 0:
            max_unpinned = 0
        unpinned = unpinned[:max_unpinned]

        final = pinned + unpinned
        _save_contexts_raw([c.to_dict() for c in final])


def toggle_pin(team: str, repo_root: str | Path, worktree_path: str | Path) -> bool | None:
    """Toggle the pinned status of a context.

    Args:
        team: Team name.
        repo_root: Repository root path.
        worktree_path: Worktree path.

    Returns:
        New pinned status (True if now pinned, False if unpinned),
        or None if context not found.
    """
    lock_file = lock_path("contexts")
    with file_lock(lock_file):
        # Load all contexts as WorkContext objects (normalizes paths once)
        contexts = [WorkContext.from_dict(d) for d in _load_contexts_raw()]
        key = (team, normalize_path(repo_root), normalize_path(worktree_path))

        for i, ctx in enumerate(contexts):
            if ctx.unique_key == key:
                # Create new context with toggled pinned status
                contexts[i] = WorkContext(
                    team=ctx.team,
                    repo_root=ctx.repo_root,
                    worktree_path=ctx.worktree_path,
                    worktree_name=ctx.worktree_name,
                    branch=ctx.branch,  # Preserve branch metadata
                    last_session_id=ctx.last_session_id,
                    last_used=ctx.last_used,
                    pinned=not ctx.pinned,
                )
                _save_contexts_raw([c.to_dict() for c in contexts])
                return contexts[i].pinned

    return None


def clear_contexts() -> int:
    """Clear all contexts from cache.

    Returns:
        Number of contexts cleared.
    """
    lock_file = lock_path("contexts")
    with file_lock(lock_file):
        raw_data = _load_contexts_raw()
        count = len(raw_data)
        _save_contexts_raw([])
        return count


def get_context_for_path(worktree_path: str | Path, team: str | None = None) -> WorkContext | None:
    """Find a context matching the given worktree path.

    Uses normalized path comparison for robustness.

    Args:
        worktree_path: The worktree path to search for.
        team: Optional team filter.

    Returns:
        Matching context or None.
    """
    normalized = normalize_path(worktree_path)
    contexts = load_recent_contexts(limit=MAX_CONTEXTS)

    for ctx in contexts:
        if ctx.worktree_path == normalized:
            if team is None or ctx.team == team:
                return ctx
    return None
