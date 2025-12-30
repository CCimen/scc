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

from typing import Any

from rich.console import Group, RenderableType
from rich.live import Live
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

# Import config for standalone mode detection
from ... import config as scc_config
from ...theme import Indicators
from ..chrome import Chrome, ChromeConfig, FooterHint
from ..keys import (
    Action,
    ActionType,
    KeyReader,
    RefreshRequested,
    SessionResumeRequested,
    StartRequested,
    TeamSwitchRequested,
)
from ..list_screen import ListItem
from .models import TAB_ORDER, DashboardState, DashboardTab


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

    def run(self) -> None:
        """Run the interactive dashboard.

        Blocks until the user quits (q or Esc).
        """
        # Use custom_keys for dashboard-specific actions that aren't in DEFAULT_KEY_MAP
        # This allows 'r' to be a filter char in pickers but REFRESH in dashboard
        # 'n' (new session) is also screen-specific to avoid global key conflicts
        reader = KeyReader(custom_keys={"r": "refresh", "n": "new_session"}, enable_filter=True)

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

            return render_help_content(HelpMode.DASHBOARD)

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
            text.append(f"{Indicators.get('INFO_ICON')} ", style="yellow")
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
            table.add_row(list_body, Indicators.get("VERTICAL_LINE"), padded_details)
            return table
        else:
            # Stacked: list above details with thin separator
            # Use same visual weight as side-by-side for smooth switching
            separator = Text(Indicators.get("HORIZONTAL_LINE") * 30, style="dim")
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
        header.append(Indicators.get("HORIZONTAL_LINE") * 20, style="dim")

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
        header.append(Indicators.get("HORIZONTAL_LINE") * 20, style="dim")

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
        header.append(Indicators.get("HORIZONTAL_LINE") * 20, style="dim")

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
            # Container placeholders (first-time user friendly)
            "no_containers": (
                "No containers running. Press 'n' to start a new session, "
                "or run `scc start <path>` from the terminal."
            ),
            # Session placeholders (first-time user friendly)
            "no_sessions": ("No sessions recorded yet. Press 'n' to create your first session!"),
            # Worktree placeholders
            "no_worktrees": (
                "Not in a git repository. Navigate to a git repo to see worktrees, "
                "or run `git init` to initialize one."
            ),
            "no_git": ("Not in a git repository. Run `git init` or clone a repo first."),
            # Error placeholders (actionable doctor suggestion)
            "error": (
                "Unable to load data. Run `scc doctor` to check Docker status and diagnose issues."
            ),
            "config_error": ("Configuration issue detected. Run `scc doctor` to diagnose and fix."),
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
            # Details pane is open
            if self.state.active_tab == DashboardTab.SESSIONS:
                # Sessions tab: Enter resumes, Esc closes
                hints.append(FooterHint("Enter", "resume"))
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
        tab_names = [tab.display_name for tab in TAB_ORDER]
        active_index = TAB_ORDER.index(self.state.active_tab)
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
                    # Resource tabs handling (Containers, Worktrees, Sessions)
                    current = self.state.list_state.current_item

                    # All resource tabs: toggle details pane on first Enter
                    if self.state.details_open:
                        # Sessions tab: Enter in details pane resumes the session
                        if (
                            self.state.active_tab == DashboardTab.SESSIONS
                            and current
                            and not self.state.is_placeholder_selected()
                            and isinstance(current.value, dict)
                            and not current.value.get("_placeholder")
                        ):
                            raise SessionResumeRequested(
                                session=current.value,
                                return_to=self.state.active_tab.name,
                            )
                        # All tabs (including Sessions without valid session):
                        # Close details
                        self.state.details_open = False
                        return True
                    elif not self.state.is_placeholder_selected():
                        # Open details (only for real items, not placeholders)
                        self.state.details_open = True
                        return True
                    else:
                        # Placeholder or empty state: handle appropriately
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
                # Show help overlay INSIDE the Live context (avoids scroll artifacts)
                # The overlay is rendered in _render() and dismissed on next keypress
                self.state.help_visible = True
                return True  # Refresh to show help overlay

            case ActionType.CUSTOM:
                # Handle dashboard-specific custom keys (not in DEFAULT_KEY_MAP)
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

        return None
