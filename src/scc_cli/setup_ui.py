"""
TUI rendering components for the SCC setup wizard.

Extracted from setup.py to reduce module size.
Contains: arrow-key selection, welcome banner, step headers, two-pane layouts.
"""

import readchar
from rich import box
from rich.columns import Columns
from rich.console import Console, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .theme import Borders, Indicators
from .ui.chrome import LayoutMetrics, apply_layout, get_layout_metrics, print_with_layout

# ═══════════════════════════════════════════════════════════════════════════════
# Layout Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _layout_metrics(console: Console) -> LayoutMetrics:
    """Return layout metrics for setup rendering."""
    return get_layout_metrics(console, max_width=104)


def _print_padded(console: Console, renderable: RenderableType, metrics: LayoutMetrics) -> None:
    """Print with layout padding when applicable."""
    print_with_layout(console, renderable, metrics=metrics, constrain=True)


def _build_hint_text(hints: list[tuple[str, str]]) -> Text:
    """Build a compact hint line with middot separators."""
    text = Text()
    for index, (key, action) in enumerate(hints):
        if index > 0:
            text.append(" · ", style="dim")
        text.append(key, style="cyan bold")
        text.append(" ", style="dim")
        text.append(action, style="dim")
    return text


# ═══════════════════════════════════════════════════════════════════════════════
# Arrow-Key Selection Component
# ═══════════════════════════════════════════════════════════════════════════════


def _select_option(
    console: Console,
    options: list[tuple[str, str, str]],
    *,
    default: int = 0,
) -> int | None:
    """Interactive arrow-key selection for setup options.

    Args:
        console: Rich console for output.
        options: List of (label, tag, description) tuples.
        default: Default selected index.

    Returns:
        Selected index (0-based), or None if cancelled.
    """
    cursor = default
    cursor_symbol = Indicators.get("CURSOR")

    def _render_options() -> RenderableType:
        """Render options for the live picker."""
        metrics = _layout_metrics(console)
        content_width = metrics.content_width
        min_label_width = min(36, max(24, content_width // 3))
        label_width = max(min_label_width, max((len(label) for label, _, _ in options), default=0))
        tag_width = max((len(tag) for _, tag, _ in options), default=0)

        body = Text()
        if not metrics.tight_height:
            body.append("\n")

        for i, (label, tag, desc) in enumerate(options):
            is_selected = i == cursor
            line = Text()
            line.append("  ")
            line.append(cursor_symbol if is_selected else " ", style="cyan" if is_selected else "")
            line.append(" ")
            line.append(label, style="bold white" if is_selected else "dim")
            if tag:
                padding = label_width - len(label) + (3 if tag_width else 2)
                line.append(" " * max(2, padding))
                line.append(tag, style="cyan" if is_selected else "dim")
            body.append_text(line)
            body.append("\n")
            if desc:
                body.append(f"    {desc}\n", style="dim")

            if i < len(options) - 1 and not metrics.tight_height:
                body.append("\n")

        if not metrics.tight_height:
            body.append("\n")

        hints = _build_hint_text(
            [
                ("↑↓", "navigate"),
                ("Enter", "confirm"),
                ("Esc", "cancel"),
            ]
        )
        inner_width = (
            metrics.inner_width(padding_x=1, border=2)
            if metrics.should_center and metrics.apply
            else content_width
        )
        separator_len = max(len(hints.plain), inner_width)
        body.append(Borders.FOOTER_SEPARATOR * separator_len, style="dim")
        body.append("\n")
        body.append_text(hints)

        renderable: RenderableType = body
        if metrics.apply and metrics.should_center:
            renderable = Panel(
                body,
                border_style="bright_black",
                box=box.ROUNDED,
                padding=(0, 1),
                width=metrics.content_width,
            )

        if metrics.apply:
            renderable = apply_layout(renderable, metrics)

        return renderable

    with Live(_render_options(), console=console, auto_refresh=False, transient=True) as live:
        while True:
            key = readchar.readkey()

            if key in (readchar.key.UP, "k"):
                cursor = (cursor - 1) % len(options)
                live.update(_render_options(), refresh=True)
            elif key in (readchar.key.DOWN, "j"):
                cursor = (cursor + 1) % len(options)
                live.update(_render_options(), refresh=True)
            elif key in (readchar.key.ENTER, "\r", "\n"):
                return cursor
            elif key in (readchar.key.ESC, "q"):
                return None
            else:
                continue


# ═══════════════════════════════════════════════════════════════════════════════
# Welcome Screen
# ═══════════════════════════════════════════════════════════════════════════════


WELCOME_BANNER = """
[cyan]╔═══════════════════════════════════════════════════════════╗[/cyan]
[cyan]║[/cyan]                                                           [cyan]║[/cyan]
[cyan]║[/cyan]   [bold white]Welcome to SCC - Sandboxed Claude CLI[/bold white]                [cyan]║[/cyan]
[cyan]║[/cyan]                                                           [cyan]║[/cyan]
[cyan]║[/cyan]   [dim]Safe development environment for AI-assisted coding[/dim]   [cyan]║[/cyan]
[cyan]║[/cyan]                                                           [cyan]║[/cyan]
[cyan]╚═══════════════════════════════════════════════════════════╝[/cyan]
"""


def show_welcome(console: Console) -> None:
    """Display the welcome banner on the console."""
    console.print()
    console.print(WELCOME_BANNER)


# ═══════════════════════════════════════════════════════════════════════════════
# Setup Header (TUI-style)
# ═══════════════════════════════════════════════════════════════════════════════


SETUP_STEPS = ("Mode", "Org", "Auth", "Team", "Hooks", "Confirm")


def _render_setup_header(console: Console, *, step_index: int, subtitle: str | None = None) -> None:
    """Render the setup step header with underline-style tabs."""
    console.clear()

    metrics = _layout_metrics(console)
    content_width = metrics.content_width

    console.print()
    _print_padded(console, Text("SCC Setup", style="bold white"), metrics)
    if not metrics.tight_height:
        console.print()

    tabs = Text()
    underline = Text()
    separator = "   "

    for idx, step in enumerate(SETUP_STEPS):
        if idx > 0:
            tabs.append(separator)
            underline.append(" " * len(separator))

        is_active = idx == step_index
        is_complete = idx < step_index
        if is_active:
            tab_style = "bold cyan"
        elif is_complete:
            tab_style = "green"
        else:
            tab_style = "dim"

        tabs.append(step, style=tab_style)
        underline_segment = (
            Indicators.get("HORIZONTAL_LINE") * len(step) if is_active else " " * len(step)
        )
        underline.append(underline_segment, style="cyan" if is_active else "dim")

    _print_padded(console, tabs, metrics)
    _print_padded(console, underline, metrics)

    if not metrics.should_center:
        separator_len = max(len(tabs.plain), content_width)
        _print_padded(console, Borders.FOOTER_SEPARATOR * separator_len, metrics)

    if subtitle:
        if not metrics.tight_height:
            console.print()
        _print_padded(console, f"  {subtitle}", metrics)
        console.print()
    else:
        console.print()


def _render_setup_layout(
    console: Console,
    *,
    step_index: int,
    subtitle: str | None,
    left_title: str,
    left_body: Text | Table,
    right_title: str,
    right_body: Text | Table,
    footer_hint: str | None = None,
) -> None:
    """Render a two-pane setup layout with a shared header."""
    _render_setup_header(console, step_index=step_index, subtitle=subtitle)

    metrics = _layout_metrics(console)
    content_width = metrics.content_width
    width = console.size.width
    stacked_width = content_width
    column_width = max(32, (content_width - 4) // 2)

    expand_panels = width >= 100

    left_panel = Panel(
        left_body,
        title=f"[dim]{left_title}[/dim]",
        border_style="bright_black",
        padding=(0, 1),
        box=box.ROUNDED,
        width=stacked_width if width < 100 else column_width,
        expand=expand_panels,
    )
    right_panel = Panel(
        right_body,
        title=f"[dim]{right_title}[/dim]",
        border_style="bright_black",
        padding=(0, 1),
        box=box.ROUNDED,
        width=stacked_width if width < 100 else column_width,
        expand=expand_panels,
    )

    if width < 100:
        _print_padded(console, left_panel, metrics)
        if not metrics.tight_height:
            console.print()
        _print_padded(console, right_panel, metrics)
    else:
        columns = Columns([left_panel, right_panel], expand=False, equal=True)
        _print_padded(console, columns, metrics)

    console.print()
    if footer_hint:
        separator_len = max(len(footer_hint), content_width)
        _print_padded(console, Borders.FOOTER_SEPARATOR * separator_len, metrics)
        _print_padded(console, f"  [dim]{footer_hint}[/dim]", metrics)
        return

    hints = _build_hint_text(
        [
            ("↑↓", "navigate"),
            ("Enter", "confirm"),
            ("Esc", "cancel"),
        ]
    )
    separator_len = max(len(hints.plain), content_width)
    _print_padded(console, Borders.FOOTER_SEPARATOR * separator_len, metrics)
    _print_padded(console, hints, metrics)
