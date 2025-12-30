"""Core navigation engine for interactive list-based UI.

This module provides the ListScreen component - the heart of the interactive
UI system. It handles:
- State management (cursor, scroll, filter, selection)
- Key handling (using the keys module)
- Rendering (using the chrome module)
- Event loop (blocking key reads → state updates → re-render)

The design is mode-agnostic: SINGLE_SELECT, MULTI_SELECT, and ACTIONABLE
modes use the same engine with different handlers for actions.

Example:
    >>> items = [ListItem(value=t, label=t.name) for t in teams]
    >>> screen = ListScreen(items, title="Select Team")
    >>> selected = screen.run()  # Blocking until selection or cancel
    >>> if selected:
    ...     print(f"Selected: {selected.value}")
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Generic, TypeVar

from rich.console import RenderableType
from rich.live import Live
from rich.text import Text

from scc_cli.theme import Indicators

from .chrome import Chrome, ChromeConfig
from .keys import Action, ActionType, KeyReader, TeamSwitchRequested

if TYPE_CHECKING:
    pass

T = TypeVar("T")


class ListMode(Enum):
    """Operating mode for ListScreen.

    Determines how the screen handles selection and confirmation.
    """

    SINGLE_SELECT = auto()  # Enter returns single item
    MULTI_SELECT = auto()  # Space toggles, Enter returns list
    ACTIONABLE = auto()  # Action keys dispatch callbacks


@dataclass
class ListItem(Generic[T]):
    """Wrapper for items in a list with display metadata.

    Attributes:
        value: The underlying value (domain object).
        label: Primary display text.
        description: Secondary text (optional).
        metadata: Additional key-value pairs for display.
        governance_status: "blocked", "warning", or None.
    """

    value: T
    label: str
    description: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    governance_status: str | None = None


@dataclass
class ListState(Generic[T]):
    """Mutable state for ListScreen navigation and selection.

    Attributes:
        items: All items in the list.
        cursor: Current cursor position (in filtered items).
        scroll_offset: Scroll position for viewport.
        filter_query: Current type-to-filter query.
        selected: Set of selected indices (for multi-select).
        viewport_height: Max items visible at once.
    """

    items: Sequence[ListItem[T]]
    cursor: int = 0
    scroll_offset: int = 0
    filter_query: str = ""
    selected: set[int] = field(default_factory=set)
    viewport_height: int = 10

    @property
    def filtered_items(self) -> list[ListItem[T]]:
        """Items matching the current filter query."""
        if not self.filter_query:
            return list(self.items)
        query = self.filter_query.lower()
        return [
            item
            for item in self.items
            if query in item.label.lower() or query in item.description.lower()
        ]

    @property
    def visible_items(self) -> list[ListItem[T]]:
        """Items visible in the current viewport."""
        filtered = self.filtered_items
        end = min(self.scroll_offset + self.viewport_height, len(filtered))
        return filtered[self.scroll_offset : end]

    @property
    def current_item(self) -> ListItem[T] | None:
        """Item at cursor position, or None if list empty."""
        filtered = self.filtered_items
        if 0 <= self.cursor < len(filtered):
            return filtered[self.cursor]
        return None

    def move_cursor(self, delta: int) -> bool:
        """Move cursor by delta, clamping to valid range.

        Returns True if cursor position changed.
        """
        filtered = self.filtered_items
        if not filtered:
            return False

        old_cursor = self.cursor
        self.cursor = max(0, min(len(filtered) - 1, self.cursor + delta))

        # Adjust scroll to keep cursor visible
        if self.cursor < self.scroll_offset:
            self.scroll_offset = self.cursor
        elif self.cursor >= self.scroll_offset + self.viewport_height:
            self.scroll_offset = self.cursor - self.viewport_height + 1

        return self.cursor != old_cursor

    def toggle_selection(self) -> bool:
        """Toggle selection state of current item."""
        if self.current_item is None:
            return False

        if self.cursor in self.selected:
            self.selected.discard(self.cursor)
        else:
            self.selected.add(self.cursor)
        return True

    def toggle_all(self) -> bool:
        """Toggle all items selected/deselected."""
        filtered = self.filtered_items
        if not filtered:
            return False

        all_selected = len(self.selected) == len(filtered)
        if all_selected:
            self.selected.clear()
        else:
            self.selected = set(range(len(filtered)))
        return True

    def add_filter_char(self, char: str) -> bool:
        """Add character to filter query."""
        self.filter_query += char
        # Reset cursor and selection when filter changes
        # Selection indices become stale when filtered list shrinks
        self.cursor = 0
        self.scroll_offset = 0
        self.selected.clear()
        return True

    def delete_filter_char(self) -> bool:
        """Remove last character from filter query."""
        if not self.filter_query:
            return False
        self.filter_query = self.filter_query[:-1]
        # Reset cursor and selection when filter changes
        # Selection indices become stale when filtered list changes
        self.cursor = 0
        self.scroll_offset = 0
        self.selected.clear()
        return True

    def clear_filter(self) -> bool:
        """Clear the entire filter query.

        Returns True if filter was cleared, False if already empty.
        """
        if not self.filter_query:
            return False
        self.filter_query = ""
        # Reset cursor and selection when filter changes
        # Selection indices become stale when filtered list changes
        self.cursor = 0
        self.scroll_offset = 0
        self.selected.clear()
        return True


class ListScreen(Generic[T]):
    """Core navigation engine for list-based UI.

    ListScreen combines state management, key handling, and rendering
    into a cohesive event loop that blocks for user input and returns
    the selected value(s).

    Attributes:
        state: Current list state.
        mode: Operating mode (SINGLE_SELECT, MULTI_SELECT, ACTIONABLE).
        title: Display title for the chrome.
        custom_actions: Custom key handlers for ACTIONABLE mode.
    """

    def __init__(
        self,
        items: Sequence[ListItem[T]],
        *,
        title: str = "Select",
        mode: ListMode = ListMode.SINGLE_SELECT,
        custom_actions: dict[str, Callable[[ListItem[T]], None]] | None = None,
        viewport_height: int = 10,
    ) -> None:
        """Initialize the list screen.

        Args:
            items: Items to display in the list.
            title: Title for the chrome header.
            mode: Operating mode for selection behavior.
            custom_actions: Key → handler map for ACTIONABLE mode.
            viewport_height: Max items visible at once.
        """
        self.state = ListState(items=items, viewport_height=viewport_height)
        self.mode = mode
        self.title = title
        self.custom_actions = custom_actions or {}
        from ..console import get_err_console

        self._console = get_err_console()

    def run(self) -> T | list[T] | None:
        """Run the interactive list screen.

        Blocks until the user makes a selection or cancels.

        Returns:
            - SINGLE_SELECT: The selected item's value, or None if cancelled.
            - MULTI_SELECT: List of selected values, or None if cancelled.
            - ACTIONABLE: None (actions handled via callbacks).
        """
        # Set up key reader with custom keys if in actionable mode
        custom_keys = {k: k for k in self.custom_actions} if self.custom_actions else None
        reader = KeyReader(custom_keys=custom_keys, enable_filter=True)

        # Use Rich Live for efficient updates
        with Live(
            self._render(),
            console=self._console,
            auto_refresh=False,  # Manual refresh for instant response
            transient=True,  # Clear on exit
        ) as live:
            while True:
                action = reader.read(filter_active=bool(self.state.filter_query))

                # Handle action based on type
                result = self._handle_action(action)

                if result is not None:
                    return result

                if action.should_exit:
                    return None

                # Re-render if state changed
                if action.state_changed:
                    live.update(self._render(), refresh=True)

    def _render(self) -> RenderableType:
        """Render the current state to a Rich renderable."""
        # Build the list body
        body = self._render_list_body()

        # Get appropriate chrome config
        config = self._get_chrome_config()

        # Render with chrome
        chrome = Chrome(config)
        return chrome.render(body, search_query=self.state.filter_query)

    def _render_list_body(self) -> Text:
        """Render the list items."""
        text = Text()
        filtered = self.state.filtered_items
        visible = self.state.visible_items

        if not filtered:
            text.append("No matches found", style="dim italic")
            if self.state.filter_query:
                text.append(" — ", style="dim")
                text.append("Backspace", style="cyan")
                text.append(" to edit filter", style="dim")
            return text

        for i, item in enumerate(visible):
            # Calculate actual index in filtered list
            actual_index = self.state.scroll_offset + i
            is_cursor = actual_index == self.state.cursor
            is_selected = actual_index in self.state.selected

            # Build line with cursor indicator
            if is_cursor:
                text.append(f"{Indicators.get('CURSOR')} ", style="cyan bold")
            else:
                text.append("  ")

            # Selection checkbox for multi-select
            if self.mode == ListMode.MULTI_SELECT:
                if is_selected:
                    text.append(f"[{Indicators.get('PASS')}] ", style="green")
                else:
                    text.append("[ ] ", style="dim")

            # Governance indicator
            if item.governance_status == "blocked":
                text.append("⛔ ", style="red")
            elif item.governance_status == "warning":
                text.append("⚠️  ", style="yellow")

            # Label and description
            label_style = "bold" if is_cursor else ""
            text.append(item.label, style=label_style)

            if item.description:
                text.append(f"  {item.description}", style="dim")

            # Metadata badges
            if item.metadata:
                for key, value in item.metadata.items():
                    if value:  # Only show non-empty values
                        text.append(f" [{value}]", style="cyan dim")

            text.append("\n")

        # Scroll indicators
        if self.state.scroll_offset > 0:
            text.append(f"{Indicators.get('SCROLL_UP')} more above\n", style="dim")
        if self.state.scroll_offset + self.state.viewport_height < len(filtered):
            text.append(f"{Indicators.get('SCROLL_DOWN')} more below\n", style="dim")

        return text

    def _get_chrome_config(self) -> ChromeConfig:
        """Get the appropriate chrome config for current mode."""
        filtered_count = len(self.state.filtered_items)

        if self.mode == ListMode.MULTI_SELECT:
            return ChromeConfig.for_multi_select(
                self.title,
                len(self.state.selected),
                filtered_count,
            )
        # SINGLE_SELECT and ACTIONABLE use picker style
        return ChromeConfig.for_picker(self.title, item_count=filtered_count)

    def _handle_action(self, action: Action[Any]) -> T | list[T] | None:
        """Handle an action and return result if selection complete."""
        match action.action_type:
            case ActionType.NAVIGATE_UP:
                self.state.move_cursor(-1)

            case ActionType.NAVIGATE_DOWN:
                self.state.move_cursor(1)

            case ActionType.SELECT:
                if self.mode == ListMode.SINGLE_SELECT:
                    item = self.state.current_item
                    if item:
                        return item.value
                elif self.mode == ListMode.MULTI_SELECT:
                    # In MULTI_SELECT, Enter confirms selection (same as CONFIRM)
                    # This prevents should_exit from returning None as "cancelled"
                    filtered = self.state.filtered_items
                    selected_indices = self.state.selected & set(range(len(filtered)))
                    return [filtered[i].value for i in sorted(selected_indices)]

            case ActionType.TOGGLE:
                if self.mode == ListMode.MULTI_SELECT:
                    self.state.toggle_selection()

            case ActionType.TOGGLE_ALL:
                if self.mode == ListMode.MULTI_SELECT:
                    self.state.toggle_all()

            case ActionType.CONFIRM:
                if self.mode == ListMode.MULTI_SELECT:
                    # Return all selected items
                    filtered = self.state.filtered_items
                    return [filtered[i].value for i in sorted(self.state.selected)]

            case ActionType.FILTER_CHAR:
                if action.filter_char:
                    self.state.add_filter_char(action.filter_char)

            case ActionType.FILTER_DELETE:
                self.state.delete_filter_char()

            case ActionType.CUSTOM:
                if action.custom_key and action.custom_key in self.custom_actions:
                    item = self.state.current_item
                    if item:
                        self.custom_actions[action.custom_key](item)

            case ActionType.CANCEL | ActionType.QUIT:
                # Will be handled by should_exit in caller
                pass

            case ActionType.TEAM_SWITCH:
                # Bubble up to orchestrator for consistent team switching
                raise TeamSwitchRequested()

            case ActionType.HELP:
                # Show mode-aware help overlay
                from .help import HelpMode, show_help_overlay

                help_mode = (
                    HelpMode.MULTI_SELECT if self.mode == ListMode.MULTI_SELECT else HelpMode.PICKER
                )
                show_help_overlay(help_mode, self._console)

        return None
