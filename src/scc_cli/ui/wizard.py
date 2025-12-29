"""Wizard-specific pickers with three-state navigation support.

This module provides picker functions for the interactive start wizard,
with proper navigation support for nested screens. All pickers follow
a three-state return contract:

- Success: Returns the selected value (WorkspaceSource, str path, etc.)
- Back: Returns BACK sentinel (Esc pressed - go to previous screen)
- Quit: Returns None (q pressed - exit app entirely)

The BACK sentinel provides type-safe back navigation that callers can
check with identity comparison: `if result is BACK`.

Top-level vs Sub-screen behavior:
- Top-level (pick_workspace_source with allow_back=False): Esc returns None
- Sub-screens (pick_recent_workspace, pick_team_repo): Esc returns BACK, q returns None

Example:
    >>> from scc_cli.ui.wizard import (
    ...     BACK, WorkspaceSource,
    ...     pick_workspace_source, pick_recent_workspace
    ... )
    >>>
    >>> while True:
    ...     source = pick_workspace_source(team="platform")
    ...     if source is None:
    ...         break  # User pressed q or Esc at top level - quit
    ...
    ...     if source == WorkspaceSource.RECENT:
    ...         workspace = pick_recent_workspace(recent_sessions)
    ...         if workspace is None:
    ...             break  # User pressed q - quit app
    ...         if workspace is BACK:
    ...             continue  # User pressed Esc - go back to source picker
    ...         return workspace  # Got a valid path
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from .keys import BACK, _BackSentinel
from .list_screen import ListItem
from .picker import _run_single_select_picker

if TYPE_CHECKING:
    pass

# Type variable for generic picker return types
T = TypeVar("T")


# ═══════════════════════════════════════════════════════════════════════════════
# Workspace Source Enum
# ═══════════════════════════════════════════════════════════════════════════════


class WorkspaceSource(Enum):
    """Options for where to get the workspace from."""

    CURRENT_DIR = "current_dir"  # Use current working directory
    RECENT = "recent"
    TEAM_REPOS = "team_repos"
    CUSTOM = "custom"
    CLONE = "clone"


# ═══════════════════════════════════════════════════════════════════════════════
# Local Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _normalize_path(path: str) -> str:
    """Collapse HOME to ~ and truncate keeping last 2 segments.

    Uses Path.parts for cross-platform robustness.

    Examples:
        /Users/dev/projects/api → ~/projects/api
        /Users/dev/very/long/path/to/project → ~/…/to/project
        /opt/data/files → /opt/data/files (no home prefix)
    """
    p = Path(path)
    home = Path.home()

    # Try to make path relative to home
    try:
        relative = p.relative_to(home)
        display = "~/" + str(relative)
        starts_with_home = True
    except ValueError:
        display = str(p)
        starts_with_home = False

    # Truncate if too long, keeping last 2 segments for context
    if len(display) > 50:
        parts = p.parts
        if len(parts) >= 2:
            tail = "/".join(parts[-2:])
        elif parts:
            tail = parts[-1]
        else:
            tail = ""

        prefix = "~" if starts_with_home else ""
        display = f"{prefix}/…/{tail}"

    return display


def _format_relative_time(iso_timestamp: str) -> str:
    """Format an ISO timestamp as relative time.

    Examples:
        2 minutes ago → "2m ago"
        3 hours ago → "3h ago"
        yesterday → "yesterday"
        5 days ago → "5d ago"
        older → "Dec 20" (month day format)
    """
    try:
        # Handle Z suffix for UTC
        if iso_timestamp.endswith("Z"):
            iso_timestamp = iso_timestamp[:-1] + "+00:00"

        timestamp = datetime.fromisoformat(iso_timestamp)

        # Ensure timezone-aware comparison
        now = datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        delta = now - timestamp
        seconds = delta.total_seconds()

        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes}m ago"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours}h ago"
        elif seconds < 172800:  # 2 days
            return "yesterday"
        elif seconds < 604800:  # 7 days
            days = int(seconds / 86400)
            return f"{days}d ago"
        else:
            # Older than a week - show month day
            return timestamp.strftime("%b %d")

    except (ValueError, AttributeError):
        return ""


# ═══════════════════════════════════════════════════════════════════════════════
# Sub-screen Picker Wrapper
# ═══════════════════════════════════════════════════════════════════════════════


def _run_subscreen_picker(
    items: list[ListItem[T]],
    title: str,
    subtitle: str | None = None,
    *,
    standalone: bool = False,
    context_label: str | None = None,
) -> T | _BackSentinel | None:
    """Run picker for sub-screens with three-state return contract.

    Sub-screen pickers distinguish between:
    - Esc (go back to previous screen) → BACK sentinel
    - q (quit app entirely) → None

    Args:
        items: List items to display (first item should be "← Back").
        title: Title for chrome header.
        subtitle: Optional subtitle.
        standalone: If True, dim the "t teams" hint (not available without org).

    Returns:
        Selected item value, BACK if Esc pressed, or None if q pressed (quit).
    """
    # Pass allow_back=True so picker distinguishes Esc (BACK) from q (None)
    result = _run_single_select_picker(
        items,
        title=title,
        subtitle=subtitle,
        standalone=standalone,
        allow_back=True,
        context_label=context_label,
    )
    # Three-state contract:
    # - T value: user selected an item
    # - BACK: user pressed Esc (go back)
    # - None: user pressed q (quit app)
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Top-Level Picker: Workspace Source
# ═══════════════════════════════════════════════════════════════════════════════


def _is_valid_workspace(path: Path) -> bool:
    """Check if a directory looks like a valid workspace.

    A valid workspace must have at least one of:
    - .git directory or file (for worktrees)
    - .scc.yaml config file

    Random directories (like $HOME) are NOT valid workspaces.

    Args:
        path: Directory to check.

    Returns:
        True if directory exists and has workspace markers.
    """
    if not path.is_dir():
        return False

    # Check for git (directory or file for worktrees)
    git_path = path / ".git"
    if git_path.exists():
        return True

    # Check for SCC config
    if (path / ".scc.yaml").exists():
        return True

    # No workspace markers found - not a valid workspace
    return False


def pick_workspace_source(
    has_team_repos: bool = False,
    team: str | None = None,
    *,
    standalone: bool = False,
    allow_back: bool = False,
    context_label: str | None = None,
) -> WorkspaceSource | _BackSentinel | None:
    """Show picker for workspace source selection.

    Three-state return contract:
    - Success: Returns WorkspaceSource (user selected an option)
    - Back: Returns BACK sentinel (user pressed Esc, only if allow_back=True)
    - Quit: Returns None (user pressed q)

    Args:
        has_team_repos: Whether team repositories are available.
        team: Current team name (used for context label if not provided).
        standalone: If True, dim the "t teams" hint (not available without org).
        allow_back: If True, Esc returns BACK (for sub-screen context like Dashboard).
            If False, Esc returns None (for top-level CLI context).
        context_label: Optional context label (e.g., "Team: platform") shown in header.

    Returns:
        Selected WorkspaceSource, BACK if allow_back and Esc pressed, or None if quit.
    """
    # Build subtitle based on context
    subtitle = "Pick a project source"
    resolved_context_label = context_label
    if resolved_context_label is None and team:
        resolved_context_label = f"Team: {team}"

    # Build items list - start with CWD option if valid
    items: list[ListItem[WorkspaceSource]] = []

    # Check if current directory is a valid workspace
    cwd = Path.cwd()
    if _is_valid_workspace(cwd):
        # Show CWD name (last path component)
        cwd_name = cwd.name or str(cwd)
        items.append(
            ListItem(
                label="📍 Use current directory",
                description=cwd_name,
                value=WorkspaceSource.CURRENT_DIR,
            )
        )

    # Add standard options
    items.append(
        ListItem(
            label="📂 Recent workspaces",
            description="Continue working on previous project",
            value=WorkspaceSource.RECENT,
        )
    )

    if has_team_repos:
        items.append(
            ListItem(
                label="🏢 Team repositories",
                description="Choose from team's common repos",
                value=WorkspaceSource.TEAM_REPOS,
            )
        )

    items.extend(
        [
            ListItem(
                label="📁 Enter path",
                description="Specify a local directory path",
                value=WorkspaceSource.CUSTOM,
            ),
            ListItem(
                label="🔗 Clone repository",
                description="Clone a Git repository",
                value=WorkspaceSource.CLONE,
            ),
        ]
    )

    return _run_single_select_picker(
        items=items,
        title="Where is your project?",
        subtitle=subtitle,
        standalone=standalone,
        allow_back=allow_back,
        context_label=resolved_context_label,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Sub-Screen Picker: Recent Workspaces
# ═══════════════════════════════════════════════════════════════════════════════


def pick_recent_workspace(
    recent: list[dict[str, Any]],
    *,
    standalone: bool = False,
    context_label: str | None = None,
) -> str | _BackSentinel | None:
    """Show picker for recent workspace selection.

    This is a sub-screen picker with three-state return contract:
    - str: User selected a workspace path
    - BACK: User pressed Esc (go back to previous screen)
    - None: User pressed q (quit app entirely)

    Args:
        recent: List of recent session dicts with 'workspace' and 'last_used' keys.
        standalone: If True, dim the "t teams" hint (not available without org).
        context_label: Optional context label (e.g., "Team: platform") shown in header.

    Returns:
        Selected workspace path, BACK if Esc pressed, or None if q pressed (quit).
    """
    # Build items with "← Back" first
    items: list[ListItem[str | _BackSentinel]] = [
        ListItem(
            label="← Back",
            description="",
            value=BACK,
        ),
    ]

    # Add recent workspaces
    for session in recent:
        workspace = session.get("workspace", "")
        last_used = session.get("last_used", "")

        items.append(
            ListItem(
                label=_normalize_path(workspace),
                description=_format_relative_time(last_used),
                value=workspace,  # Full path as value
            )
        )

    # Empty state hint in subtitle
    if len(items) == 1:  # Only "← Back"
        subtitle = "No recent workspaces found"
    else:
        subtitle = None

    return _run_subscreen_picker(
        items=items,
        title="Recent Workspaces",
        subtitle=subtitle,
        standalone=standalone,
        context_label=context_label,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Sub-Screen Picker: Team Repositories (Phase 3)
# ═══════════════════════════════════════════════════════════════════════════════


def pick_team_repo(
    repos: list[dict[str, Any]],
    workspace_base: str = "~/projects",
    *,
    standalone: bool = False,
    context_label: str | None = None,
) -> str | _BackSentinel | None:
    """Show picker for team repository selection.

    This is a sub-screen picker with three-state return contract:
    - str: User selected a repo (returns existing local_path or newly cloned path)
    - BACK: User pressed Esc (go back to previous screen)
    - None: User pressed q (quit app entirely)

    If the selected repo has a local_path that exists, returns that path.
    Otherwise, clones the repository and returns the new path.

    Args:
        repos: List of repo dicts with 'name', 'url', optional 'description', 'local_path'.
        workspace_base: Base directory for cloning new repos.
        standalone: If True, dim the "t teams" hint (not available without org).
        context_label: Optional context label (e.g., "Team: platform") shown in header.

    Returns:
        Workspace path (existing or newly cloned), BACK if Esc pressed, or None if q pressed.
    """
    # Build items with "← Back" first
    items: list[ListItem[dict[str, Any] | _BackSentinel]] = [
        ListItem(
            label="← Back",
            description="",
            value=BACK,
        ),
    ]

    # Add team repos
    for repo in repos:
        name = repo.get("name", repo.get("url", "Unknown"))
        description = repo.get("description", "")

        items.append(
            ListItem(
                label=name,
                description=description,
                value=repo,  # Full repo dict as value
            )
        )

    # Empty state hint
    if len(items) == 1:  # Only "← Back"
        subtitle = "No team repositories configured"
    else:
        subtitle = None

    result = _run_subscreen_picker(
        items=items,
        title="Team Repositories",
        subtitle=subtitle,
        standalone=standalone,
        context_label=context_label,
    )

    # Handle quit (q pressed)
    if result is None:
        return None

    # Handle BACK (Esc pressed)
    if result is BACK:
        return BACK

    # Handle repo selection - check for existing local path or clone
    if isinstance(result, dict):
        local_path = result.get("local_path")
        if local_path:
            expanded = Path(local_path).expanduser()
            if expanded.exists():
                return str(expanded)

        # Need to clone - import git module here to avoid circular imports
        from .. import git

        repo_url = result.get("url", "")
        if repo_url:
            cloned_path = git.clone_repo(repo_url, workspace_base)
            if cloned_path:
                return cloned_path

        # Cloning failed or no URL - return BACK to let user try again
        return BACK

    # Shouldn't happen, but handle gracefully
    return BACK
