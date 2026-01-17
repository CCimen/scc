"""
Manage Claude Code sessions.

Track recent sessions, workspaces, containers, and enable resuming.

Container Linking:
- Sessions are linked to their Docker container names
- Container names are deterministic: scc-<workspace>-<hash>
- This enables seamless resume of Claude Code conversations
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from scc_cli.application.sessions import SessionService
from scc_cli.bootstrap import build_session_store
from scc_cli.ports.filesystem import Filesystem
from scc_cli.ports.session_models import SessionFilter, SessionRecord, SessionSummary
from scc_cli.ports.session_store import SessionStore
from scc_cli.ui.time_format import format_relative_time_from_datetime

from .core.constants import AGENT_CONFIG_DIR

# ═══════════════════════════════════════════════════════════════════════════════
# Store Wiring
# ═══════════════════════════════════════════════════════════════════════════════


def get_session_store(filesystem: Filesystem | None = None) -> SessionStore:
    """Return the JSON session store adapter."""
    return build_session_store(filesystem)


def get_session_service(filesystem: Filesystem | None = None) -> SessionService:
    """Return the session service wired to the JSON store."""
    return SessionService(store=get_session_store(filesystem))


# ═══════════════════════════════════════════════════════════════════════════════
# Session Operations
# ═══════════════════════════════════════════════════════════════════════════════


def get_most_recent(filesystem: Filesystem | None = None) -> SessionSummary | None:
    """Return the most recently used session summary."""
    recent = list_recent(limit=1, include_all=True, filesystem=filesystem)
    return recent[0] if recent else None


def list_recent(
    limit: int = 10,
    team: str | None = None,
    include_all: bool | None = None,
    *,
    filesystem: Filesystem | None = None,
) -> list[SessionSummary]:
    """Return recent sessions from the store."""
    resolved_include_all = team is None if include_all is None else include_all
    service = get_session_service(filesystem)
    result = service.list_recent(
        SessionFilter(limit=limit, team=team, include_all=resolved_include_all)
    )
    return result.sessions


def record_session(
    workspace: str,
    team: str | None = None,
    session_name: str | None = None,
    container_name: str | None = None,
    branch: str | None = None,
    *,
    filesystem: Filesystem | None = None,
) -> SessionRecord:
    """Record a new session or update an existing one."""
    service = get_session_service(filesystem)
    return service.record_session(
        workspace=workspace,
        team=team,
        session_name=session_name,
        container_name=container_name,
        branch=branch,
    )


def update_session_container(
    workspace: str,
    container_name: str,
    branch: str | None = None,
    *,
    filesystem: Filesystem | None = None,
) -> None:
    """Update the container name for an existing session."""
    service = get_session_service(filesystem)
    service.update_session_container(
        workspace=workspace,
        container_name=container_name,
        branch=branch,
    )


def find_session_by_container(
    container_name: str,
    *,
    filesystem: Filesystem | None = None,
) -> SessionRecord | None:
    """Find a session by its container name."""
    sessions_list = get_session_store(filesystem).load_sessions()
    for record in sessions_list:
        if record.container_name == container_name:
            return record
    return None


def find_session_by_workspace(
    workspace: str,
    branch: str | None = None,
    *,
    filesystem: Filesystem | None = None,
) -> SessionRecord | None:
    """Find a session by workspace and optionally branch."""
    sessions_list = get_session_store(filesystem).load_sessions()
    sessions_list.sort(key=lambda record: record.last_used or "", reverse=True)
    for record in sessions_list:
        if record.workspace == workspace and (branch is None or record.branch == branch):
            return record
    return None


def get_container_for_workspace(
    workspace: str,
    branch: str | None = None,
    *,
    filesystem: Filesystem | None = None,
) -> str | None:
    """Return the container name for a workspace (and optionally branch)."""
    session = find_session_by_workspace(workspace, branch, filesystem=filesystem)
    return session.container_name if session else None


# ═══════════════════════════════════════════════════════════════════════════════
# History Management
# ═══════════════════════════════════════════════════════════════════════════════


def clear_history(filesystem: Filesystem | None = None) -> int:
    """Clear all session history and return count cleared."""
    store = get_session_store(filesystem)
    with store.lock():
        sessions_list = store.load_sessions()
        count = len(sessions_list)
        store.save_sessions([])
        return count


def remove_session(
    workspace: str,
    branch: str | None = None,
    *,
    filesystem: Filesystem | None = None,
) -> bool:
    """Remove a specific session from history."""
    store = get_session_store(filesystem)
    with store.lock():
        sessions_list = store.load_sessions()
        original_count = len(sessions_list)

        if branch:
            sessions_list = [
                record
                for record in sessions_list
                if not (record.workspace == workspace and record.branch == branch)
            ]
        else:
            sessions_list = [record for record in sessions_list if record.workspace != workspace]

        store.save_sessions(sessions_list)
        return len(sessions_list) < original_count


def prune_orphaned_sessions(filesystem: Filesystem | None = None) -> int:
    """Remove sessions whose workspaces no longer exist."""
    service = get_session_service(filesystem)
    return service.prune_orphaned_sessions()


# ═══════════════════════════════════════════════════════════════════════════════
# Claude Code Integration
# ═══════════════════════════════════════════════════════════════════════════════


def get_claude_sessions_dir() -> Path:
    """Return the Claude Code sessions directory."""
    return Path.home() / AGENT_CONFIG_DIR


def get_claude_recent_sessions() -> list[dict[Any, Any]]:
    """Return recent sessions from Claude Code's own storage."""
    claude_dir = get_claude_sessions_dir()
    sessions_file = claude_dir / "sessions.json"

    if sessions_file.exists():
        try:
            with open(sessions_file) as f:
                data = json.load(f)
            return cast(list[dict[Any, Any]], data.get("sessions", []))
        except (OSError, json.JSONDecodeError):
            pass

    return []


# ═══════════════════════════════════════════════════════════════════════════════
# Formatting Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def format_relative_time(dt: datetime) -> str:
    """Format a datetime as a relative time string (e.g., '2h ago')."""
    return format_relative_time_from_datetime(dt)
