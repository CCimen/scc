"""Tabbed dashboard orchestration for the main SCC view.

This module provides the Dashboard component that presents a tabbed interface
for navigating SCC resources (Status, Containers, Sessions, Worktrees).

The dashboard reuses ListScreen for navigation within each tab, and Chrome
for consistent visual presentation. It handles:
- Tab state management (active tab, cycling)
- Tab-specific content loading
- Consistent navigation and keybinding behavior

Example:
    >>> from scc_cli.ui.dashboard import run_dashboard
    >>> run_dashboard()  # Blocks until user quits

The dashboard is the default behavior when running `scc` with no arguments
in an interactive TTY environment.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto

from rich.console import Console, RenderableType
from rich.live import Live
from rich.text import Text

from .chrome import Chrome, ChromeConfig
from .keys import Action, ActionType, KeyReader, TeamSwitchRequested
from .list_screen import ListItem, ListState


class DashboardTab(Enum):
    """Available dashboard tabs.

    Each tab represents a major resource category in SCC.
    Tabs are displayed in definition order (Status first, Worktrees last).
    """

    STATUS = auto()
    CONTAINERS = auto()
    SESSIONS = auto()
    WORKTREES = auto()

    @property
    def display_name(self) -> str:
        """Human-readable name for display in chrome."""
        names = {
            DashboardTab.STATUS: "Status",
            DashboardTab.CONTAINERS: "Containers",
            DashboardTab.SESSIONS: "Sessions",
            DashboardTab.WORKTREES: "Worktrees",
        }
        return names[self]


# Ordered list for tab cycling
_TAB_ORDER = [
    DashboardTab.STATUS,
    DashboardTab.CONTAINERS,
    DashboardTab.SESSIONS,
    DashboardTab.WORKTREES,
]


@dataclass
class TabData:
    """Data for a single dashboard tab.

    Attributes:
        tab: The tab identifier.
        title: Display title for the tab content area.
        items: List items to display in this tab.
        count_active: Number of active items (e.g., running containers).
        count_total: Total number of items.
    """

    tab: DashboardTab
    title: str
    items: Sequence[ListItem[str]]
    count_active: int
    count_total: int

    @property
    def subtitle(self) -> str:
        """Generate subtitle from counts."""
        if self.count_active == self.count_total:
            return f"{self.count_total} total"
        return f"{self.count_active} active, {self.count_total} total"


@dataclass
class DashboardState:
    """State for the tabbed dashboard view.

    Manages which tab is active and provides methods for tab navigation.
    Each tab switch resets the list state for the new tab.

    Attributes:
        active_tab: Currently active tab.
        tabs: Mapping from tab to its data.
        list_state: Navigation state for the current tab's list.
    """

    active_tab: DashboardTab
    tabs: dict[DashboardTab, TabData]
    list_state: ListState[str]

    @property
    def current_tab_data(self) -> TabData:
        """Get data for the currently active tab."""
        return self.tabs[self.active_tab]

    def switch_tab(self, tab: DashboardTab) -> DashboardState:
        """Create new state with different active tab.

        Resets list state (cursor, filter) for the new tab.

        Args:
            tab: Tab to switch to.

        Returns:
            New DashboardState with the specified tab active.
        """
        new_list_state = ListState(items=self.tabs[tab].items)
        return DashboardState(
            active_tab=tab,
            tabs=self.tabs,
            list_state=new_list_state,
        )

    def next_tab(self) -> DashboardState:
        """Switch to the next tab (wraps around).

        Returns:
            New DashboardState with next tab active.
        """
        current_index = _TAB_ORDER.index(self.active_tab)
        next_index = (current_index + 1) % len(_TAB_ORDER)
        return self.switch_tab(_TAB_ORDER[next_index])

    def prev_tab(self) -> DashboardState:
        """Switch to the previous tab (wraps around).

        Returns:
            New DashboardState with previous tab active.
        """
        current_index = _TAB_ORDER.index(self.active_tab)
        prev_index = (current_index - 1) % len(_TAB_ORDER)
        return self.switch_tab(_TAB_ORDER[prev_index])


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
        self._console = Console()

    def run(self) -> None:
        """Run the interactive dashboard.

        Blocks until the user quits (q or Esc).
        """
        reader = KeyReader(enable_filter=True)

        with Live(
            self._render(),
            console=self._console,
            refresh_per_second=4,  # Required > 0, we use manual refresh
            transient=True,
        ) as live:
            while True:
                action = reader.read()

                result = self._handle_action(action)
                if result is False:
                    return

                if action.state_changed:
                    live.update(self._render())

    def _render(self) -> RenderableType:
        """Render the current dashboard state."""
        body = self._render_list_body()
        config = self._get_chrome_config()
        chrome = Chrome(config)
        return chrome.render(body, search_query=self.state.list_state.filter_query)

    def _render_list_body(self) -> Text:
        """Render the list content for the active tab."""
        text = Text()
        filtered = self.state.list_state.filtered_items
        visible = self.state.list_state.visible_items

        if not filtered:
            text.append("No items", style="dim italic")
            return text

        for i, item in enumerate(visible):
            actual_index = self.state.list_state.scroll_offset + i
            is_cursor = actual_index == self.state.list_state.cursor

            if is_cursor:
                text.append("❯ ", style="cyan bold")
            else:
                text.append("  ")

            label_style = "bold" if is_cursor else ""
            text.append(item.label, style=label_style)

            if item.description:
                text.append(f"  {item.description}", style="dim")

            text.append("\n")

        return text

    def _get_chrome_config(self) -> ChromeConfig:
        """Get chrome configuration for current state."""
        tab_names = [tab.display_name for tab in _TAB_ORDER]
        active_index = _TAB_ORDER.index(self.state.active_tab)

        return ChromeConfig.for_dashboard(tab_names, active_index)

    def _handle_action(self, action: Action[None]) -> bool | None:
        """Handle an action and return False to exit.

        Returns:
            False to exit dashboard, None to continue.
        """
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
                if action.filter_char:
                    self.state.list_state.add_filter_char(action.filter_char)

            case ActionType.FILTER_DELETE:
                self.state.list_state.delete_filter_char()

            case ActionType.CANCEL | ActionType.QUIT:
                return False

            case ActionType.TEAM_SWITCH:
                # Bubble up to orchestrator for consistent team switching
                raise TeamSwitchRequested()

            case ActionType.HELP:
                # Show dashboard-specific help overlay
                from .help import HelpMode, show_help_overlay

                show_help_overlay(HelpMode.DASHBOARD, self._console)

        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Tab Data Loading Functions
# ═══════════════════════════════════════════════════════════════════════════════


def _load_status_tab_data() -> TabData:
    """Load Status tab data showing system overview.

    The Status tab displays:
    - Current team and organization info
    - Sync status with remote config
    - Resource counts for quick overview

    Returns:
        TabData with status summary items.
    """
    # Import here to avoid circular imports
    from .. import config, sessions
    from ..docker import core as docker_core

    items: list[ListItem[str]] = []

    # Load current team info
    try:
        user_config = config.load_user_config()
        team = user_config.get("selected_profile")
        org_source = user_config.get("organization_source")

        if team:
            items.append(
                ListItem(
                    value="team",
                    label="Team",
                    description=str(team),
                )
            )
        else:
            items.append(
                ListItem(
                    value="team",
                    label="Team",
                    description="No team selected",
                )
            )

        # Organization/sync status
        if org_source and isinstance(org_source, dict):
            org_url = org_source.get("url", "")
            if org_url:
                # Extract domain for display
                domain = org_url.replace("https://", "").replace("http://", "").split("/")[0]
                items.append(
                    ListItem(
                        value="organization",
                        label="Organization",
                        description=domain,
                    )
                )
        elif user_config.get("standalone"):
            items.append(
                ListItem(
                    value="organization",
                    label="Mode",
                    description="Standalone (no remote config)",
                )
            )

    except Exception:
        items.append(
            ListItem(
                value="config_error",
                label="Configuration",
                description="Error loading config",
            )
        )

    # Load container count
    try:
        containers = docker_core.list_scc_containers()
        running = sum(1 for c in containers if "Up" in c.status)
        total = len(containers)
        items.append(
            ListItem(
                value="containers",
                label="Containers",
                description=f"{running} running, {total} total",
            )
        )
    except Exception:
        items.append(
            ListItem(
                value="containers",
                label="Containers",
                description="Unable to query Docker",
            )
        )

    # Load session count
    try:
        recent_sessions = sessions.list_recent(limit=100)
        session_count = len(recent_sessions)
        items.append(
            ListItem(
                value="sessions",
                label="Sessions",
                description=f"{session_count} recorded",
            )
        )
    except Exception:
        items.append(
            ListItem(
                value="sessions",
                label="Sessions",
                description="Error loading sessions",
            )
        )

    return TabData(
        tab=DashboardTab.STATUS,
        title="Status",
        items=items,
        count_active=len(items),
        count_total=len(items),
    )


def _load_containers_tab_data() -> TabData:
    """Load Containers tab data showing SCC-managed containers.

    Returns:
        TabData with container list items.
    """
    from ..docker import core as docker_core

    items: list[ListItem[str]] = []

    try:
        containers = docker_core.list_scc_containers()
        running_count = 0

        for container in containers:
            is_running = "Up" in container.status
            if is_running:
                running_count += 1

            # Build description from available info
            desc_parts = []
            if container.profile:
                desc_parts.append(container.profile)
            if container.workspace:
                # Show just the workspace name
                workspace_name = container.workspace.split("/")[-1]
                desc_parts.append(workspace_name)
            if container.status:
                # Simplify status (e.g., "Up 2 hours" → "Up 2h")
                status_short = container.status.replace(" hours", "h").replace(" hour", "h")
                status_short = status_short.replace(" minutes", "m").replace(" minute", "m")
                status_short = status_short.replace(" days", "d").replace(" day", "d")
                desc_parts.append(status_short)

            items.append(
                ListItem(
                    value=container.id,
                    label=container.name,
                    description="  ".join(desc_parts),
                )
            )

        if not items:
            items.append(
                ListItem(
                    value="no_containers",
                    label="No containers",
                    description="Run 'scc start' to create one",
                )
            )

        return TabData(
            tab=DashboardTab.CONTAINERS,
            title="Containers",
            items=items,
            count_active=running_count,
            count_total=len(containers),
        )

    except Exception:
        return TabData(
            tab=DashboardTab.CONTAINERS,
            title="Containers",
            items=[
                ListItem(
                    value="error",
                    label="Error",
                    description="Unable to query Docker",
                )
            ],
            count_active=0,
            count_total=0,
        )


def _load_sessions_tab_data() -> TabData:
    """Load Sessions tab data showing recent Claude sessions.

    Returns:
        TabData with session list items.
    """
    from .. import sessions

    items: list[ListItem[str]] = []

    try:
        recent = sessions.list_recent(limit=20)

        for session in recent:
            name = session.get("name", "Unnamed")
            desc_parts = []

            if session.get("team"):
                desc_parts.append(str(session["team"]))
            if session.get("branch"):
                desc_parts.append(str(session["branch"]))
            if session.get("last_used"):
                desc_parts.append(str(session["last_used"]))

            items.append(
                ListItem(
                    value=session.get("container_name", name),
                    label=name,
                    description="  ".join(desc_parts),
                )
            )

        if not items:
            items.append(
                ListItem(
                    value="no_sessions",
                    label="No sessions",
                    description="Start a session with 'scc start'",
                )
            )

        return TabData(
            tab=DashboardTab.SESSIONS,
            title="Sessions",
            items=items,
            count_active=len(recent),
            count_total=len(recent),
        )

    except Exception:
        return TabData(
            tab=DashboardTab.SESSIONS,
            title="Sessions",
            items=[
                ListItem(
                    value="error",
                    label="Error",
                    description="Unable to load sessions",
                )
            ],
            count_active=0,
            count_total=0,
        )


def _load_worktrees_tab_data() -> TabData:
    """Load Worktrees tab data showing git worktrees.

    Worktrees are loaded from the current working directory if it's a git repo.

    Returns:
        TabData with worktree list items.
    """
    import os
    from pathlib import Path

    from .. import git

    items: list[ListItem[str]] = []

    try:
        cwd = Path(os.getcwd())
        worktrees = git.list_worktrees(cwd)
        current_count = 0

        for wt in worktrees:
            if wt.is_current:
                current_count += 1

            desc_parts = []
            if wt.branch:
                desc_parts.append(wt.branch)
            if wt.has_changes:
                desc_parts.append("*modified")
            if wt.is_current:
                desc_parts.append("(current)")

            items.append(
                ListItem(
                    value=wt.path,
                    label=Path(wt.path).name,
                    description="  ".join(desc_parts),
                )
            )

        if not items:
            items.append(
                ListItem(
                    value="no_worktrees",
                    label="No worktrees",
                    description="Not in a git repository",
                )
            )

        return TabData(
            tab=DashboardTab.WORKTREES,
            title="Worktrees",
            items=items,
            count_active=current_count,
            count_total=len(worktrees),
        )

    except Exception:
        return TabData(
            tab=DashboardTab.WORKTREES,
            title="Worktrees",
            items=[
                ListItem(
                    value="no_git",
                    label="Not available",
                    description="Not in a git repository",
                )
            ],
            count_active=0,
            count_total=0,
        )


def _load_all_tab_data() -> dict[DashboardTab, TabData]:
    """Load data for all dashboard tabs.

    Returns:
        Dictionary mapping each tab to its data.
    """
    return {
        DashboardTab.STATUS: _load_status_tab_data(),
        DashboardTab.CONTAINERS: _load_containers_tab_data(),
        DashboardTab.SESSIONS: _load_sessions_tab_data(),
        DashboardTab.WORKTREES: _load_worktrees_tab_data(),
    }


def run_dashboard() -> None:
    """Run the main SCC dashboard.

    This is the entry point for `scc` with no arguments in a TTY.
    It loads current resource data and displays the interactive dashboard.

    Handles TeamSwitchRequested by showing team picker and reloading.
    """
    while True:
        # Load real data for all tabs
        tabs = _load_all_tab_data()

        state = DashboardState(
            active_tab=DashboardTab.STATUS,
            tabs=tabs,
            list_state=ListState(items=tabs[DashboardTab.STATUS].items),
        )

        dashboard = Dashboard(state)
        try:
            dashboard.run()
            break  # Normal exit (q or Esc)
        except TeamSwitchRequested:
            # User pressed 't' - show team picker then reload dashboard
            _handle_team_switch()
            # Loop continues to reload dashboard with new team


def _handle_team_switch() -> None:
    """Handle team switch request from dashboard.

    Shows the team picker and switches team if user selects one.
    """
    from .. import config, teams
    from .picker import pick_team

    console = Console()
    console.print()  # Clear line after dashboard

    try:
        # Load config and org config for team list
        cfg = config.load_user_config()
        org_config = config.load_cached_org_config()

        available_teams = teams.list_teams(cfg, org_config=org_config)
        if not available_teams:
            console.print("[yellow]No teams available[/yellow]")
            return

        # Get current team for marking
        current_team = cfg.get("selected_profile")

        selected = pick_team(
            available_teams,
            current_team=str(current_team) if current_team else None,
            title="Switch Team",
        )

        if selected:
            # Update team selection
            team_name = selected.get("name", "")
            cfg["selected_profile"] = team_name
            config.save_user_config(cfg)
            console.print(f"[green]Switched to team: {team_name}[/green]")
        # If cancelled, just return to dashboard

    except TeamSwitchRequested:
        # Nested team switch (shouldn't happen, but handle gracefully)
        pass
    except Exception as e:
        console.print(f"[red]Error switching team: {e}[/red]")
