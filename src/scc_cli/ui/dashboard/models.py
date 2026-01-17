"""Data models for the dashboard module.

This module contains the UI data structures used by the dashboard:
- TabData: Content for a single tab
- DashboardState: State management for the dashboard

Dashboard tab identities and view models live in the application layer, keeping
UI models focused on rendering and navigation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from scc_cli.application.dashboard import (
    TAB_ORDER,
    DashboardItem,
    DashboardTab,
    PlaceholderItem,
)

from ..list_screen import ListItem, ListState


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
    items: Sequence[ListItem[DashboardItem]]
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
        help_visible: Whether the help overlay is shown (rendered inside Live).
        filter_mode: Whether filter input is explicitly active.
    """

    active_tab: DashboardTab
    tabs: dict[DashboardTab, TabData]
    list_state: ListState[DashboardItem]
    status_message: str | None = None
    details_open: bool = False
    help_visible: bool = False
    verbose_worktrees: bool = False  # Toggle for worktree status display
    filter_mode: bool = False

    @property
    def current_tab_data(self) -> TabData:
        """Get data for the currently active tab."""
        return self.tabs[self.active_tab]

    def is_placeholder_selected(self) -> bool:
        """Check if the current selection is a placeholder row.

        Placeholder rows represent empty states or errors and shouldn't show details.

        Returns:
            True if current item is a placeholder, False otherwise.
        """
        current = self.list_state.current_item
        if not current:
            return True  # No item = treat as placeholder

        return isinstance(current.value, PlaceholderItem)

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
            verbose_worktrees=self.verbose_worktrees,
            filter_mode=False,
        )

    def next_tab(self) -> DashboardState:
        """Switch to the next tab (wraps around).

        Returns:
            New DashboardState with next tab active.
        """
        current_index = TAB_ORDER.index(self.active_tab)
        next_index = (current_index + 1) % len(TAB_ORDER)
        return self.switch_tab(TAB_ORDER[next_index])

    def prev_tab(self) -> DashboardState:
        """Switch to the previous tab (wraps around).

        Returns:
            New DashboardState with previous tab active.
        """
        current_index = TAB_ORDER.index(self.active_tab)
        prev_index = (current_index - 1) % len(TAB_ORDER)
        return self.switch_tab(TAB_ORDER[prev_index])
