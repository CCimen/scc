"""Action handling for the Dashboard component.

Extracted from _dashboard.py to keep that module focused on rendering
and the run loop. This module contains the `handle_dashboard_action`
function that processes keyboard actions and updates dashboard state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scc_cli.application.dashboard import (
    ContainerItem,
    DashboardTab,
    PlaceholderItem,
    PlaceholderKind,
    SessionItem,
    StatusAction,
    StatusItem,
    WorktreeItem,
    placeholder_start_reason,
)

from ..keys import (
    Action,
    ActionType,
    ContainerActionMenuRequested,
    ContainerRemoveRequested,
    ContainerResumeRequested,
    ContainerStopRequested,
    CreateWorktreeRequested,
    GitInitRequested,
    ProfileMenuRequested,
    RecentWorkspacesRequested,
    RefreshRequested,
    SandboxImportRequested,
    SessionActionMenuRequested,
    SessionResumeRequested,
    SettingsRequested,
    StartRequested,
    StatuslineInstallRequested,
    TeamSwitchRequested,
    VerboseToggleRequested,
    WorktreeActionMenuRequested,
)

if TYPE_CHECKING:
    from .models import DashboardState


def handle_dashboard_action(
    state: DashboardState,
    action: Action[None],
    *,
    is_standalone: bool,
    get_placeholder_tip: object,
) -> tuple[DashboardState, bool | None]:
    """Handle a dashboard keyboard action and update state.

    This is a standalone function extracted from Dashboard._handle_action.
    It receives the current state and returns (possibly_updated_state, result).

    Args:
        state: Current dashboard state (mutated in place for list_state ops).
        action: The keyboard action to handle.
        is_standalone: Whether SCC is in standalone mode (no org).
        get_placeholder_tip: Callable(PlaceholderItem) -> str for tips.

    Returns:
        Tuple of (state, result) where result is:
        - True to force refresh (state changed by us, not action).
        - False to exit dashboard.
        - None to continue (refresh only if action.state_changed).
    """
    # Selective status clearing: only clear on navigation/filter/tab actions
    status_clearing_actions = {
        ActionType.NAVIGATE_UP,
        ActionType.NAVIGATE_DOWN,
        ActionType.TAB_NEXT,
        ActionType.TAB_PREV,
        ActionType.FILTER_CHAR,
        ActionType.FILTER_DELETE,
    }
    is_refresh_action = action.action_type == ActionType.CUSTOM and action.custom_key == "r"
    if state.status_message and (
        action.action_type in status_clearing_actions or is_refresh_action
    ):
        state.status_message = None

    match action.action_type:
        case ActionType.NAVIGATE_UP:
            state.list_state.move_cursor(-1)

        case ActionType.NAVIGATE_DOWN:
            state.list_state.move_cursor(1)

        case ActionType.TAB_NEXT:
            state = state.next_tab()

        case ActionType.TAB_PREV:
            state = state.prev_tab()

        case ActionType.FILTER_CHAR:
            if action.filter_char and state.filter_mode:
                state.list_state.add_filter_char(action.filter_char)

        case ActionType.FILTER_DELETE:
            if state.filter_mode or state.list_state.filter_query:
                state.list_state.delete_filter_char()

        case ActionType.CANCEL:
            if state.details_open:
                state.details_open = False
                return state, True
            if state.filter_mode or state.list_state.filter_query:
                state.list_state.clear_filter()
                state.filter_mode = False
                return state, True
            return state, None

        case ActionType.QUIT:
            return state, False

        case ActionType.TOGGLE:
            current = state.list_state.current_item
            if not current:
                return state, None
            if state.active_tab == DashboardTab.STATUS:
                state.status_message = "Details not available in Status tab"
                return state, True
            if state.is_placeholder_selected():
                if isinstance(current.value, PlaceholderItem):
                    state.status_message = get_placeholder_tip(current.value)  # type: ignore[operator]
                else:
                    state.status_message = "No details available for this item"
                return state, True
            state.details_open = not state.details_open
            return state, True

        case ActionType.SELECT:
            return _handle_select(state, is_standalone=is_standalone, get_placeholder_tip=get_placeholder_tip)

        case ActionType.TOGGLE_ALL:
            return _handle_toggle_all(state)

        case ActionType.TEAM_SWITCH:
            if is_standalone:
                state.status_message = (
                    "Teams require org mode. Run `scc setup` to configure."
                )
                return state, True
            raise TeamSwitchRequested()

        case ActionType.HELP:
            state.help_visible = True
            return state, True

        case ActionType.CUSTOM:
            return _handle_custom(state, action, is_standalone=is_standalone)

    return state, None


def _handle_select(
    state: DashboardState,
    *,
    is_standalone: bool,
    get_placeholder_tip: object,
) -> tuple[DashboardState, bool | None]:
    """Handle Enter/Select action."""
    if state.active_tab == DashboardTab.STATUS:
        current = state.list_state.current_item
        if current and isinstance(current.value, StatusItem):
            status_action = current.value.action
            if status_action is StatusAction.RESUME_SESSION and current.value.session:
                raise SessionResumeRequested(
                    session=current.value.session,
                    return_to=state.active_tab.name,
                )
            if status_action is StatusAction.START_SESSION:
                raise StartRequested(
                    return_to=state.active_tab.name,
                    reason="dashboard_start",
                )
            if status_action is StatusAction.SWITCH_TEAM:
                if is_standalone:
                    state.status_message = (
                        "Teams require org mode. Run `scc setup` to configure."
                    )
                    return state, True
                raise TeamSwitchRequested()
            if status_action is StatusAction.OPEN_TAB and current.value.action_tab:
                state.list_state.clear_filter()
                state = state.switch_tab(current.value.action_tab)
                return state, True
            if status_action is StatusAction.INSTALL_STATUSLINE:
                raise StatuslineInstallRequested(return_to=state.active_tab.name)
            if status_action is StatusAction.OPEN_PROFILE:
                raise ProfileMenuRequested(return_to=state.active_tab.name)
            if status_action is StatusAction.OPEN_SETTINGS:
                raise SettingsRequested(return_to=state.active_tab.name)
    else:
        current = state.list_state.current_item
        if not current:
            return state, None

        if state.is_placeholder_selected():
            if isinstance(current.value, PlaceholderItem):
                if current.value.startable:
                    raise StartRequested(
                        return_to=state.active_tab.name,
                        reason=placeholder_start_reason(current.value),
                    )
                state.status_message = get_placeholder_tip(current.value)  # type: ignore[operator]
                return state, True
            state.status_message = "No details available for this item"
            return state, True

        if state.active_tab == DashboardTab.SESSIONS and isinstance(
            current.value, SessionItem
        ):
            raise SessionResumeRequested(
                session=current.value.session,
                return_to=state.active_tab.name,
            )
        if state.active_tab == DashboardTab.WORKTREES and isinstance(
            current.value, WorktreeItem
        ):
            raise StartRequested(
                return_to=state.active_tab.name,
                reason=f"worktree:{current.value.path}",
            )
        if state.active_tab == DashboardTab.CONTAINERS and isinstance(
            current.value, ContainerItem
        ):
            raise ContainerActionMenuRequested(
                container_id=current.value.container.id,
                container_name=current.value.container.name,
                return_to=state.active_tab.name,
            )
        if state.active_tab == DashboardTab.SESSIONS and isinstance(
            current.value, SessionItem
        ):
            raise SessionActionMenuRequested(
                session=current.value.session,
                return_to=state.active_tab.name,
            )
        if state.active_tab == DashboardTab.WORKTREES and isinstance(
            current.value, WorktreeItem
        ):
            raise WorktreeActionMenuRequested(
                worktree_path=current.value.path,
                return_to=state.active_tab.name,
            )
        return state, None

    return state, None


def _handle_toggle_all(state: DashboardState) -> tuple[DashboardState, bool | None]:
    """Handle 'a' actions menu."""
    current = state.list_state.current_item
    if not current or state.is_placeholder_selected():
        state.status_message = "No item selected"
        return state, True

    if state.active_tab == DashboardTab.CONTAINERS and isinstance(
        current.value, ContainerItem
    ):
        raise ContainerActionMenuRequested(
            container_id=current.value.container.id,
            container_name=current.value.container.name,
            return_to=state.active_tab.name,
        )
    if state.active_tab == DashboardTab.SESSIONS and isinstance(
        current.value, SessionItem
    ):
        raise SessionActionMenuRequested(
            session=current.value.session,
            return_to=state.active_tab.name,
        )
    if state.active_tab == DashboardTab.WORKTREES and isinstance(
        current.value, WorktreeItem
    ):
        raise WorktreeActionMenuRequested(
            worktree_path=current.value.path,
            return_to=state.active_tab.name,
        )
    return state, None


def _handle_custom(
    state: DashboardState,
    action: Action[None],
    *,
    is_standalone: bool,
) -> tuple[DashboardState, bool | None]:
    """Handle custom dashboard-specific keys."""
    if action.custom_key == "/":
        state.filter_mode = True
        return state, True
    if action.custom_key == "r":
        raise RefreshRequested(return_to=state.active_tab.name)
    elif action.custom_key == "n":
        raise StartRequested(
            return_to=state.active_tab.name,
            reason="dashboard_new_session",
        )
    elif action.custom_key == "s":
        raise SettingsRequested(return_to=state.active_tab.name)
    elif action.custom_key == "p":
        if not state.list_state.filter_query:
            raise ProfileMenuRequested(return_to=state.active_tab.name)
    elif action.custom_key == "w":
        if state.active_tab == DashboardTab.WORKTREES:
            raise RecentWorkspacesRequested(return_to=state.active_tab.name)
    elif action.custom_key == "i":
        if state.active_tab == DashboardTab.STATUS:
            if not state.list_state.filter_query:
                raise SandboxImportRequested(return_to=state.active_tab.name)
        elif state.active_tab == DashboardTab.WORKTREES:
            current = state.list_state.current_item
            is_non_git = (
                current
                and isinstance(current.value, PlaceholderItem)
                and current.value.kind
                in {
                    PlaceholderKind.NO_GIT,
                    PlaceholderKind.NO_WORKTREES,
                }
            )
            if is_non_git:
                raise GitInitRequested(return_to=state.active_tab.name)
            state.status_message = "Already in a git repository"
            return state, True
    elif action.custom_key == "c":
        if state.active_tab == DashboardTab.WORKTREES:
            current = state.list_state.current_item
            is_git_repo = True
            if current and isinstance(current.value, PlaceholderItem):
                is_git_repo = current.value.kind not in {
                    PlaceholderKind.NO_GIT,
                    PlaceholderKind.NO_WORKTREES,
                }
            raise CreateWorktreeRequested(
                return_to=state.active_tab.name,
                is_git_repo=is_git_repo,
            )
    elif action.custom_key == "verbose_toggle":
        if state.active_tab == DashboardTab.WORKTREES:
            new_verbose = not state.verbose_worktrees
            raise VerboseToggleRequested(
                return_to=state.active_tab.name,
                verbose=new_verbose,
            )
    elif action.custom_key in {"K", "R", "D"}:
        if state.active_tab == DashboardTab.CONTAINERS:
            current = state.list_state.current_item
            if not current or state.is_placeholder_selected():
                state.status_message = "No container selected"
                return state, True

            from ...application.dashboard_models import ContainerSummary
            from ...docker.core import ContainerInfo

            key_container: ContainerInfo | ContainerSummary | None = None
            if isinstance(current.value, ContainerItem):
                key_container = current.value.container
            elif isinstance(current.value, ContainerInfo):
                key_container = current.value
            elif isinstance(current.value, str):
                status = None
                if current.description:
                    parts = current.description.split("  ")
                    if len(parts) >= 3:
                        status = parts[2]
                key_container = ContainerInfo(
                    id=current.value,
                    name=current.label,
                    status=status or "",
                )

            if not key_container:
                state.status_message = "Unable to read container metadata"
                return state, True

            if action.custom_key == "K":
                raise ContainerStopRequested(
                    container_id=key_container.id,
                    container_name=key_container.name,
                    return_to=state.active_tab.name,
                )
            if action.custom_key == "R":
                raise ContainerResumeRequested(
                    container_id=key_container.id,
                    container_name=key_container.name,
                    return_to=state.active_tab.name,
                )
            if action.custom_key == "D":
                raise ContainerRemoveRequested(
                    container_id=key_container.id,
                    container_name=key_container.name,
                    return_to=state.active_tab.name,
                )

    return state, None
