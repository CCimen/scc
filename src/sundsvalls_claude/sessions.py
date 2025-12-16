"""
Session management for Claude Code.

Tracks recent sessions, workspaces, containers, and allows resuming.

Container Linking:
- Sessions are linked to their Docker container names
- Container names are deterministic: scc-<workspace>-<hash>
- This enables seamless resume of Claude Code conversations
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from dataclasses import dataclass, asdict

from . import config


# ═══════════════════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class SessionRecord:
    """A recorded Claude Code session with container linking."""

    workspace: str
    team: Optional[str] = None
    name: Optional[str] = None
    container_name: Optional[str] = None
    branch: Optional[str] = None
    last_used: Optional[str] = None
    created_at: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: dict) -> "SessionRecord":
        """Create from dictionary."""
        return cls(
            workspace=data.get("workspace", ""),
            team=data.get("team"),
            name=data.get("name"),
            container_name=data.get("container_name"),
            branch=data.get("branch"),
            last_used=data.get("last_used"),
            created_at=data.get("created_at"),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Session Operations
# ═══════════════════════════════════════════════════════════════════════════════


def list_recent(limit: int = 10) -> List[dict]:
    """
    List recent sessions with container and relative time info.

    Returns list of dicts with: name, workspace, team, last_used, container_name, branch
    """
    sessions = _load_sessions()

    # Sort by last_used descending
    sessions.sort(key=lambda s: s.get("last_used", ""), reverse=True)

    # Limit results
    sessions = sessions[:limit]

    # Format for display
    result = []
    for s in sessions:
        last_used = s.get("last_used", "")
        if last_used:
            try:
                dt = datetime.fromisoformat(last_used)
                last_used = format_relative_time(dt)
            except ValueError:
                pass

        result.append({
            "name": s.get("name") or _generate_session_name(s),
            "workspace": s.get("workspace", ""),
            "team": s.get("team"),
            "last_used": last_used,
            "container_name": s.get("container_name"),
            "branch": s.get("branch"),
        })

    return result


def _generate_session_name(session: dict) -> str:
    """Generate a display name for a session without an explicit name."""
    workspace = session.get("workspace", "")
    if workspace:
        return Path(workspace).name
    return "Unnamed"


def record_session(
    workspace: str,
    team: Optional[str] = None,
    session_name: Optional[str] = None,
    container_name: Optional[str] = None,
    branch: Optional[str] = None,
) -> SessionRecord:
    """
    Record a new session or update an existing one.

    Sessions are keyed by workspace + branch combination.
    """
    sessions = _load_sessions()
    now = datetime.now().isoformat()

    # Find existing session for this workspace+branch
    existing_idx = None
    for idx, s in enumerate(sessions):
        if s.get("workspace") == workspace and s.get("branch") == branch:
            existing_idx = idx
            break

    record = SessionRecord(
        workspace=workspace,
        team=team,
        name=session_name,
        container_name=container_name,
        branch=branch,
        last_used=now,
        created_at=sessions[existing_idx].get("created_at", now) if existing_idx is not None else now,
    )

    if existing_idx is not None:
        # Update existing
        sessions[existing_idx] = record.to_dict()
    else:
        # Add new
        sessions.insert(0, record.to_dict())

    _save_sessions(sessions)
    return record


def update_session_container(
    workspace: str,
    container_name: str,
    branch: Optional[str] = None,
) -> None:
    """
    Update the container name for an existing session.

    Called when a container is created for a session.
    """
    sessions = _load_sessions()

    for s in sessions:
        if s.get("workspace") == workspace:
            if branch is None or s.get("branch") == branch:
                s["container_name"] = container_name
                s["last_used"] = datetime.now().isoformat()
                break

    _save_sessions(sessions)


def find_session_by_container(container_name: str) -> Optional[dict]:
    """
    Find a session by its container name.

    Useful for resume operations.
    """
    sessions = _load_sessions()
    for s in sessions:
        if s.get("container_name") == container_name:
            return s
    return None


def find_session_by_workspace(
    workspace: str,
    branch: Optional[str] = None,
) -> Optional[dict]:
    """
    Find a session by workspace and optionally branch.

    Returns the most recent matching session.
    """
    sessions = _load_sessions()

    # Sort by last_used descending
    sessions.sort(key=lambda s: s.get("last_used", ""), reverse=True)

    for s in sessions:
        if s.get("workspace") == workspace:
            if branch is None or s.get("branch") == branch:
                return s
    return None


def get_container_for_workspace(
    workspace: str,
    branch: Optional[str] = None,
) -> Optional[str]:
    """
    Get the container name for a workspace (and optionally branch).

    Returns None if no container has been recorded.
    """
    session = find_session_by_workspace(workspace, branch)
    if session:
        return session.get("container_name")
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# History Management
# ═══════════════════════════════════════════════════════════════════════════════


def clear_history() -> int:
    """
    Clear all session history.

    Returns the number of sessions cleared.
    """
    sessions = _load_sessions()
    count = len(sessions)
    _save_sessions([])
    return count


def remove_session(workspace: str, branch: Optional[str] = None) -> bool:
    """
    Remove a specific session from history.

    Args:
        workspace: Workspace path to remove
        branch: Optional branch (if None, removes all sessions for workspace)

    Returns:
        True if session was found and removed
    """
    sessions = _load_sessions()
    original_count = len(sessions)

    if branch:
        sessions = [
            s for s in sessions
            if not (s.get("workspace") == workspace and s.get("branch") == branch)
        ]
    else:
        sessions = [s for s in sessions if s.get("workspace") != workspace]

    _save_sessions(sessions)
    return len(sessions) < original_count


def prune_orphaned_sessions() -> int:
    """
    Remove sessions whose workspaces no longer exist.

    Returns the number of sessions pruned.
    """
    sessions = _load_sessions()
    original_count = len(sessions)

    valid_sessions = [
        s for s in sessions
        if Path(s.get("workspace", "")).expanduser().exists()
    ]

    _save_sessions(valid_sessions)
    return original_count - len(valid_sessions)


# ═══════════════════════════════════════════════════════════════════════════════
# Claude Code Integration
# ═══════════════════════════════════════════════════════════════════════════════


def get_claude_sessions_dir() -> Path:
    """Get the Claude Code sessions directory."""
    # Claude Code stores sessions in ~/.claude/
    return Path.home() / ".claude"


def get_claude_recent_sessions() -> List[dict]:
    """
    Try to get recent sessions from Claude Code's own storage.

    This reads from ~/.claude/ if available.
    Note: Claude Code's session format may change; this is best-effort.
    """
    claude_dir = get_claude_sessions_dir()
    sessions_file = claude_dir / "sessions.json"

    if sessions_file.exists():
        try:
            with open(sessions_file) as f:
                data = json.load(f)
            return data.get("sessions", [])
        except (IOError, json.JSONDecodeError):
            pass

    return []


# ═══════════════════════════════════════════════════════════════════════════════
# Internal Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _load_sessions() -> List[dict]:
    """Load sessions from the config file."""
    sessions_file = config.SESSIONS_FILE

    if sessions_file.exists():
        try:
            with open(sessions_file) as f:
                data = json.load(f)
            return data.get("sessions", [])
        except (IOError, json.JSONDecodeError):
            pass

    return []


def _save_sessions(sessions: List[dict]) -> None:
    """Save sessions to the config file."""
    sessions_file = config.SESSIONS_FILE

    # Ensure parent directory exists
    sessions_file.parent.mkdir(parents=True, exist_ok=True)

    with open(sessions_file, "w") as f:
        json.dump({"sessions": sessions}, f, indent=2)


def format_relative_time(dt: datetime) -> str:
    """Format a datetime as relative time (e.g., '2h ago')."""
    now = datetime.now()
    diff = now - dt

    seconds = diff.total_seconds()

    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes}m ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours}h ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days}d ago"
    else:
        weeks = int(seconds / 604800)
        return f"{weeks}w ago"
