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
from typing import Any

from rich.console import Console, Group, RenderableType
from rich.live import Live
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

# Import config for standalone mode detection
from .. import config as scc_config
from .chrome import Chrome, ChromeConfig, FooterHint
from .keys import (
    Action,
    ActionType,
    KeyReader,
    RefreshRequested,
    StartRequested,
    TeamSwitchRequested,
)
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
        items: List items to display in this tab. Value type varies by tab:
            - Containers/Worktrees: str (container ID or worktree name)
            - Sessions: dict[str, Any] (full session data for details pane)
        count_active: Number of active items (e.g., running containers).
        count_total: Total number of items.
    """

    tab: DashboardTab
    title: str
    items: Sequence[ListItem[Any]]
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
        status_message: Transient message to display (cleared on next action).
        details_open: Whether the details pane is visible.
    """

    active_tab: DashboardTab
    tabs: dict[DashboardTab, TabData]
    list_state: ListState[str]
    status_message: str | None = None
    details_open: bool = False

    @property
    def current_tab_data(self) -> TabData:
        """Get data for the currently active tab."""
        return self.tabs[self.active_tab]

    def is_placeholder_selected(self) -> bool:
        """Check if the current selection is a placeholder row.

        Placeholder rows represent empty states or errors (e.g., "No containers",
        "Error loading sessions") and shouldn't show details.

        Placeholders can be identified by:
        - String value matching known placeholder names (containers, worktrees)
        - Dict value with "_placeholder" key (sessions)

        Returns:
            True if current item is a placeholder, False otherwise.
        """
        current = self.list_state.current_item
        if not current:
            return True  # No item = treat as placeholder

        # Known placeholder string values from tab data loaders
        placeholder_values = {
            "no_containers",
            "no_sessions",
            "no_worktrees",
            "no_git",
            "error",
            "config_error",
        }

        # Check string placeholders (must be string type first - dicts are unhashable)
        if isinstance(current.value, str) and current.value in placeholder_values:
            return True

        # Check dict placeholders (sessions tab uses dicts)
        if isinstance(current.value, dict) and "_placeholder" in current.value:
            return True

        return False

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
        # Track last layout mode for hysteresis (prevents flip-flop at resize boundary)
        self._last_side_by_side: bool | None = None

    def run(self) -> None:
        """Run the interactive dashboard.

        Blocks until the user quits (q or Esc).
        """
        # Use custom_keys for dashboard-specific actions that aren't in DEFAULT_KEY_MAP
        # This allows 'r' to be a filter char in pickers but REFRESH in dashboard
        reader = KeyReader(custom_keys={"r": "refresh"}, enable_filter=True)

        with Live(
            self._render(),
            console=self._console,
            auto_refresh=False,  # Manual refresh for instant response
            transient=True,
        ) as live:
            while True:
                # Pass filter_active based on actual filter state, not always True
                # When filter is empty, j/k navigate; when typing, j/k become filter chars
                action = reader.read(filter_active=bool(self.state.list_state.filter_query))

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
        """
        list_body = self._render_list_body()
        config = self._get_chrome_config()
        chrome = Chrome(config)

        # Check if details should be shown (render rule: not on Status tab)
        show_details = self.state.details_open and self.state.active_tab != DashboardTab.STATUS

        body: RenderableType = list_body
        if show_details and not self.state.is_placeholder_selected():
            # Render details pane content
            details = self._render_details_pane()

            # Responsive layout with hysteresis to prevent flip-flop at resize boundary
            # Thresholds: ≥112 → side-by-side, ≤108 → stacked, 109-111 → maintain previous
            terminal_width = self._console.size.width
            if terminal_width >= 112:
                side_by_side = True
            elif terminal_width <= 108:
                side_by_side = False
            elif self._last_side_by_side is not None:
                # In dead zone (109-111): maintain previous layout
                side_by_side = self._last_side_by_side
            else:
                # First render in dead zone: default to stacked (conservative)
                side_by_side = False

            self._last_side_by_side = side_by_side
            body = self._render_split_view(list_body, details, side_by_side=side_by_side)

        return chrome.render(body, search_query=self.state.list_state.filter_query)

    def _render_list_body(self) -> Text:
        """Render the list content for the active tab."""
        text = Text()
        filtered = self.state.list_state.filtered_items
        visible = self.state.list_state.visible_items

        if not filtered:
            text.append("No items", style="dim italic")
        else:
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

        # Render status message if present (transient toast)
        if self.state.status_message:
            text.append("\n")
            text.append("ℹ ", style="yellow")
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
        # Wrap details in consistent padding for visual balance
        padded_details = Padding(details, (0, 0, 0, 1))  # Left padding

        if side_by_side:
            # Use Table.grid for side-by-side with vertical separator
            # Table handles row height automatically (no fixed separator height)
            table = Table.grid(expand=True, padding=(0, 1))
            table.add_column("list", ratio=1, no_wrap=False)
            table.add_column("sep", width=1, style="dim", justify="center")
            table.add_column("details", ratio=1, no_wrap=False)

            # Single vertical bar - Rich expands it to match row height
            table.add_row(list_body, "│", padded_details)
            return table
        else:
            # Stacked: list above details with thin separator
            # Use same visual weight as side-by-side for smooth switching
            separator = Text("─" * 30, style="dim")
            return Group(
                list_body,
                Text(""),  # Blank line for spacing
                separator,
                Text(""),  # Blank line for spacing
                padded_details,
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

    def _render_container_details(self, item: ListItem[Any]) -> RenderableType:
        """Render details for a container item using structured key/value table."""
        # Header
        header = Text()
        header.append("Container Details\n", style="bold cyan")
        header.append("─" * 20, style="dim")

        # Key/value table
        table = Table.grid(padding=(0, 1))
        table.add_column("key", style="dim", width=10)
        table.add_column("value")

        table.add_row("Name", Text(item.label, style="bold"))

        # Short container ID
        container_id = item.value[:12] if len(item.value) > 12 else item.value
        table.add_row("ID", container_id)

        # Parse description into fields if available
        if item.description:
            parts = item.description.split("  ")
            if len(parts) >= 1 and parts[0]:
                table.add_row("Profile", parts[0])
            if len(parts) >= 2 and parts[1]:
                table.add_row("Workspace", parts[1])
            if len(parts) >= 3 and parts[2]:
                table.add_row("Status", parts[2])

        # Commands section
        commands = Text()
        commands.append("\nCommands\n", style="dim")
        commands.append(f"  docker exec -it {item.label} bash\n", style="cyan")

        return Group(header, table, commands)

    def _render_session_details(self, item: ListItem[Any]) -> RenderableType:
        """Render details for a session item using structured key/value table.

        Uses the raw session dict stored in item.value for field access.
        """
        session = item.value

        # Header
        header = Text()
        header.append("Session Details\n", style="bold cyan")
        header.append("─" * 20, style="dim")

        # Key/value table
        table = Table.grid(padding=(0, 1))
        table.add_column("key", style="dim", width=10)
        table.add_column("value")

        table.add_row("Name", Text(item.label, style="bold"))

        # Read fields directly from session dict (with None protection)
        if session.get("team"):
            table.add_row("Team", str(session["team"]))
        if session.get("branch"):
            table.add_row("Branch", str(session["branch"]))
        if session.get("workspace"):
            table.add_row("Workspace", str(session["workspace"]))
        if session.get("last_used"):
            table.add_row("Last Used", str(session["last_used"]))

        # Commands section with None protection and helpful tips
        commands = Text()
        commands.append("\nCommands\n", style="dim")

        container_name = session.get("container_name")
        session_id = session.get("id")

        if container_name:
            # Container is available - show resume command
            commands.append(f"  scc resume {container_name}\n", style="cyan")
        elif session_id:
            # Session exists but container stopped - show restart tip
            commands.append("  Container stopped. Start new session:\n", style="dim italic")
            commands.append(
                f"  scc start --workspace {session.get('workspace', '.')}\n", style="cyan"
            )
        else:
            # Minimal session info - generic tip
            commands.append("  Start session: scc start\n", style="cyan dim")

        return Group(header, table, commands)

    def _render_worktree_details(self, item: ListItem[Any]) -> RenderableType:
        """Render details for a worktree item using structured key/value table."""
        # Header
        header = Text()
        header.append("Worktree Details\n", style="bold cyan")
        header.append("─" * 20, style="dim")

        # Key/value table
        table = Table.grid(padding=(0, 1))
        table.add_column("key", style="dim", width=10)
        table.add_column("value")

        table.add_row("Name", Text(item.label, style="bold"))
        table.add_row("Path", item.value)

        # Parse description into fields (branch  *modified  (current))
        if item.description:
            parts = item.description.split("  ")
            for part in parts:
                if part.startswith("(") and part.endswith(")"):
                    table.add_row("Status", Text(part, style="green"))
                elif part == "*modified":
                    table.add_row("Changes", Text("Modified", style="yellow"))
                elif part:
                    table.add_row("Branch", part)

        # Commands section
        commands = Text()
        commands.append("\nCommands\n", style="dim")
        commands.append(f"  scc start {item.value}\n", style="cyan")

        return Group(header, table, commands)

    def _get_placeholder_tip(self, value: str | dict[str, Any]) -> str:
        """Get contextual help tip for placeholder items.

        Returns actionable guidance for empty/error states.

        Args:
            value: Either a string placeholder key or a dict with "_placeholder" key.
        """
        tips: dict[str, str] = {
            # Container placeholders
            "no_containers": "No containers running. Run `scc start <path>` to launch one.",
            # Session placeholders
            "no_sessions": "No sessions recorded yet. Run `scc start` to create your first.",
            # Worktree placeholders
            "no_worktrees": "Not in a git repository. Navigate to a git repo to see worktrees.",
            "no_git": "Not in a git repository. Run `git init` or clone a repo first.",
            # Error placeholders
            "error": "Unable to load data. Check Docker is running and try again.",
            "config_error": "Configuration error. Run `scc doctor` to diagnose.",
        }

        # Extract placeholder key from dict if needed
        placeholder_key = value
        if isinstance(value, dict):
            placeholder_key = value.get("_placeholder", "")

        return tips.get(str(placeholder_key), "No details available for this item.")

    def _compute_footer_hints(self, standalone: bool, show_details: bool) -> tuple[FooterHint, ...]:
        """Compute context-aware footer hints based on current state.

        Hints reflect available actions for the current selection:
        - Details open: "Esc close"
        - Status tab: No Enter action (info-only)
        - Startable placeholder: "Enter start"
        - Non-startable placeholder: No Enter hint
        - Real item: "Enter details"

        Args:
            standalone: Whether running in standalone mode (dims team hint).
            show_details: Whether the details pane is currently showing.

        Returns:
            Tuple of FooterHint objects for the chrome footer.
        """
        hints: list[FooterHint] = [FooterHint("↑↓", "navigate")]

        # Determine primary action hint based on context
        if show_details:
            # Details pane is open - show close action
            hints.append(FooterHint("Esc", "close"))
        elif self.state.active_tab == DashboardTab.STATUS:
            # Status tab has no actionable items - no Enter hint
            pass
        elif self.state.is_placeholder_selected():
            # Check if placeholder is startable
            current = self.state.list_state.current_item
            is_startable = False
            if current:
                if isinstance(current.value, str):
                    is_startable = current.value in {"no_containers", "no_sessions"}
                elif isinstance(current.value, dict):
                    is_startable = current.value.get("_startable", False)

            if is_startable:
                hints.append(FooterHint("Enter", "start"))
            # Non-startable placeholders get no Enter hint
        else:
            # Real item selected - show details action
            hints.append(FooterHint("Enter", "details"))

        # Tab navigation and refresh
        hints.append(FooterHint("Tab", "switch tab"))
        hints.append(FooterHint("r", "refresh"))

        # Global actions
        hints.append(FooterHint("t", "teams", dimmed=standalone))
        hints.append(FooterHint("q", "quit"))
        hints.append(FooterHint("?", "help"))

        return tuple(hints)

    def _get_chrome_config(self) -> ChromeConfig:
        """Get chrome configuration for current state."""
        tab_names = [tab.display_name for tab in _TAB_ORDER]
        active_index = _TAB_ORDER.index(self.state.active_tab)
        standalone = scc_config.is_standalone_mode()

        # Render rule: auto-hide details on Status tab (no state mutation)
        show_details = self.state.details_open and self.state.active_tab != DashboardTab.STATUS

        # Compute dynamic footer hints based on current context
        footer_hints = self._compute_footer_hints(standalone, show_details)

        return ChromeConfig.for_dashboard(
            tab_names,
            active_index,
            standalone=standalone,
            details_open=show_details,
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
                if action.filter_char:
                    self.state.list_state.add_filter_char(action.filter_char)

            case ActionType.FILTER_DELETE:
                self.state.list_state.delete_filter_char()

            case ActionType.CANCEL:
                # ESC precedence: details → filter → no-op
                if self.state.details_open:
                    self.state.details_open = False
                    return True  # Refresh to hide details
                if self.state.list_state.filter_query:
                    self.state.list_state.clear_filter()
                    return True  # Refresh to show unfiltered list
                return None  # No-op

            case ActionType.QUIT:
                return False

            case ActionType.SELECT:
                # On Status tab, Enter triggers different actions based on item
                if self.state.active_tab == DashboardTab.STATUS:
                    current = self.state.list_state.current_item
                    if current:
                        # Team row: same behavior as 't' key
                        if current.value == "team":
                            if scc_config.is_standalone_mode():
                                self.state.status_message = (
                                    "Teams require org mode. Run `scc setup` to configure."
                                )
                                return True  # Refresh to show message
                            raise TeamSwitchRequested()

                        # Resource rows: drill down to corresponding tab
                        tab_mapping: dict[str, DashboardTab] = {
                            "containers": DashboardTab.CONTAINERS,
                            "sessions": DashboardTab.SESSIONS,
                            "worktrees": DashboardTab.WORKTREES,
                        }
                        target_tab = tab_mapping.get(current.value)
                        if target_tab:
                            # Clear filter on drill-down (avoids confusion)
                            self.state.list_state.clear_filter()
                            self.state = self.state.switch_tab(target_tab)
                            return True  # Refresh to show new tab
                else:
                    # Resource tabs: toggle details pane
                    if self.state.details_open:
                        # Close details
                        self.state.details_open = False
                        return True
                    elif not self.state.is_placeholder_selected():
                        # Open details (only for real items, not placeholders)
                        self.state.details_open = True
                        return True
                    else:
                        # Placeholder or empty state: handle appropriately
                        current = self.state.list_state.current_item
                        if current:
                            # Check if this is a startable placeholder
                            # (containers/sessions empty → user can start a new session)
                            is_startable = False
                            reason = ""

                            # String placeholders (containers, worktrees)
                            if isinstance(current.value, str):
                                startable_strings = {"no_containers", "no_sessions"}
                                if current.value in startable_strings:
                                    is_startable = True
                                    reason = current.value

                            # Dict placeholders (sessions tab uses dicts)
                            elif isinstance(current.value, dict):
                                if current.value.get("_startable"):
                                    is_startable = True
                                    reason = current.value.get("_placeholder", "unknown")

                            if is_startable:
                                # Uses .name (stable identifier) not .value (display string)
                                raise StartRequested(
                                    return_to=self.state.active_tab.name,
                                    reason=reason,
                                )
                            else:
                                # Non-startable placeholders show a tip
                                self.state.status_message = self._get_placeholder_tip(current.value)
                        elif self.state.list_state.filter_query:
                            # Filter has no matches
                            self.state.status_message = (
                                f"No matches for '{self.state.list_state.filter_query}'. "
                                "Press Esc to clear filter."
                            )
                        else:
                            # Truly empty list (shouldn't happen normally)
                            self.state.status_message = "No items available."
                        return True

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
                # Show dashboard-specific help overlay
                from .help import HelpMode, show_help_overlay

                show_help_overlay(HelpMode.DASHBOARD, self._console)

            case ActionType.CUSTOM:
                # Handle dashboard-specific custom keys (not in DEFAULT_KEY_MAP)
                if action.custom_key == "r":
                    # User pressed 'r' - signal orchestrator to reload tab data
                    # Uses .name (stable identifier) not .value (display string)
                    raise RefreshRequested(return_to=self.state.active_tab.name)

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
        TabData with session list items. Each ListItem.value contains
        the raw session dict for access in the details pane.
    """
    from .. import sessions

    items: list[ListItem[dict[str, Any]]] = []

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

            # Store full session dict for details pane access
            items.append(
                ListItem(
                    value=session,
                    label=name,
                    description="  ".join(desc_parts),
                )
            )

        if not items:
            # Placeholder with sentinel dict (startable: True enables Enter action)
            items.append(
                ListItem(
                    value={"_placeholder": "no_sessions", "_startable": True},
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

    Handles intent exceptions by executing the requested flow outside the
    Rich Live context (critical to avoid nested Live conflicts), then
    reloading the dashboard with restored tab state.

    Intent Exceptions:
        - TeamSwitchRequested: Show team picker, reload with new team
        - StartRequested: Run start wizard, return to source tab with fresh data
        - RefreshRequested: Reload tab data, return to source tab
    """
    # Track which tab to restore after flow (uses .name for stability)
    restore_tab: str | None = None
    # Toast message to show on next dashboard iteration (e.g., "Start cancelled")
    toast_message: str | None = None

    while True:
        # Load real data for all tabs
        tabs = _load_all_tab_data()

        # Determine initial tab (restore previous or default to STATUS)
        initial_tab = DashboardTab.STATUS
        if restore_tab:
            # Find tab by name (stable identifier)
            for tab in DashboardTab:
                if tab.name == restore_tab:
                    initial_tab = tab
                    break
            restore_tab = None  # Clear after use

        state = DashboardState(
            active_tab=initial_tab,
            tabs=tabs,
            list_state=ListState(items=tabs[initial_tab].items),
            status_message=toast_message,  # Show any pending toast
        )
        toast_message = None  # Clear after use

        dashboard = Dashboard(state)
        try:
            dashboard.run()
            break  # Normal exit (q or Esc)
        except TeamSwitchRequested:
            # User pressed 't' - show team picker then reload dashboard
            _handle_team_switch()
            # Loop continues to reload dashboard with new team

        except StartRequested as start_req:
            # User pressed Enter on startable placeholder
            # Execute start flow OUTSIDE Rich Live (critical: avoids nested Live)
            restore_tab = start_req.return_to
            completed = _handle_start_flow(start_req.reason)
            if not completed:
                # User cancelled the wizard - show toast on dashboard reload
                toast_message = "Start cancelled"
            # Loop continues to reload dashboard with fresh data

        except RefreshRequested as refresh_req:
            # User pressed 'r' - just reload data
            restore_tab = refresh_req.return_to
            # Loop continues with fresh data (no additional action needed)


def _prepare_for_nested_ui(console: Console) -> None:
    """Prepare terminal state for launching nested UI components.

    Restores cursor visibility, ensures clean newline, and flushes
    any buffered input to prevent ghost keypresses from Rich Live context.

    This should be called before launching any interactive picker or wizard
    from the dashboard to ensure clean terminal state.

    Args:
        console: Rich Console instance for terminal operations.
    """
    import io
    import sys
    import termios

    # Restore cursor (Rich Live may hide it)
    console.show_cursor(True)
    console.print()  # Ensure clean newline

    # Flush buffered input (best-effort)
    try:
        termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
    except (termios.error, OSError, ValueError, TypeError, io.UnsupportedOperation):
        pass  # Non-Unix, redirected stdin, or mock - safe to ignore


def _handle_team_switch() -> None:
    """Handle team switch request from dashboard.

    Shows the team picker and switches team if user selects one.
    """
    from .. import config, teams
    from .picker import pick_team

    console = Console()
    _prepare_for_nested_ui(console)

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


def _handle_start_flow(reason: str) -> bool:
    """Handle start flow request from dashboard.

    Runs the interactive start wizard and launches a sandbox if user completes it.
    Executes OUTSIDE Rich Live context (the dashboard has already exited
    via the exception unwind before this is called).

    Args:
        reason: Why the start flow was triggered (e.g., "no_containers", "no_sessions").
            Used for logging/analytics and to determine skip_quick_resume.

    Returns:
        True if wizard completed successfully, False if cancelled.
    """
    from ..cli_launch import run_start_wizard_flow

    console = Console()
    _prepare_for_nested_ui(console)

    # For empty-state starts, skip Quick Resume (user intent is "create new")
    skip_quick_resume = reason in ("no_containers", "no_sessions")

    # Show contextual message based on reason
    if reason == "no_containers":
        console.print("[dim]Starting a new session...[/dim]")
    elif reason == "no_sessions":
        console.print("[dim]Starting your first session...[/dim]")
    console.print()

    # Run the wizard (handles its own errors internally)
    return run_start_wizard_flow(skip_quick_resume=skip_quick_resume)
