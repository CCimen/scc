"""Shared chrome layout rendering for interactive UI components.

This module provides the consistent visual wrapper (chrome) around all
list-based UI components. It handles:
- Title and subtitle rendering
- Tab row for dashboard views
- Search/filter query display
- Footer hints with keybindings
- Consistent spacing and styling

The chrome pattern ensures visual consistency across pickers, multi-select
lists, and the dashboard while keeping content rendering separate.

Example:
    >>> config = ChromeConfig.for_picker("Select Team", 5)
    >>> chrome = Chrome(config)
    >>> rendered = chrome.render(body_content, search_query="dev")
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rich.console import Group
from rich.panel import Panel
from rich.text import Text

from ..theme import Borders, Indicators

if TYPE_CHECKING:
    from rich.console import RenderableType


@dataclass(frozen=True)
class FooterHint:
    """Single hint displayed in the footer.

    Attributes:
        key: The key or key combination (e.g., "↑↓", "Enter", "q").
        action: Description of what the key does (e.g., "navigate", "select").
        dimmed: Whether to show this hint as dimmed/disabled (e.g., standalone mode).
    """

    key: str
    action: str
    dimmed: bool = False


@dataclass(frozen=True)
class ChromeConfig:
    """Configuration for the shared chrome layout.

    Use the factory methods for common configurations:
    - for_picker(): Standard single-select picker
    - for_multi_select(): Multi-select list
    - for_dashboard(): Tabbed dashboard view

    Attributes:
        title: Main title displayed at top.
        subtitle: Secondary text (e.g., item count).
        context_label: Current work context (e.g., "team · repo · worktree").
        show_tabs: Whether to display tab row.
        tabs: List of tab names when show_tabs=True.
        active_tab_index: Index of currently active tab.
        show_search: Whether to show search/filter row.
        footer_hints: List of keybinding hints for footer.
    """

    title: str
    subtitle: str = ""
    context_label: str = ""
    show_tabs: bool = False
    tabs: tuple[str, ...] = ()
    active_tab_index: int = 0
    show_search: bool = True
    footer_hints: tuple[FooterHint, ...] = ()

    @classmethod
    def for_picker(
        cls,
        title: str,
        subtitle: str | None = None,
        *,
        item_count: int | None = None,
        standalone: bool = False,
    ) -> ChromeConfig:
        """Create standard config for single-select pickers.

        Args:
            title: Picker title (e.g., "Select Team").
            subtitle: Optional subtitle text. If not provided and item_count is,
                generates "{item_count} available".
            item_count: Deprecated, use subtitle instead. Number of available items.
            standalone: If True, dim the "t teams" hint (not available without org).

        Returns:
            ChromeConfig with standard picker hints.
        """
        if subtitle is None and item_count is not None:
            subtitle = f"{item_count} available"
        return cls(
            title=title,
            subtitle=subtitle or "",
            show_tabs=False,
            show_search=True,
            footer_hints=(
                FooterHint("↑↓", "navigate"),
                FooterHint("Enter", "select"),
                FooterHint("Esc", "back"),
                FooterHint("q", "quit"),
                FooterHint("t", "teams", dimmed=standalone),
            ),
        )

    @classmethod
    def for_multi_select(cls, title: str, selected: int, total: int) -> ChromeConfig:
        """Create standard config for multi-select lists.

        Args:
            title: List title (e.g., "Stop Containers").
            selected: Number of currently selected items.
            total: Total number of items.

        Returns:
            ChromeConfig with multi-select hints.
        """
        return cls(
            title=title,
            subtitle=f"{selected} of {total} selected",
            show_tabs=False,
            show_search=True,
            footer_hints=(
                FooterHint("↑↓", "navigate"),
                FooterHint("Space", "toggle"),
                FooterHint("a", "toggle all"),
                FooterHint("Enter", "confirm"),
                FooterHint("Esc", "back"),
                FooterHint("q", "quit"),
                FooterHint("t", "teams"),
            ),
        )

    @classmethod
    def for_quick_resume(
        cls, title: str, subtitle: str | None = None, *, standalone: bool = False
    ) -> ChromeConfig:
        """Create config for Quick Resume picker with consistent key hints.

        The Quick Resume picker follows the standard TUI key contract:
        - Enter: Resume the selected context
        - n: Explicitly start a new session (skip resume)
        - Esc: Back/dismiss (cancel wizard from this screen)
        - q: Quit app

        Args:
            title: Picker title (typically "Quick Resume").
            subtitle: Optional subtitle (defaults to hint about n/Esc).
            standalone: If True, dim the "t teams" hint (not available without org).

        Returns:
            ChromeConfig with Quick Resume-specific hints.
        """
        return cls(
            title=title,
            subtitle=subtitle or "n for new session · Esc to go back",
            show_tabs=False,
            show_search=True,
            footer_hints=(
                FooterHint("↑↓", "navigate"),
                FooterHint("Enter", "resume"),
                FooterHint("n", "new session"),
                FooterHint("Esc", "back"),
                FooterHint("q", "quit"),
                FooterHint("t", "teams", dimmed=standalone),
            ),
        )

    @classmethod
    def for_dashboard(
        cls,
        tabs: list[str],
        active: int,
        *,
        standalone: bool = False,
        details_open: bool = False,
        custom_hints: tuple[FooterHint, ...] | None = None,
    ) -> ChromeConfig:
        """Create standard config for dashboard view.

        Args:
            tabs: List of tab names.
            active: Index of active tab (0-based).
            standalone: If True, dim the "t teams" hint (not available without org).
            details_open: If True, show "Esc close" instead of "Enter details".
            custom_hints: Optional custom footer hints to override defaults.
                When provided, these hints are used instead of the standard set.

        Returns:
            ChromeConfig with dashboard hints.
        """
        # Use custom hints if provided
        if custom_hints is not None:
            footer_hints = custom_hints
        # Otherwise fall back to standard hints based on details state
        elif details_open:
            footer_hints = (
                FooterHint("↑↓", "navigate"),
                FooterHint("Esc", "close"),
                FooterHint("Tab", "switch tab"),
                FooterHint("t", "teams", dimmed=standalone),
                FooterHint("q", "quit"),
                FooterHint("?", "help"),
            )
        else:
            footer_hints = (
                FooterHint("↑↓", "navigate"),
                FooterHint("Tab", "switch tab"),
                FooterHint("Enter", "details"),
                FooterHint("t", "teams", dimmed=standalone),
                FooterHint("q", "quit"),
                FooterHint("?", "help"),
            )

        return cls(
            title="SCC Dashboard",
            show_tabs=True,
            tabs=tuple(tabs),
            active_tab_index=active,
            show_search=True,
            footer_hints=footer_hints,
        )

    def with_context(self, context_label: str) -> ChromeConfig:
        """Create a new config with context label added.

        This is useful for adding current work context (team/repo/worktree)
        to any existing chrome configuration.

        Args:
            context_label: The context label (e.g., "platform · api · main").

        Returns:
            New ChromeConfig with context_label set.
        """
        return ChromeConfig(
            title=self.title,
            subtitle=self.subtitle,
            context_label=context_label,
            show_tabs=self.show_tabs,
            tabs=self.tabs,
            active_tab_index=self.active_tab_index,
            show_search=self.show_search,
            footer_hints=self.footer_hints,
        )


class Chrome:
    """Renderer for the shared chrome layout.

    Chrome wraps content in a consistent visual frame with title,
    tabs, search, and footer hints.

    Attributes:
        config: The ChromeConfig defining layout options.
    """

    def __init__(self, config: ChromeConfig) -> None:
        """Initialize chrome renderer.

        Args:
            config: Layout configuration.
        """
        self.config = config

    def render(
        self,
        body: RenderableType,
        *,
        search_query: str = "",
    ) -> RenderableType:
        """Render complete chrome with body content.

        Args:
            body: The main content to display inside chrome.
            search_query: Current filter/search query.

        Returns:
            A Rich renderable combining all chrome elements.
        """
        elements: list[RenderableType] = []

        # Tabs row (if enabled)
        if self.config.show_tabs:
            elements.append(self._render_tabs())

        # Search row (if enabled and has query)
        if self.config.show_search:
            elements.append(self._render_search(search_query))

        # Body content
        elements.append(body)

        # Footer hints
        if self.config.footer_hints:
            elements.append(self._render_footer())

        # Combine into panel with title
        title = self._build_title()
        return Panel(
            Group(*elements),
            title=title,
            title_align="left",
            border_style="blue",
            padding=(0, 1),
        )

    def _build_title(self) -> str:
        """Build the panel title string.

        Format: "Title │ context_label │ subtitle"
        - If only subtitle: "Title │ subtitle"
        - If only context: "Title │ context_label"
        - If neither: "Title"
        """
        parts = [self.config.title]
        if self.config.context_label:
            parts.append(self.config.context_label)
        if self.config.subtitle:
            parts.append(self.config.subtitle)
        sep = Indicators.get("VERTICAL_LINE")
        return f" {sep} ".join(parts)

    def _render_tabs(self) -> Text:
        """Render the tab row."""
        text = Text()
        for i, tab in enumerate(self.config.tabs):
            if i > 0:
                text.append("  ")
            if i == self.config.active_tab_index:
                text.append(f"[{tab}]", style="bold cyan")
            else:
                text.append(f" {tab} ", style="dim")
        text.append("\n")
        return text

    def _render_search(self, query: str) -> Text:
        """Render the search/filter row."""
        text = Text()
        if query:
            text.append(f"{Indicators.get('SEARCH_ICON')} ", style="dim")
            text.append(query, style="yellow")
            text.append(Indicators.get("TEXT_CURSOR"), style="yellow bold")
        else:
            text.append("Type to filter...", style="dim italic")
        text.append("\n")
        return text

    def _render_footer(self) -> Text:
        """Render the footer hints row."""
        text = Text()
        text.append(Borders.FOOTER_SEPARATOR * 40 + "\n", style="dim")
        for i, hint in enumerate(self.config.footer_hints):
            if i > 0:
                text.append(f" {Indicators.get('VERTICAL_LINE')} ", style="dim")
            # Dimmed hints (e.g., teams in standalone mode) show in strike-through dim
            if hint.dimmed:
                text.append(hint.key, style="dim strike")
                text.append(" ", style="dim")
                text.append(hint.action, style="dim strike")
            else:
                text.append(hint.key, style="cyan bold")
                text.append(" ", style="dim")
                text.append(hint.action, style="dim")
        return text


def render_chrome(
    config: ChromeConfig,
    body: RenderableType,
    *,
    search_query: str = "",
) -> RenderableType:
    """Convenience function to render chrome without instantiating Chrome class.

    Args:
        config: Chrome configuration.
        body: Body content to wrap.
        search_query: Current search/filter query.

    Returns:
        Complete rendered chrome with body.
    """
    chrome = Chrome(config)
    return chrome.render(body, search_query=search_query)
