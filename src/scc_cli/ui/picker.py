"""Interactive picker functions for selection workflows.

This module provides high-level picker functions that compose ListScreen
with domain formatters to create complete selection experiences. Each picker
handles:
- Loading data from domain sources
- Converting to display items via formatters
- Running the interactive selection loop
- Returning the selected domain object(s)

Supports both single-selection and multi-selection modes:
- Single: pick_team(), pick_container(), pick_session(), pick_worktree(), pick_context()
- Multi: pick_containers()

Example:
    >>> from scc_cli.ui.picker import pick_team, pick_containers
    >>>
    >>> # Single-select: Show team picker
    >>> team = pick_team(available_teams, current_team="platform")
    >>> if team is not None:
    ...     print(f"Selected: {team['name']}")
    >>>
    >>> # Multi-select: Show container picker for stopping
    >>> containers = pick_containers(running_containers)
    >>> if containers:
    ...     for c in containers:
    ...         stop_container(c)

The pickers respect the interactivity gate and should only be called
after verifying is_interactive_allowed() returns True.

Global hotkeys:
- 't': Raises TeamSwitchRequested to allow callers to redirect to team selection
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum
from typing import TYPE_CHECKING, Any, TypeVar

from rich.live import Live
from rich.text import Text

from ..contexts import normalize_path
from ..theme import Indicators
from .chrome import Chrome, ChromeConfig
from .formatters import (
    format_container,
    format_context,
    format_session,
    format_team,
    format_worktree,
)
from .keys import BACK, ActionType, KeyReader, TeamSwitchRequested
from .list_screen import ListItem, ListMode, ListScreen, ListState

# Re-export for backwards compatibility
__all__ = ["QuickResumeResult", "TeamSwitchRequested"]

if TYPE_CHECKING:
    from rich.console import RenderableType

    from ..contexts import WorkContext

# Type variable for generic picker return types
T = TypeVar("T")


class QuickResumeResult(Enum):
    """Result of the Quick Resume picker interaction.

    This enum distinguishes between four distinct user intents:
    - SELECTED: User pressed Enter to resume the highlighted context
    - NEW_SESSION: User pressed 'n' to explicitly start a new session
    - BACK: User pressed Esc to go back to the previous screen
    - CANCELLED: User pressed 'q' to quit the application entirely
    """

    SELECTED = "selected"
    NEW_SESSION = "new_session"
    BACK = "back"
    CANCELLED = "cancelled"


def pick_team(
    teams: Sequence[dict[str, Any]],
    *,
    current_team: str | None = None,
    title: str = "Select Team",
    subtitle: str | None = None,
) -> dict[str, Any] | None:
    """Show interactive team picker.

    Display a list of teams with the current team marked. User can navigate
    with arrow keys, filter by typing, and select with Enter. Escape or 'q'
    cancels the selection.

    Args:
        teams: Sequence of team dicts with 'name' and optional 'description'.
        current_team: Name of currently selected team (marked with checkmark).
        title: Title shown in chrome header.
        subtitle: Optional subtitle for additional context.

    Returns:
        Selected team dict, or None if cancelled.

    Example:
        >>> teams = [
        ...     {"name": "platform", "description": "Platform team"},
        ...     {"name": "backend", "description": "Backend team"},
        ... ]
        >>> result = pick_team(teams, current_team="platform")
        >>> if result:
        ...     print(f"Switching to: {result['name']}")
    """
    if not teams:
        return None

    # Convert teams to list items using formatter
    items: list[ListItem[dict[str, Any]]] = [
        format_team(team, current_team=current_team) for team in teams
    ]

    return _run_single_select_picker(
        items=items,
        title=title,
        subtitle=subtitle or f"{len(teams)} teams available",
    )


def pick_container(
    containers: Sequence[Any],
    *,
    title: str = "Select Container",
    subtitle: str | None = None,
) -> Any | None:
    """Show interactive container picker (single-select).

    Display a list of containers with status and workspace info. User can
    navigate with arrow keys, filter by typing, and select with Enter.

    Args:
        containers: Sequence of ContainerInfo objects.
        title: Title shown in chrome header.
        subtitle: Optional subtitle for additional context.

    Returns:
        Selected ContainerInfo, or None if cancelled.
    """
    if not containers:
        return None

    # Convert containers to list items using formatter
    items = [format_container(container) for container in containers]

    return _run_single_select_picker(
        items=items,
        title=title,
        subtitle=subtitle or f"{len(containers)} containers",
    )


def pick_containers(
    containers: Sequence[Any],
    *,
    title: str = "Select Containers",
    subtitle: str | None = None,
    require_selection: bool = False,
) -> list[Any]:
    """Show interactive container picker (multi-select).

    Display a list of containers with checkboxes. User can:
    - Navigate with arrow keys (↑↓ or j/k)
    - Toggle selection with Space
    - Toggle all with 'a'
    - Filter by typing
    - Confirm selection with Enter

    Args:
        containers: Sequence of ContainerInfo objects.
        title: Title shown in chrome header.
        subtitle: Optional subtitle for additional context.
        require_selection: If True, return empty list only if no containers.
            If False, empty selection on Enter returns empty list.

    Returns:
        List of selected ContainerInfo objects (may be empty if cancelled).

    Example:
        >>> running = get_running_containers()
        >>> to_stop = pick_containers(running, title="Stop Containers")
        >>> for container in to_stop:
        ...     docker.stop(container.id)
    """
    if not containers:
        return []

    # Convert containers to list items using formatter
    items = [format_container(container) for container in containers]

    # Use ListScreen in MULTI_SELECT mode
    screen = ListScreen(
        items,
        title=title,
        mode=ListMode.MULTI_SELECT,
    )

    result = screen.run()

    # Handle cancellation (None) vs empty selection ([])
    if result is None:
        return []

    # In MULTI_SELECT mode, result is list[ContainerInfo]
    # Type narrowing: if not None, it's a list in multi-select mode
    if isinstance(result, list):
        return result
    return []


def pick_session(
    sessions: Sequence[dict[str, Any]],
    *,
    title: str = "Select Session",
    subtitle: str | None = None,
) -> dict[str, Any] | None:
    """Show interactive session picker.

    Display a list of sessions with team, branch, and last used info.
    User can navigate with arrow keys, filter by typing, and select with Enter.

    Args:
        sessions: Sequence of session dicts.
        title: Title shown in chrome header.
        subtitle: Optional subtitle for additional context.

    Returns:
        Selected session dict, or None if cancelled.
    """
    if not sessions:
        return None

    # Convert sessions to list items using formatter
    items = [format_session(session) for session in sessions]

    return _run_single_select_picker(
        items=items,
        title=title,
        subtitle=subtitle or f"{len(sessions)} sessions",
    )


def pick_worktree(
    worktrees: Sequence[Any],
    *,
    title: str = "Select Worktree",
    subtitle: str | None = None,
) -> Any | None:
    """Show interactive worktree picker.

    Display a list of git worktrees with branch and status info.
    User can navigate with arrow keys, filter by typing, and select with Enter.

    Args:
        worktrees: Sequence of WorktreeInfo objects.
        title: Title shown in chrome header.
        subtitle: Optional subtitle for additional context.

    Returns:
        Selected WorktreeInfo, or None if cancelled.
    """
    if not worktrees:
        return None

    # Convert worktrees to list items using formatter
    items = [format_worktree(worktree) for worktree in worktrees]

    return _run_single_select_picker(
        items=items,
        title=title,
        subtitle=subtitle or f"{len(worktrees)} worktrees",
    )


def pick_context(
    contexts: Sequence[WorkContext],
    *,
    title: str = "Recent Contexts",
    subtitle: str | None = None,
) -> WorkContext | None:
    """Show interactive context picker for quick resume.

    Display a list of recent work contexts (team + repo + worktree) with
    pinned items first, then sorted by recency. User can filter by typing,
    navigate with arrow keys, and select with Enter.

    This is the primary entry point for the "context-first" UX pattern,
    allowing developers to quickly resume where they left off.

    Args:
        contexts: Sequence of WorkContext objects (typically from load_recent_contexts).
        title: Title shown in chrome header.
        subtitle: Optional subtitle for additional context.

    Returns:
        Selected WorkContext, or None if cancelled.

    Example:
        >>> from scc_cli.contexts import load_recent_contexts
        >>> from scc_cli.ui.picker import pick_context
        >>>
        >>> contexts = load_recent_contexts(limit=10)
        >>> selected = pick_context(contexts)
        >>> if selected:
        ...     # Resume work in the selected context
        ...     start_session(selected.team, selected.worktree_path)
    """
    if not contexts:
        return None

    # Convert contexts to list items using formatter
    items = [format_context(context) for context in contexts]

    return _run_single_select_picker(
        items=items,
        title=title,
        subtitle=subtitle or f"{len(contexts)} recent contexts",
    )


def pick_context_quick_resume(
    contexts: Sequence[WorkContext],
    *,
    title: str = "Recent Contexts",
    subtitle: str | None = None,
    standalone: bool = False,
    current_branch: str | None = None,
    context_label: str | None = None,
) -> tuple[QuickResumeResult, WorkContext | None]:
    """Show Quick Resume picker with 4-way result semantics.

    This picker distinguishes between four user intents:
    - Enter: Resume the selected context (SELECTED)
    - n: Explicitly start a new session (NEW_SESSION)
    - Esc: Go back to previous screen (BACK)
    - q: Cancel the entire wizard (CANCELLED)

    Args:
        contexts: Sequence of WorkContext objects.
        title: Title shown in chrome header.
        subtitle: Optional subtitle (defaults to showing Esc hint).
        standalone: If True, dim the "t teams" hint (not available without org).
        current_branch: Current git branch from CWD, used to highlight
            contexts matching this branch with a ★ indicator.
        context_label: Optional context label (e.g., "Team: platform") shown in header.

    Returns:
        Tuple of (QuickResumeResult, selected WorkContext or None).

    Example:
        >>> from scc_cli.contexts import load_recent_contexts
        >>> from scc_cli.ui.picker import pick_context_quick_resume, QuickResumeResult
        >>>
        >>> contexts = load_recent_contexts(limit=10)
        >>> result, context = pick_context_quick_resume(contexts, standalone=True)
        >>> match result:
        ...     case QuickResumeResult.SELECTED:
        ...         resume_session(context)
        ...     case QuickResumeResult.NEW_SESSION:
        ...         start_new_session()
        ...     case QuickResumeResult.BACK:
        ...         continue  # Go back to previous screen
        ...     case QuickResumeResult.CANCELLED:
        ...         return  # Exit wizard
    """
    if not contexts:
        return (QuickResumeResult.NEW_SESSION, None)

    # Query running containers for status indicators
    running_workspaces = _get_running_workspaces()

    # Convert contexts to list items with status and branch indicators
    items = [
        format_context(
            context,
            is_running=str(context.worktree_path) in running_workspaces,
            is_current_branch=(
                current_branch is not None and context.worktree_name == current_branch
            ),
        )
        for context in contexts
    ]

    return _run_quick_resume_picker(
        items=items,
        title=title,
        subtitle=subtitle,
        standalone=standalone,
        context_label=context_label,
    )


def _get_running_workspaces() -> set[str]:
    """Get set of workspace paths with running containers.

    Paths are normalized (resolved symlinks, expanded ~) via normalize_path()
    to ensure consistent comparison with context.worktree_path.

    Returns an empty set if Docker is not available or on error.
    This allows the picker to work without Docker status indicators.
    """
    try:
        from ..docker import list_scc_containers

        containers = list_scc_containers()
        # Normalize paths using the same function as WorkContext for consistency
        return {
            str(normalize_path(c.workspace))
            for c in containers
            if c.workspace and c.status.startswith("Up")
        }
    except Exception:
        # Docker not available or error - return empty set
        return set()


def _run_single_select_picker(
    items: list[ListItem[T]],
    *,
    title: str,
    subtitle: str | None = None,
    standalone: bool = False,
    allow_back: bool = False,
    context_label: str | None = None,
) -> T | None:
    """Run the interactive single-selection picker loop.

    This is the core picker implementation that handles:
    - Rendering the list with chrome
    - Processing keyboard input
    - Managing navigation and filtering state
    - Returning selection on Enter, BACK on Esc (if allow_back), or None on quit

    Args:
        items: List items to display.
        title: Title for chrome header.
        subtitle: Optional subtitle.
        standalone: If True, dim the "t teams" hint (not available without org).
        allow_back: If True, Esc returns BACK sentinel (for sub-screens).
            If False, Esc returns None (for top-level screens).
        context_label: Optional context label (e.g., "Team: platform") shown in header.

    Returns:
        Value from selected item, BACK if allow_back and Esc pressed, or None if quit.
    """
    if not items:
        return None

    from ..console import get_err_console

    console = get_err_console()
    state = ListState(items=items)
    reader = KeyReader(enable_filter=True)

    def render() -> RenderableType:
        """Render current picker state."""
        # Build list body
        body = Text()
        visible = state.visible_items

        if not state.filtered_items:
            body.append("No matches", style="dim italic")
            return _wrap_in_chrome(body, title, subtitle, state.filter_query)

        for i, item in enumerate(visible):
            actual_index = state.scroll_offset + i
            is_cursor = actual_index == state.cursor

            # Cursor indicator
            if is_cursor:
                body.append(f"{Indicators.get('CURSOR')} ", style="cyan bold")
            else:
                body.append("  ")

            # Label with governance styling
            label_style = "bold" if is_cursor else ""
            if item.governance_status == "blocked":
                label_style += " red"
            elif item.governance_status == "warning":
                label_style += " yellow"

            body.append(item.label, style=label_style.strip())

            # Description
            if item.description:
                body.append(f"  {item.description}", style="dim")

            body.append("\n")

        return _wrap_in_chrome(body, title, subtitle, state.filter_query)

    def _wrap_in_chrome(
        body: Text, title: str, subtitle: str | None, filter_query: str
    ) -> RenderableType:
        """Wrap body content in chrome."""
        # Capture `standalone` from outer scope for proper footer hint dimming
        config = ChromeConfig.for_picker(title, subtitle, standalone=standalone)
        if context_label:
            config = config.with_context(context_label)
        chrome = Chrome(config)
        return chrome.render(body, search_query=filter_query)

    # Run the picker loop
    with Live(
        render(),
        console=console,
        auto_refresh=False,  # Manual refresh for instant response
        transient=True,
    ) as live:
        while True:
            action = reader.read(filter_active=bool(state.filter_query))

            match action.action_type:
                case ActionType.NAVIGATE_UP:
                    state.move_cursor(-1)

                case ActionType.NAVIGATE_DOWN:
                    state.move_cursor(1)

                case ActionType.SELECT:
                    # Return selected value
                    current = state.current_item
                    if current is not None:
                        return current.value
                    return None

                case ActionType.CANCEL:
                    # Esc: back to previous screen (if allowed) or cancel
                    if allow_back:
                        return BACK  # type: ignore[return-value]
                    return None

                case ActionType.QUIT:
                    # q: always quit entirely
                    return None

                case ActionType.TEAM_SWITCH:
                    # Signal caller to redirect to team selection
                    raise TeamSwitchRequested()

                case ActionType.FILTER_CHAR:
                    if action.filter_char:
                        state.add_filter_char(action.filter_char)

                case ActionType.FILTER_DELETE:
                    state.delete_filter_char()

                case ActionType.NOOP:
                    pass  # Unrecognized key - no action needed

            if action.state_changed:
                live.update(render(), refresh=True)


def _run_quick_resume_picker(
    items: list[ListItem[T]],
    *,
    title: str,
    subtitle: str | None = None,
    standalone: bool = False,
    context_label: str | None = None,
) -> tuple[QuickResumeResult, T | None]:
    """Run the Quick Resume picker with 4-way result semantics.

    Unlike the standard single-select picker, this distinguishes between:
    - Enter: Resume the selected context (SELECTED)
    - n: Explicitly start a new session (NEW_SESSION)
    - Esc: Go back to previous screen (BACK)
    - q: Cancel the entire wizard (CANCELLED)

    Args:
        items: List items to display (recent contexts).
        title: Title for chrome header.
        subtitle: Optional subtitle.
        standalone: If True, dim the "t teams" hint (not available without org).
        context_label: Optional context label (e.g., "Team: platform") shown in header.

    Returns:
        Tuple of (QuickResumeResult, selected_value or None).
    """
    if not items:
        return (QuickResumeResult.NEW_SESSION, None)

    from ..console import get_err_console

    console = get_err_console()
    state = ListState(items=items)
    # 'n' (new session) is screen-specific, not global, to avoid key conflicts
    reader = KeyReader(custom_keys={"n": "new_session"}, enable_filter=True)

    def render() -> RenderableType:
        """Render current picker state."""
        body = Text()
        visible = state.visible_items

        if not state.filtered_items:
            body.append("No matches", style="dim italic")
            return _wrap_quick_resume_chrome(body, title, subtitle, state.filter_query)

        for i, item in enumerate(visible):
            actual_index = state.scroll_offset + i
            is_cursor = actual_index == state.cursor

            # Cursor indicator
            if is_cursor:
                body.append(f"{Indicators.get('CURSOR')} ", style="cyan bold")
            else:
                body.append("  ")

            # Label with governance styling
            label_style = "bold" if is_cursor else ""
            if item.governance_status == "blocked":
                label_style += " red"
            elif item.governance_status == "warning":
                label_style += " yellow"

            body.append(item.label, style=label_style.strip())

            # Description
            if item.description:
                body.append(f"  {item.description}", style="dim")

            body.append("\n")

        return _wrap_quick_resume_chrome(body, title, subtitle, state.filter_query)

    def _wrap_quick_resume_chrome(
        body: Text, title: str, subtitle: str | None, filter_query: str
    ) -> RenderableType:
        """Wrap body content in Quick Resume chrome with truthful hints."""
        config = ChromeConfig.for_quick_resume(title, subtitle, standalone=standalone)
        if context_label:
            config = config.with_context(context_label)
        chrome = Chrome(config)
        return chrome.render(body, search_query=filter_query)

    # Run the picker loop with 3-way key handling
    with Live(
        render(),
        console=console,
        auto_refresh=False,
        transient=True,
    ) as live:
        while True:
            action = reader.read(filter_active=bool(state.filter_query))

            match action.action_type:
                case ActionType.NAVIGATE_UP:
                    state.move_cursor(-1)

                case ActionType.NAVIGATE_DOWN:
                    state.move_cursor(1)

                case ActionType.SELECT:
                    # Enter = resume selected context
                    current = state.current_item
                    if current is not None:
                        return (QuickResumeResult.SELECTED, current.value)
                    return (QuickResumeResult.NEW_SESSION, None)

                case ActionType.CUSTOM:
                    # Handle screen-specific custom keys (e.g., 'n' for new session)
                    if action.custom_key == "n":
                        # n = explicitly start new session (skip resume)
                        return (QuickResumeResult.NEW_SESSION, None)

                case ActionType.CANCEL:
                    # Esc = go back to previous screen
                    return (QuickResumeResult.BACK, None)

                case ActionType.QUIT:
                    # q = quit app entirely
                    return (QuickResumeResult.CANCELLED, None)

                case ActionType.TEAM_SWITCH:
                    raise TeamSwitchRequested()

                case ActionType.FILTER_CHAR:
                    if action.filter_char:
                        state.add_filter_char(action.filter_char)

                case ActionType.FILTER_DELETE:
                    state.delete_filter_char()

                case ActionType.NOOP:
                    pass  # Unrecognized key - no action needed

            if action.state_changed:
                live.update(render(), refresh=True)
