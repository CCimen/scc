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

from rich import box
from rich.console import Console, Group
from rich.padding import Padding
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
class LayoutMetrics:
    """Layout metrics for consistent TUI framing and spacing."""

    content_width: int
    left_pad: int
    should_center: bool
    tight_height: bool
    apply: bool
    pad_x: int

    def inner_width(self, *, padding_x: int = 1, border: int = 2) -> int:
        """Return usable inner width for content rendering."""
        width = self.content_width - border - 2 * padding_x
        return max(1, width)


def get_layout_metrics(
    console: Console,
    *,
    max_width: int = 104,
    gutter: int = 28,
    min_width: int = 40,
    pad_x: int = 2,
) -> LayoutMetrics:
    """Compute shared layout metrics for interactive TUI screens."""
    width = getattr(console.size, "width", 0)
    height = getattr(console.size, "height", 0)
    if not isinstance(width, int) or not isinstance(height, int):
        return LayoutMetrics(
            content_width=max_width,
            left_pad=0,
            should_center=False,
            tight_height=False,
            apply=False,
            pad_x=0,
        )

    tight_height = height < 28

    if not console.is_terminal or console.is_dumb_terminal:
        return LayoutMetrics(
            content_width=max_width,
            left_pad=0,
            should_center=False,
            tight_height=tight_height,
            apply=False,
            pad_x=0,
        )

    pad_x = 1 if width < 90 else pad_x
    usable_width = max(0, width - 2 * pad_x)
    content_width = min(max_width, usable_width)
    content_width = max(min_width, content_width)
    content_width = min(content_width, usable_width) if usable_width > 0 else 0
    should_center = width >= max_width + 2 * gutter
    left_pad = max(0, (width - content_width) // 2) if should_center else pad_x

    return LayoutMetrics(
        content_width=content_width,
        left_pad=left_pad,
        should_center=should_center,
        tight_height=tight_height,
        apply=True,
        pad_x=pad_x,
    )


def apply_layout(renderable: RenderableType, metrics: LayoutMetrics) -> RenderableType:
    """Apply left padding for centered or inset layouts."""
    if not metrics.apply or metrics.left_pad <= 0:
        return renderable
    return Padding(renderable, (0, 0, 0, metrics.left_pad))


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
        search_hint: Placeholder text when no filter query is active.
        footer_hints: List of keybinding hints for footer.
    """

    title: str
    subtitle: str = ""
    context_label: str = ""
    show_tabs: bool = False
    tabs: tuple[str, ...] = ()
    active_tab_index: int = 0
    show_search: bool = True
    search_hint: str = "type to search"
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
        - Enter: Select highlighted item (New Session or resume context)
        - n: Explicitly start a new session (skip resume)
        - a: Toggle all teams view (show contexts from all teams)
        - Esc: Back/dismiss (cancel wizard from this screen)
        - q: Quit app

        Args:
            title: Picker title (typically "Quick Resume").
            subtitle: Optional subtitle (defaults to hint about n/Esc).
            standalone: If True, dim the "t teams" and "a all teams" hints.

        Returns:
            ChromeConfig with Quick Resume-specific hints.
        """
        default_subtitle = "n for new session · a all teams · Esc to go back"
        if standalone:
            default_subtitle = "n for new session · Esc to go back"

        return cls(
            title=title,
            subtitle=subtitle or default_subtitle,
            show_tabs=False,
            show_search=True,
            footer_hints=(
                FooterHint("↑↓", "navigate"),
                FooterHint("Enter", "select"),
                FooterHint("n", "new session"),
                FooterHint("a", "all teams", dimmed=standalone),
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
        search_hint: str = "type to search",
        custom_hints: tuple[FooterHint, ...] | None = None,
    ) -> ChromeConfig:
        """Create standard config for dashboard view.

        Args:
            tabs: List of tab names.
            active: Index of active tab (0-based).
            standalone: If True, dim the "t teams" hint (not available without org).
            details_open: If True, show "Esc close" instead of "Enter details".
            search_hint: Placeholder text when filter input is idle.
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
            title="[cyan]SCC[/cyan] Dashboard",
            show_tabs=True,
            tabs=tuple(tabs),
            active_tab_index=active,
            show_search=True,
            search_hint=search_hint,
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
            search_hint=self.search_hint,
            footer_hints=self.footer_hints,
        )


class Chrome:
    """Renderer for the shared chrome layout.

    Chrome wraps content in a consistent visual frame with title,
    tabs, search, and footer hints.

    Attributes:
        config: The ChromeConfig defining layout options.
    """

    def __init__(
        self, config: ChromeConfig, *, console: Console | None = None, max_width: int = 104
    ) -> None:
        """Initialize chrome renderer.

        Args:
            config: Layout configuration.
            console: Console for layout sizing (optional).
            max_width: Maximum content width for the chrome frame.
        """
        self.config = config
        self._console = console
        self._max_width = max_width

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
        metrics: LayoutMetrics | None = None
        panel_width: int | None = None
        inner_width: int | None = None
        tight_height = False

        if self._console is not None:
            metrics = get_layout_metrics(self._console, max_width=self._max_width)
            tight_height = metrics.tight_height
            if metrics.apply:
                panel_width = metrics.content_width
                inner_width = metrics.inner_width(padding_x=1, border=2)

        elements: list[RenderableType] = []

        # Tabs row (if enabled)
        if self.config.show_tabs:
            elements.append(self._render_tabs(tight_height=tight_height))

        # Search row (if enabled and has query)
        if self.config.show_search:
            elements.append(self._render_search(search_query))

        # Body content
        elements.append(body)

        # Footer hints
        if self.config.footer_hints:
            elements.append(self._render_footer(inner_width=inner_width))

        # Combine into panel with title
        title = self._build_title()
        panel = Panel(
            Group(*elements),
            title=title,
            title_align="left",
            border_style="bright_black",
            box=box.ROUNDED,
            padding=(0, 1),
            width=panel_width,
        )

        if metrics is not None and metrics.apply:
            return apply_layout(panel, metrics)
        return panel

    def _build_title(self) -> Text:
        """Build the panel title renderable.

        Format: "Title │ context_label │ subtitle"
        - If only subtitle: "Title │ subtitle"
        - If only context: "Title │ context_label"
        - If neither: "Title"
        """
        segments: list[Text] = []
        segments.append(Text.from_markup(self.config.title))

        if self.config.context_label:
            segments.append(Text(self.config.context_label, style="dim"))
        if self.config.subtitle:
            segments.append(Text(self.config.subtitle, style="dim"))

        sep = f" {Indicators.get('VERTICAL_LINE')} "
        title = Text()
        for index, segment in enumerate(segments):
            if index > 0:
                title.append(sep, style="dim")
            title.append(segment)
        return title

    def _render_tabs(self, *, tight_height: bool = False) -> Text:
        """Render the tab row with underline-style active indicator."""
        tab_line = Text()
        underline_line = Text()
        separator = "   "

        for i, tab in enumerate(self.config.tabs):
            if i > 0:
                tab_line.append(separator)
                underline_line.append(" " * len(separator))

            is_active = i == self.config.active_tab_index
            segment = tab
            tab_style = "bold cyan" if is_active else "dim"
            tab_line.append(segment, style=tab_style)

            underline_char = Indicators.get("HORIZONTAL_LINE")
            underline = underline_char * len(segment) if is_active else " " * len(segment)
            underline_style = "cyan" if is_active else "dim"
            underline_line.append(underline, style=underline_style)

        if tight_height:
            return Text.assemble(tab_line, "\n", underline_line)
        return Text.assemble(tab_line, "\n", underline_line, "\n")

    def _render_search(self, query: str) -> Text:
        """Render the search/filter row."""
        text = Text()
        if query:
            text.append("Filter", style="cyan")
            text.append(": ", style="dim")
            text.append(query, style="white")
            text.append(Indicators.get("TEXT_CURSOR"), style="cyan")
        else:
            text.append("Filter: ", style="dim")
            if "/" in self.config.search_hint:
                before, after = self.config.search_hint.split("/", 1)
                text.append(before, style="dim italic")
                text.append("/", style="cyan")
                text.append(after, style="dim italic")
            else:
                text.append(self.config.search_hint, style="dim italic")
        text.append("\n")
        return text

    def _render_footer(self, *, inner_width: int | None = None) -> Text:
        """Render the footer hints row."""
        hints = Text()
        for i, hint in enumerate(self.config.footer_hints):
            if i > 0:
                hints.append("  ·  ", style="dim")
            if hint.dimmed:
                hints.append(hint.key, style="dim strike")
                hints.append(" ", style="dim")
                hints.append(hint.action, style="dim strike")
            else:
                hints.append(hint.key, style="cyan bold")
                hints.append(" ", style="dim")
                hints.append(hint.action, style="dim")

        separator_len = max(32, len(hints.plain))
        if inner_width:
            separator_len = max(separator_len, inner_width)
        text = Text()
        text.append(Borders.FOOTER_SEPARATOR * separator_len + "\n", style="dim")
        text.append(hints)
        return text


def render_chrome(
    config: ChromeConfig,
    body: RenderableType,
    *,
    search_query: str = "",
    console: Console | None = None,
    max_width: int = 104,
) -> RenderableType:
    """Convenience function to render chrome without instantiating Chrome class.

    Args:
        config: Chrome configuration.
        body: Body content to wrap.
        search_query: Current search/filter query.
        console: Console for layout sizing (optional).
        max_width: Maximum content width for the chrome frame.

    Returns:
        Complete rendered chrome with body.
    """
    chrome = Chrome(config, console=console, max_width=max_width)
    return chrome.render(body, search_query=search_query)
