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
from typing import TYPE_CHECKING, Any

from ..docker.core import ContainerInfo
from ..git import WorktreeInfo
from .list_screen import ListItem

if TYPE_CHECKING:
    from ..contexts import WorkContext


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
    label = f"✓ {name}" if is_current else name

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
    label = f"✓ {dir_name}" if worktree.is_current else dir_name

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


def format_context(context: WorkContext) -> ListItem[WorkContext]:
    """Format a work context for display in a picker.

    Shows the context's display_label (team · repo · worktree) with
    pinned indicator and relative time since last used.

    Args:
        context: Work context to format.

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
    """
    # Build label with pinned indicator
    label = f"📌 {context.display_label}" if context.pinned else context.display_label

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
            "team": context.team,
            "repo": context.repo_name,
            "worktree": context.worktree_name,
            "path": str(context.worktree_path),
            "pinned": "yes" if context.pinned else "no",
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
