"""Display formatting helpers for domain types.

This module provides pure functions to convert domain objects into display
representations suitable for the interactive UI. Each formatter transforms
a domain type into a ListItem for use in pickers and lists.

Example:
    >>> from scc_cli.docker.core import ContainerInfo
    >>> from scc_cli.ui.formatters import format_container
    >>>
    >>> container = ContainerInfo(id="abc123", name="scc-main", status="Up 2 hours")
    >>> item = format_container(container)
    >>> print(item.label)  # scc-main
    >>> print(item.description)  # Up 2 hours

The formatters follow a consistent pattern:
- Input: Domain type (dataclass or dict)
- Output: ListItem with label, description, metadata, and optional governance status
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, TypedDict

from ..docker.core import ContainerInfo
from ..git import WorktreeInfo
from ..theme import Indicators
from .list_screen import ListItem

if TYPE_CHECKING:
    from ..contexts import WorkContext


# ═══════════════════════════════════════════════════════════════════════════════
# TypedDict Metadata Definitions (enables mypy type checking and IDE autocomplete)
# ═══════════════════════════════════════════════════════════════════════════════


class ContainerMetadata(TypedDict):
    """Metadata for container list items.

    Keys:
        running: "yes" or "no" indicating container state.
        id: Short (12-char) container ID for display.
    """

    running: str
    id: str


class WorktreeMetadata(TypedDict):
    """Metadata for worktree list items.

    Keys:
        path: Full filesystem path to the worktree.
        current: "yes" or "no" indicating if this is the current worktree.
    """

    path: str
    current: str


class ContextMetadata(TypedDict):
    """Metadata for work context list items.

    Keys:
        team: Team/profile name.
        repo: Repository name.
        worktree: Worktree directory name.
        path: Full filesystem path.
        pinned: "yes" or "no".
        running: "yes", "no", or "" (unknown).
        current_branch: "yes", "no", or "" (unknown).
    """

    team: str
    repo: str
    worktree: str
    path: str
    pinned: str
    running: str
    current_branch: str


def format_team(
    team: dict[str, Any], *, current_team: str | None = None
) -> ListItem[dict[str, Any]]:
    """Format a team dict for display in a picker.

    Args:
        team: Team dictionary with name and optional metadata.
        current_team: Currently selected team name (marked with indicator).

    Returns:
        ListItem suitable for ListScreen display.

    Example:
        >>> team = {"name": "platform", "description": "Platform team"}
        >>> item = format_team(team, current_team="platform")
        >>> item.label
        '✓ platform'
    """
    name = team.get("name", "unknown")
    description = team.get("description", "")
    is_current = current_team is not None and name == current_team

    # Build label with current indicator
    label = f"{Indicators.get('PASS')} {name}" if is_current else name

    # Check for credential/governance status
    governance_status: str | None = None
    credential_status = team.get("credential_status")
    if credential_status == "expired":
        governance_status = "blocked"
    elif credential_status == "expiring":
        governance_status = "warning"

    # Build description parts
    desc_parts: list[str] = []
    if description:
        desc_parts.append(description)
    if credential_status == "expired":
        desc_parts.append("(credentials expired)")
    elif credential_status == "expiring":
        desc_parts.append("(credentials expiring)")

    return ListItem(
        value=team,
        label=label,
        description="  ".join(desc_parts),
        governance_status=governance_status,
    )


def format_container(container: ContainerInfo) -> ListItem[ContainerInfo]:
    """Format a container for display in a picker or list.

    Args:
        container: Container information from Docker.

    Returns:
        ListItem suitable for ListScreen display.

    Example:
        >>> container = ContainerInfo(
        ...     id="abc123",
        ...     name="scc-main",
        ...     status="Up 2 hours",
        ...     profile="team-a",
        ...     workspace="/home/user/project",
        ... )
        >>> item = format_container(container)
        >>> item.label
        'scc-main'
    """
    # Build description parts
    desc_parts: list[str] = []

    if container.profile:
        desc_parts.append(container.profile)

    if container.workspace:
        # Show just the workspace name (last path component)
        workspace_name = container.workspace.split("/")[-1]
        desc_parts.append(workspace_name)

    if container.status:
        # Simplify status (e.g., "Up 2 hours" -> "Up 2h")
        status_short = _shorten_docker_status(container.status)
        desc_parts.append(status_short)

    # Determine if container is running
    is_running = container.status.startswith("Up") if container.status else False

    return ListItem(
        value=container,
        label=container.name,
        description="  ".join(desc_parts),
        metadata={
            "running": "yes" if is_running else "no",
            "id": container.id[:12],  # Short container ID
        },
    )


def format_session(session: dict[str, Any]) -> ListItem[dict[str, Any]]:
    """Format a session dict for display in a picker.

    Args:
        session: Session dictionary with name, team, branch, etc.

    Returns:
        ListItem suitable for ListScreen display.

    Example:
        >>> session = {
        ...     "name": "project-feature",
        ...     "team": "platform",
        ...     "branch": "feature/auth",
        ...     "last_used": "2 hours ago",
        ... }
        >>> item = format_session(session)
        >>> item.label
        'project-feature'
    """
    name = session.get("name", "Unnamed")

    # Build description parts
    desc_parts: list[str] = []

    if session.get("team"):
        desc_parts.append(str(session["team"]))

    if session.get("branch"):
        desc_parts.append(str(session["branch"]))

    if session.get("last_used"):
        desc_parts.append(str(session["last_used"]))

    # Check for governance warnings (e.g., expiring exceptions)
    governance_status: str | None = None
    if session.get("has_exception_warning"):
        governance_status = "warning"

    return ListItem(
        value=session,
        label=name,
        description="  ".join(desc_parts),
        governance_status=governance_status,
    )


def format_worktree(worktree: WorktreeInfo) -> ListItem[WorktreeInfo]:
    """Format a worktree for display in a picker or list.

    Args:
        worktree: Worktree information from Git.

    Returns:
        ListItem suitable for ListScreen display.

    Example:
        >>> from scc_cli.git import WorktreeInfo
        >>> wt = WorktreeInfo(
        ...     path="/home/user/project-feature",
        ...     branch="feature/auth",
        ...     is_current=True,
        ...     has_changes=True,
        ... )
        >>> item = format_worktree(wt)
        >>> item.label
        '✓ project-feature'
    """
    from pathlib import Path

    # Use just the directory name for the label
    dir_name = Path(worktree.path).name

    # Build label with current indicator
    label = f"{Indicators.get('PASS')} {dir_name}" if worktree.is_current else dir_name

    # Build description parts
    desc_parts: list[str] = []

    if worktree.branch:
        desc_parts.append(worktree.branch)

    if worktree.has_changes:
        desc_parts.append("*modified")

    if worktree.is_current:
        desc_parts.append("(current)")

    return ListItem(
        value=worktree,
        label=label,
        description="  ".join(desc_parts),
        metadata={
            "path": worktree.path,
            "current": "yes" if worktree.is_current else "no",
        },
    )


def format_context(
    context: WorkContext,
    *,
    is_running: bool | None = None,
    is_current_branch: bool | None = None,
) -> ListItem[WorkContext]:
    """Format a work context for display in a picker.

    Shows the context's display_label (team · repo · worktree) with
    pinned indicator, status indicator, current branch indicator, and
    relative time since last used.

    Args:
        context: Work context to format.
        is_running: Whether the context's container is running.
            True = show 🟢 (running), False = show ⚫ (stopped), None = no indicator.
        is_current_branch: Whether this context matches the current git branch.
            True = show ★ indicator, False/None = no indicator.

    Returns:
        ListItem suitable for ListScreen display.

    Example:
        >>> from scc_cli.contexts import WorkContext
        >>> from pathlib import Path
        >>> ctx = WorkContext(
        ...     team="platform",
        ...     repo_root=Path("/code/api"),
        ...     worktree_path=Path("/code/api"),
        ...     worktree_name="main",
        ...     pinned=True,
        ... )
        >>> item = format_context(ctx)
        >>> item.label
        '📌 platform · api · main'
        >>> item = format_context(ctx, is_running=True)
        >>> '🟢' in item.label
        True
        >>> item = format_context(ctx, is_current_branch=True)
        >>> '★' in item.label
        True
    """
    # Build label parts
    parts: list[str] = []

    # Add pinned indicator
    if context.pinned:
        parts.append("📌")

    # Add current branch indicator (matches CWD branch)
    if is_current_branch is True:
        parts.append("★")

    # Add status indicator (running/stopped)
    if is_running is True:
        parts.append("🟢")
    elif is_running is False:
        parts.append("⚫")

    # Add display label
    parts.append(context.display_label)

    label = " ".join(parts)

    # Build description parts
    desc_parts: list[str] = []

    # Add relative time since last used
    relative_time = _format_relative_time(context.last_used)
    if relative_time:
        desc_parts.append(relative_time)

    # Add session info if available
    if context.last_session_id:
        desc_parts.append(f"session: {context.last_session_id}")

    return ListItem(
        value=context,
        label=label,
        description="  ".join(desc_parts),
        metadata={
            "team": context.team or "",  # Empty string for standalone mode (no team)
            "repo": context.repo_name,
            "worktree": context.worktree_name,
            "path": str(context.worktree_path),
            "pinned": "yes" if context.pinned else "no",
            "running": "yes" if is_running else "no" if is_running is False else "",
            "current_branch": (
                "yes" if is_current_branch else "no" if is_current_branch is False else ""
            ),
        },
    )


def _format_relative_time(iso_timestamp: str) -> str:
    """Format an ISO timestamp as relative time (e.g., '2 hours ago').

    Args:
        iso_timestamp: ISO 8601 timestamp string.

    Returns:
        Human-readable relative time string, or empty if parsing fails.
    """
    try:
        # Parse ISO format, handling Z suffix
        timestamp = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - timestamp

        seconds = int(delta.total_seconds())
        if seconds < 0:
            return ""
        if seconds < 60:
            return "just now"
        if seconds < 3600:
            minutes = seconds // 60
            return f"{minutes}m ago"
        if seconds < 86400:
            hours = seconds // 3600
            return f"{hours}h ago"
        if seconds < 604800:
            days = seconds // 86400
            return f"{days}d ago"
        weeks = seconds // 604800
        return f"{weeks}w ago"
    except (ValueError, TypeError):
        return ""


def _shorten_docker_status(status: str) -> str:
    """Shorten Docker status strings for compact display.

    Converts verbose time units to abbreviations:
    - "Up 2 hours" -> "Up 2h"
    - "Exited (0) 5 minutes ago" -> "Exited 5m ago"

    Args:
        status: Full Docker status string.

    Returns:
        Shortened status string.
    """
    result = status
    replacements = [
        (" hours", "h"),
        (" hour", "h"),
        (" minutes", "m"),
        (" minute", "m"),
        (" seconds", "s"),
        (" second", "s"),
        (" days", "d"),
        (" day", "d"),
        (" weeks", "w"),
        (" week", "w"),
    ]
    for old, new in replacements:
        result = result.replace(old, new)
    return result
