"""Dashboard component for interactive tabbed view.

This module contains the Dashboard class that provides the interactive
tabbed interface for SCC resources. It handles:
- Tab state management and navigation
- List rendering within each tab
- Details pane with responsive layout
- Action handling and state updates

The underscore prefix signals this is an internal implementation module.
Public API is exported via __init__.py.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from rich import box
from rich.console import Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from scc_cli.application.dashboard import (
    TAB_ORDER,
    ContainerItem,
    DashboardTab,
    PlaceholderItem,
    PlaceholderKind,
    SessionItem,
    StatusAction,
    StatusItem,
    WorktreeItem,
    placeholder_start_reason,
    placeholder_tip,
)

# Import config for standalone mode detection
from ... import config as scc_config
from ...theme import Indicators
from ..chrome import Chrome, ChromeConfig, FooterHint, get_layout_metrics
from ..keys import (
    Action,
    ActionType,
    ContainerActionMenuRequested,
    ContainerRemoveRequested,
    ContainerResumeRequested,
    ContainerStopRequested,
    CreateWorktreeRequested,
    GitInitRequested,
    KeyReader,
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
from ..list_screen import ListItem
from ..time_format import format_relative_time_from_datetime
from .models import DashboardState


class Dashboard:
    """Interactive tabbed dashboard for SCC resources.

    The Dashboard provides a unified view of SCC resources organized by tabs.
    It handles tab switching, navigation within tabs, and rendering.

    Attributes:
        state: Current dashboard state (tabs, active tab, list state).
    """

    def __init__(self, state: DashboardState) -> None:
        """Initialize dashboard.

        Args:
            state: Initial dashboard state with tab data.
        """
        self.state = state
        from ...console import get_err_console

        self._console = get_err_console()
        # Track last layout mode for hysteresis (prevents flip-flop at resize boundary)
        self._last_side_by_side: bool | None = None
        self._layout_width: int | None = None

    def run(self) -> None:
        """Run the interactive dashboard.

        Blocks until the user quits (q or Esc).
        """
        # Use custom_keys for dashboard-specific actions that aren't in DEFAULT_KEY_MAP
        # This allows 'r' to be a filter char in pickers but REFRESH in dashboard
        # 'n' (new session) is also screen-specific to avoid global key conflicts
        # 'w', 'i', 'c' are for Worktrees tab: recent workspaces, git init, create/clone
        # 'v' toggles verbose status display in Worktrees tab
        # 'K'/'R'/'D' are for Containers tab: stop/resume/delete (uppercase avoids filter collisions)
        reader = KeyReader(
            custom_keys={
                "r": "refresh",
                "n": "new_session",
                "s": "settings",
                "p": "profile_menu",
                "w": "recent_workspaces",
                "i": "git_init",
                "c": "create_worktree",
                "v": "verbose_toggle",
                "K": "container_stop",
                "R": "container_resume",
                "D": "container_remove",
                "/": "filter_mode",
            },
            enable_filter=True,
            require_filter_mode=True,
        )

        with Live(
            self._render(),
            console=self._console,
            auto_refresh=False,  # Manual refresh for instant response
            transient=True,
        ) as live:
            while True:
                # Pass filter_active based on actual filter state, not always True
                # When filter is empty, j/k navigate; when typing, j/k become filter chars
                action = reader.read(
                    filter_active=self.state.filter_mode,
                    filter_mode=self.state.filter_mode,
                )

                # Help overlay dismissal: any key while help is visible just closes help
                # This is the standard pattern for modal overlays in Rich Live applications
                if self.state.help_visible:
                    self.state.help_visible = False
                    live.update(self._render(), refresh=True)
                    continue  # Consume the keypress (don't process it further)

                result = self._handle_action(action)
                if result is False:
                    return

                # Refresh if action changed state OR handler requests refresh
                needs_refresh = result is True or action.state_changed
                if needs_refresh:
                    live.update(self._render(), refresh=True)

    def _render(self) -> RenderableType:
        """Render the current dashboard state.

        Uses responsive layout when details pane is open:
        - ≥110 columns: side-by-side (list | details)
        - <110 columns: stacked (list above details)
        - Status tab: details auto-hidden via render rule

        Help overlay is rendered INSIDE the Live context to avoid scroll artifacts.
        When help_visible is True, the help panel overlays the normal content.
        """
        # If help overlay is visible, render it instead of normal content
        # This renders INSIDE the Live context, avoiding scroll artifacts
        if self.state.help_visible:
            from ..help import HelpMode, render_help_content

            return render_help_content(HelpMode.DASHBOARD, console=self._console, max_width=120)

        list_body = self._render_list_body()
        config = self._get_chrome_config()
        chrome = Chrome(config, console=self._console, max_width=120)

        metrics = get_layout_metrics(self._console, max_width=120)
        available_width = (
            metrics.inner_width(padding_x=1, border=2)
            if metrics.apply
            else self._console.size.width
        )
        self._layout_width = available_width

        # Check if details should be shown (render rule: not on Status tab)
        show_details = self.state.details_open and self.state.active_tab != DashboardTab.STATUS

        body: RenderableType = list_body
        if show_details and not self.state.is_placeholder_selected():
            # Render details pane content
            details = self._render_details_pane()

            # Responsive layout with hysteresis to prevent flip-flop at resize boundary
            # Thresholds: ≥112 → side-by-side, ≤108 → stacked, 109-111 → maintain previous
            if available_width >= 112:
                side_by_side = True
            elif available_width <= 108:
                side_by_side = False
            elif self._last_side_by_side is not None:
                # In dead zone (109-111): maintain previous layout
                side_by_side = self._last_side_by_side
            else:
                # First render in dead zone: default to stacked (conservative)
                side_by_side = False

            self._last_side_by_side = side_by_side
            body = self._render_split_view(
                list_body,
                details,
                side_by_side=side_by_side,
            )

        return chrome.render(body, search_query=self.state.list_state.filter_query)

    def _render_list_body(self) -> Text:
        """Render the list content for the active tab."""
        text = Text()
        filtered = self.state.list_state.filtered_items
        visible = self.state.list_state.visible_items

        if not filtered:
            if self.state.list_state.filter_query:
                text.append("No matches", style="dim italic")
                text.append(" — ", style="dim")
                text.append("Esc", style="cyan")
                text.append(" to clear filter", style="dim")
            else:
                text.append("No items", style="dim italic")
        else:
            for i, item in enumerate(visible):
                actual_index = self.state.list_state.scroll_offset + i
                is_cursor = actual_index == self.state.list_state.cursor

                if is_cursor:
                    text.append(f"{Indicators.get('CURSOR')} ", style="cyan bold")
                else:
                    text.append("  ")

                label_style = "bold" if is_cursor else ""
                text.append(item.label, style=label_style)

                if item.description:
                    text.append(f"  {item.description}", style="dim")

                text.append("\n")

        # Render status message if present (transient toast)
        if self.state.status_message:
            text.append("\n")
            text.append("Note: ", style="yellow")
            text.append(self.state.status_message, style="yellow")
            text.append("\n")

        return text

    def _render_split_view(
        self,
        list_body: RenderableType,
        details: RenderableType,
        *,
        side_by_side: bool,
    ) -> RenderableType:
        """Render list and details in split view.

        Uses consistent padding and separators for smooth transitions
        between side-by-side and stacked layouts.

        Args:
            list_body: The list content.
            details: The details pane content.
            side_by_side: If True, render columns; otherwise stack vertically.

        Returns:
            Combined renderable.
        """
        details_panel = Panel(
            details,
            border_style="bright_black",
            box=box.ROUNDED,
            padding=(0, 1),
        )

        if side_by_side:
            table = Table.grid(expand=True, padding=(0, 1))
            table.add_column("list", ratio=3, no_wrap=False)
            table.add_column("sep", width=1, style="dim", justify="center")
            table.add_column("details", ratio=2, no_wrap=False)
            table.add_row(list_body, Indicators.get("VERTICAL_LINE"), details_panel)
            return table

        available_width = self._layout_width or self._console.size.width
        separator_width = max(24, min(90, available_width - 6))
        separator = Text(Indicators.get("HORIZONTAL_LINE") * separator_width, style="dim")
        return Group(
            list_body,
            Text(""),
            separator,
            Text(""),
            details_panel,
        )

    def _render_details_pane(self) -> RenderableType:
        """Render details pane content for the current item.

        Content varies by active tab:
        - Containers: ID, status, profile, workspace, commands
        - Sessions: name, path, branch, last_used, resume command
        - Worktrees: path, branch, dirty status, start command

        Returns:
            Details pane as Rich renderable.
        """
        current = self.state.list_state.current_item
        if not current:
            return Text("No item selected", style="dim italic")

        tab = self.state.active_tab

        if tab == DashboardTab.CONTAINERS:
            return self._render_container_details(current)
        elif tab == DashboardTab.SESSIONS:
            return self._render_session_details(current)
        elif tab == DashboardTab.WORKTREES:
            return self._render_worktree_details(current)
        else:
            return Text("Details not available", style="dim")

    def _build_details_header(self, title: str) -> Text:
        """Build a consistent header for details panels."""
        available_width = self._layout_width or self._console.size.width
        width = max(20, min(40, available_width // 3))
        header = Text()
        header.append(f"{title}\n", style="bold cyan")
        header.append(Indicators.get("HORIZONTAL_LINE") * width, style="dim")
        return header

    def _render_container_details(self, item: ListItem[Any]) -> RenderableType:
        """Render details for a container item using structured key/value table."""
        from ...docker.core import ContainerInfo
        from ..formatters import _shorten_docker_status

        header = self._build_details_header("Container Details")

        # Key/value table
        table = Table.grid(padding=(0, 1))
        table.add_column("key", style="dim", width=10)
        table.add_column("value", overflow="fold")

        table.add_row("Name", Text(item.label, style="bold"))

        container: ContainerInfo | None = None
        if isinstance(item.value, ContainerItem):
            container = item.value.container
        elif isinstance(item.value, ContainerInfo):
            container = item.value
        elif isinstance(item.value, str):
            # Legacy fallback when value is container ID
            profile = None
            workspace = None
            status = None
            if item.description:
                parts = item.description.split("  ")
                if len(parts) >= 1 and parts[0]:
                    profile = parts[0]
                if len(parts) >= 2 and parts[1]:
                    workspace = parts[1]
                if len(parts) >= 3 and parts[2]:
                    status = parts[2]
            container = ContainerInfo(
                id=item.value,
                name=item.label,
                status=status or "",
                profile=profile,
                workspace=workspace,
            )

        if container:
            container_id = container.id[:12] if len(container.id) > 12 else container.id
            table.add_row("ID", container_id)

            if container.profile:
                table.add_row("Profile", container.profile)
            if container.workspace:
                table.add_row("Workspace", container.workspace)
            if container.status:
                table.add_row("Status", _shorten_docker_status(container.status))

        # Commands section
        commands = Text()
        commands.append("\nCommands\n", style="dim")
        commands.append(f"  docker exec -it {item.label} bash\n", style="cyan")
        commands.append(f"  scc stop {item.label}\n", style="cyan")
        commands.append("  scc prune  # remove stopped containers\n", style="cyan")

        return Group(header, table, commands)

    def _render_session_details(self, item: ListItem[Any]) -> RenderableType:
        """Render details for a session item using structured key/value table."""
        session_source = item.value
        if isinstance(session_source, SessionItem):
            session = session_source.session
        else:
            return Text("Session details unavailable", style="dim italic")

        header = self._build_details_header("Session Details")

        # Key/value table
        table = Table.grid(padding=(0, 1))
        table.add_column("key", style="dim", width=10)
        table.add_column("value", overflow="fold")

        table.add_row("Name", Text(item.label, style="bold"))

        if session.team:
            table.add_row("Team", str(session.team))
        if session.branch:
            table.add_row("Branch", str(session.branch))
        if session.workspace:
            table.add_row("Workspace", str(session.workspace))
        if session.last_used:
            table.add_row("Last Used", self._format_session_last_used(session.last_used))

        commands = Text()
        commands.append("\nCommands\n", style="dim")

        container_name = session.container_name

        if container_name:
            commands.append(f"  scc resume {container_name}\n", style="cyan")
        elif session.workspace:
            commands.append("  Container stopped. Start new session:\n", style="dim italic")
            commands.append(f"  scc start --workspace {session.workspace}\n", style="cyan")
        else:
            commands.append("  Start session: scc start\n", style="cyan dim")

        return Group(header, table, commands)

    def _format_session_last_used(self, iso_timestamp: str) -> str:
        try:
            dt = datetime.fromisoformat(iso_timestamp)
        except ValueError:
            return iso_timestamp
        return format_relative_time_from_datetime(dt)

    def _render_worktree_details(self, item: ListItem[Any]) -> RenderableType:
        """Render details for a worktree item using structured key/value table."""
        header = self._build_details_header("Worktree Details")

        # Key/value table
        table = Table.grid(padding=(0, 1))
        table.add_column("key", style="dim", width=10)
        table.add_column("value", overflow="fold")

        table.add_row("Name", Text(item.label, style="bold"))
        worktree_path = item.value.path if isinstance(item.value, WorktreeItem) else item.value
        table.add_row("Path", worktree_path)

        # Parse description into fields (branch  modified  +1 !2 ?3  (current))
        if item.description:
            parts = [part for part in item.description.split("  ") if part]
            for part in parts:
                if part.startswith("(") and part.endswith(")"):
                    status_label = part.strip("()").replace("_", " ").title()
                    table.add_row("Status", Text(status_label, style="green"))
                    continue

                if part == "modified":
                    table.add_row("Changes", Text("Modified", style="yellow"))
                    continue

                if part == "clean":
                    table.add_row("Status", Text("Clean", style="green"))
                    continue

                if part == "status timeout":
                    table.add_row("Status", Text("Git status timed out", style="yellow"))
                    continue

                change_summary = self._format_worktree_change_summary(part)
                if change_summary:
                    table.add_row("Changes", Text(change_summary, style="yellow"))
                    continue

                table.add_row("Branch", part)

        # Commands section
        commands = Text()
        commands.append("\nCommands\n", style="dim")
        commands.append(f"  scc start {worktree_path}\n", style="cyan")

        return Group(header, table, commands)

    def _format_worktree_change_summary(self, part: str) -> str | None:
        """Format git status counts from a worktree description segment."""
        tokens = part.split()
        if not tokens:
            return None

        if not all(token[:1] in {"+", "!", "?"} for token in tokens):
            return None

        summaries: list[str] = []
        labels = {"+": "staged", "!": "modified", "?": "untracked"}
        for token in tokens:
            prefix = token[:1]
            count = token[1:]
            if not count:
                continue
            label = labels.get(prefix)
            if label:
                summaries.append(f"{label} {count}")

        return " · ".join(summaries) if summaries else None

    def _get_placeholder_tip(self, item: PlaceholderItem) -> str:
        """Get contextual help tip for placeholder items."""
        return placeholder_tip(item.kind)

    def _compute_footer_hints(
        self, _standalone: bool, show_details: bool
    ) -> tuple[FooterHint, ...]:
        """Compute concise footer hints for the active tab."""
        hints: list[FooterHint] = [FooterHint("↑↓", "navigate")]
        current = self.state.list_state.current_item

        primary_action: str | None = None
        if self.state.active_tab == DashboardTab.STATUS:
            if current and isinstance(current.value, StatusItem):
                match current.value.action:
                    case StatusAction.RESUME_SESSION:
                        primary_action = "resume"
                    case StatusAction.START_SESSION:
                        primary_action = "start"
                    case StatusAction.SWITCH_TEAM:
                        primary_action = "switch"
                    case (
                        StatusAction.OPEN_TAB
                        | StatusAction.OPEN_PROFILE
                        | StatusAction.OPEN_SETTINGS
                    ):
                        primary_action = "open"
                    case StatusAction.INSTALL_STATUSLINE:
                        primary_action = "install"
                    case None:
                        primary_action = None
        elif self.state.is_placeholder_selected():
            if current and isinstance(current.value, PlaceholderItem) and current.value.startable:
                primary_action = "start"
        else:
            if self.state.active_tab == DashboardTab.SESSIONS:
                primary_action = "resume"
            elif self.state.active_tab == DashboardTab.WORKTREES:
                primary_action = "start"
            elif self.state.active_tab == DashboardTab.CONTAINERS:
                primary_action = "actions"
            else:
                primary_action = "open"

        if primary_action:
            hints.append(FooterHint("Enter", primary_action))

        if show_details:
            hints.append(FooterHint("Space", "close"))
        elif (
            self.state.active_tab != DashboardTab.STATUS
            and not self.state.is_placeholder_selected()
        ):
            hints.append(FooterHint("Space", "details"))

        if self.state.active_tab == DashboardTab.WORKTREES and not show_details:
            is_git_repo = True
            if current and isinstance(current.value, PlaceholderItem):
                is_git_repo = current.value.kind not in {
                    PlaceholderKind.NO_GIT,
                    PlaceholderKind.NO_WORKTREES,
                }
            hints.append(FooterHint("c", "create" if is_git_repo else "clone"))

        hints.append(FooterHint("Tab", "tabs"))

        if self.state.filter_mode or self.state.list_state.filter_query:
            hints.append(FooterHint("Esc", "clear filter"))
        else:
            hints.append(FooterHint("/", "filter"))

        hints.append(FooterHint("?", "more"))
        return tuple(hints)

    def _get_chrome_config(self) -> ChromeConfig:
        """Get chrome configuration for current state."""
        tab_names = [tab.display_name for tab in TAB_ORDER]
        active_index = TAB_ORDER.index(self.state.active_tab)
        standalone = scc_config.is_standalone_mode()

        # Render rule: auto-hide details on Status tab (no state mutation)
        show_details = self.state.details_open and self.state.active_tab != DashboardTab.STATUS

        # Compute dynamic footer hints based on current context
        footer_hints = self._compute_footer_hints(standalone, show_details)
        search_hint = "type to search" if self.state.filter_mode else "press / to search"

        return ChromeConfig.for_dashboard(
            tab_names,
            active_index,
            standalone=standalone,
            details_open=show_details,
            search_hint=search_hint,
            custom_hints=footer_hints,
        )

    def _handle_action(self, action: Action[None]) -> bool | None:
        """Handle an action and update state.

        Returns:
            True to force refresh (state changed by us, not action).
            False to exit dashboard.
            None to continue (refresh only if action.state_changed).
        """
        # Selective status clearing: only clear on navigation/filter/tab actions
        # This preserves toast messages during non-state-changing actions (e.g., help)
        status_clearing_actions = {
            ActionType.NAVIGATE_UP,
            ActionType.NAVIGATE_DOWN,
            ActionType.TAB_NEXT,
            ActionType.TAB_PREV,
            ActionType.FILTER_CHAR,
            ActionType.FILTER_DELETE,
        }
        # Also clear status on 'r' (refresh), which is a CUSTOM action in dashboard
        is_refresh_action = action.action_type == ActionType.CUSTOM and action.custom_key == "r"
        if self.state.status_message and (
            action.action_type in status_clearing_actions or is_refresh_action
        ):
            self.state.status_message = None

        match action.action_type:
            case ActionType.NAVIGATE_UP:
                self.state.list_state.move_cursor(-1)

            case ActionType.NAVIGATE_DOWN:
                self.state.list_state.move_cursor(1)

            case ActionType.TAB_NEXT:
                self.state = self.state.next_tab()

            case ActionType.TAB_PREV:
                self.state = self.state.prev_tab()

            case ActionType.FILTER_CHAR:
                if action.filter_char and self.state.filter_mode:
                    self.state.list_state.add_filter_char(action.filter_char)

            case ActionType.FILTER_DELETE:
                if self.state.filter_mode or self.state.list_state.filter_query:
                    self.state.list_state.delete_filter_char()

            case ActionType.CANCEL:
                # ESC precedence: details → filter → no-op
                if self.state.details_open:
                    self.state.details_open = False
                    return True
                if self.state.filter_mode or self.state.list_state.filter_query:
                    self.state.list_state.clear_filter()
                    self.state.filter_mode = False
                    return True
                return None

            case ActionType.QUIT:
                return False

            case ActionType.TOGGLE:
                # Space toggles details pane
                current = self.state.list_state.current_item
                if not current:
                    return None
                if self.state.active_tab == DashboardTab.STATUS:
                    self.state.status_message = "Details not available in Status tab"
                    return True
                if self.state.is_placeholder_selected():
                    if isinstance(current.value, PlaceholderItem):
                        self.state.status_message = self._get_placeholder_tip(current.value)
                    else:
                        self.state.status_message = "No details available for this item"
                    return True
                self.state.details_open = not self.state.details_open
                return True

            case ActionType.SELECT:
                # On Status tab, Enter triggers different actions based on item
                if self.state.active_tab == DashboardTab.STATUS:
                    current = self.state.list_state.current_item
                    if current and isinstance(current.value, StatusItem):
                        status_action = current.value.action
                        if status_action is StatusAction.RESUME_SESSION and current.value.session:
                            raise SessionResumeRequested(
                                session=current.value.session,
                                return_to=self.state.active_tab.name,
                            )

                        if status_action is StatusAction.START_SESSION:
                            raise StartRequested(
                                return_to=self.state.active_tab.name,
                                reason="dashboard_start",
                            )

                        if status_action is StatusAction.SWITCH_TEAM:
                            if scc_config.is_standalone_mode():
                                self.state.status_message = (
                                    "Teams require org mode. Run `scc setup` to configure."
                                )
                                return True
                            raise TeamSwitchRequested()

                        if status_action is StatusAction.OPEN_TAB and current.value.action_tab:
                            self.state.list_state.clear_filter()
                            self.state = self.state.switch_tab(current.value.action_tab)
                            return True

                        if status_action is StatusAction.INSTALL_STATUSLINE:
                            raise StatuslineInstallRequested(return_to=self.state.active_tab.name)

                        if status_action is StatusAction.OPEN_PROFILE:
                            raise ProfileMenuRequested(return_to=self.state.active_tab.name)

                        if status_action is StatusAction.OPEN_SETTINGS:
                            raise SettingsRequested(return_to=self.state.active_tab.name)
                else:
                    # Resource tabs handling (Containers, Worktrees, Sessions)
                    current = self.state.list_state.current_item
                    if not current:
                        return None

                    if self.state.is_placeholder_selected():
                        if isinstance(current.value, PlaceholderItem):
                            if current.value.startable:
                                raise StartRequested(
                                    return_to=self.state.active_tab.name,
                                    reason=placeholder_start_reason(current.value),
                                )
                            self.state.status_message = self._get_placeholder_tip(current.value)
                            return True
                        self.state.status_message = "No details available for this item"
                        return True

                    if self.state.active_tab == DashboardTab.SESSIONS and isinstance(
                        current.value, SessionItem
                    ):
                        raise SessionResumeRequested(
                            session=current.value.session,
                            return_to=self.state.active_tab.name,
                        )

                    if self.state.active_tab == DashboardTab.WORKTREES and isinstance(
                        current.value, WorktreeItem
                    ):
                        raise StartRequested(
                            return_to=self.state.active_tab.name,
                            reason=f"worktree:{current.value.path}",
                        )

                    if self.state.active_tab == DashboardTab.CONTAINERS and isinstance(
                        current.value, ContainerItem
                    ):
                        raise ContainerActionMenuRequested(
                            container_id=current.value.container.id,
                            container_name=current.value.container.name,
                            return_to=self.state.active_tab.name,
                        )

                    if self.state.active_tab == DashboardTab.SESSIONS and isinstance(
                        current.value, SessionItem
                    ):
                        raise SessionActionMenuRequested(
                            session=current.value.session,
                            return_to=self.state.active_tab.name,
                        )

                    if self.state.active_tab == DashboardTab.WORKTREES and isinstance(
                        current.value, WorktreeItem
                    ):
                        raise WorktreeActionMenuRequested(
                            worktree_path=current.value.path,
                            return_to=self.state.active_tab.name,
                        )

                    return None

            case ActionType.TOGGLE_ALL:
                # 'a' actions menu
                current = self.state.list_state.current_item
                if not current or self.state.is_placeholder_selected():
                    self.state.status_message = "No item selected"
                    return True

                if self.state.active_tab == DashboardTab.CONTAINERS and isinstance(
                    current.value, ContainerItem
                ):
                    raise ContainerActionMenuRequested(
                        container_id=current.value.container.id,
                        container_name=current.value.container.name,
                        return_to=self.state.active_tab.name,
                    )

                if self.state.active_tab == DashboardTab.SESSIONS and isinstance(
                    current.value, SessionItem
                ):
                    raise SessionActionMenuRequested(
                        session=current.value.session,
                        return_to=self.state.active_tab.name,
                    )

                if self.state.active_tab == DashboardTab.WORKTREES and isinstance(
                    current.value, WorktreeItem
                ):
                    raise WorktreeActionMenuRequested(
                        worktree_path=current.value.path,
                        return_to=self.state.active_tab.name,
                    )

                return None

            case ActionType.TEAM_SWITCH:
                # In standalone mode, show guidance instead of switching
                if scc_config.is_standalone_mode():
                    self.state.status_message = (
                        "Teams require org mode. Run `scc setup` to configure."
                    )
                    return True  # Refresh to show message
                # Bubble up to orchestrator for consistent team switching
                raise TeamSwitchRequested()

            case ActionType.HELP:
                # Show help overlay INSIDE the Live context (avoids scroll artifacts)
                # The overlay is rendered in _render() and dismissed on next keypress
                self.state.help_visible = True
                return True  # Refresh to show help overlay

            case ActionType.CUSTOM:
                # Handle dashboard-specific custom keys (not in DEFAULT_KEY_MAP)
                if action.custom_key == "/":
                    self.state.filter_mode = True
                    return True
                if action.custom_key == "r":
                    # User pressed 'r' - signal orchestrator to reload tab data
                    # Uses .name (stable identifier) not .value (display string)
                    raise RefreshRequested(return_to=self.state.active_tab.name)
                elif action.custom_key == "n":
                    # User pressed 'n' - start new session (skip any resume prompts)
                    raise StartRequested(
                        return_to=self.state.active_tab.name,
                        reason="dashboard_new_session",
                    )
                elif action.custom_key == "s":
                    # User pressed 's' - open settings and maintenance screen
                    raise SettingsRequested(return_to=self.state.active_tab.name)
                elif action.custom_key == "p":
                    # User pressed 'p' - open profile menu
                    # Only works when filter is empty to avoid conflict with type-to-filter
                    if not self.state.list_state.filter_query:
                        raise ProfileMenuRequested(return_to=self.state.active_tab.name)
                    # When filter is active, 'p' is treated as filter char (handled by KeyReader)
                elif action.custom_key == "w":
                    # User pressed 'w' - show recent workspaces picker
                    # Only active on Worktrees tab
                    if self.state.active_tab == DashboardTab.WORKTREES:
                        raise RecentWorkspacesRequested(return_to=self.state.active_tab.name)
                elif action.custom_key == "i":
                    # User pressed 'i' - context-aware action
                    # Status tab: import sandbox plugins (only when filter is empty)
                    if self.state.active_tab == DashboardTab.STATUS:
                        if not self.state.list_state.filter_query:
                            raise SandboxImportRequested(return_to=self.state.active_tab.name)
                    elif self.state.active_tab == DashboardTab.WORKTREES:
                        current = self.state.list_state.current_item
                        # Only show when placeholder indicates no git repo
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
                            raise GitInitRequested(return_to=self.state.active_tab.name)
                        self.state.status_message = "Already in a git repository"
                        return True
                elif action.custom_key == "c":
                    # User pressed 'c' - create worktree (or clone if not git)
                    # Only active on Worktrees tab
                    if self.state.active_tab == DashboardTab.WORKTREES:
                        current = self.state.list_state.current_item
                        # Check if we're in a git repo
                        is_git_repo = True
                        if current and isinstance(current.value, PlaceholderItem):
                            is_git_repo = current.value.kind not in {
                                PlaceholderKind.NO_GIT,
                                PlaceholderKind.NO_WORKTREES,
                            }
                        raise CreateWorktreeRequested(
                            return_to=self.state.active_tab.name,
                            is_git_repo=is_git_repo,
                        )
                elif action.custom_key == "verbose_toggle":
                    # User pressed 'v' - toggle verbose status display
                    # Only active on Worktrees tab
                    if self.state.active_tab == DashboardTab.WORKTREES:
                        new_verbose = not self.state.verbose_worktrees
                        raise VerboseToggleRequested(
                            return_to=self.state.active_tab.name,
                            verbose=new_verbose,
                        )
                elif action.custom_key in {"K", "R", "D"}:
                    # Container actions: stop/resume/delete
                    if self.state.active_tab == DashboardTab.CONTAINERS:
                        current = self.state.list_state.current_item
                        if not current or self.state.is_placeholder_selected():
                            self.state.status_message = "No container selected"
                            return True

                        from ...docker.core import ContainerInfo

                        key_container: ContainerInfo | None = None
                        if isinstance(current.value, ContainerItem):
                            key_container = current.value.container
                        elif isinstance(current.value, ContainerInfo):
                            key_container = current.value
                        elif isinstance(current.value, str):
                            # Legacy fallback when value is container ID
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
                            self.state.status_message = "Unable to read container metadata"
                            return True

                        if action.custom_key == "K":
                            raise ContainerStopRequested(
                                container_id=key_container.id,
                                container_name=key_container.name,
                                return_to=self.state.active_tab.name,
                            )
                        if action.custom_key == "R":
                            raise ContainerResumeRequested(
                                container_id=key_container.id,
                                container_name=key_container.name,
                                return_to=self.state.active_tab.name,
                            )
                        if action.custom_key == "D":
                            raise ContainerRemoveRequested(
                                container_id=key_container.id,
                                container_name=key_container.name,
                                return_to=self.state.active_tab.name,
                            )

        return None
