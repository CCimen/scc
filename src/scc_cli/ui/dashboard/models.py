"""Data models for the dashboard module.

This module contains the core data structures used by the dashboard:
- DashboardTab: Enum for available tabs
- TabData: Content for a single tab
- DashboardState: State management for the dashboard

These models are intentionally simple dataclasses with no external dependencies
beyond the UI layer, enabling clean separation and testability.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from ..list_screen import ListItem, ListState


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
TAB_ORDER: tuple[DashboardTab, ...] = (
    DashboardTab.STATUS,
    DashboardTab.CONTAINERS,
    DashboardTab.SESSIONS,
    DashboardTab.WORKTREES,
)


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
        help_visible: Whether the help overlay is shown (rendered inside Live).
    """

    active_tab: DashboardTab
    tabs: dict[DashboardTab, TabData]
    list_state: ListState[str]
    status_message: str | None = None
    details_open: bool = False
    help_visible: bool = False

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
