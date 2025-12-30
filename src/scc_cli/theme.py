"""Design tokens and theme configuration for SCC CLI.

This module is the SINGLE SOURCE OF TRUTH for all visual constants.
It must remain a LEAF MODULE with no imports from dashboard, list_screen,
or other UI modules to prevent circular dependencies.

Contains:
- Colors: Semantic color names for panels, text, and borders
- Borders: Panel border style mappings (derived from Colors)
- Indicators: Status symbols with ASCII fallbacks
- Spinners: Contextual spinner names for different operations
- get_scc_theme(): Lazy-loaded Rich Theme for semantic style names

Usage:
    from scc_cli.theme import Colors, Borders, Indicators, get_scc_theme

    # Use semantic names instead of hardcoded colors:
    border_style=Borders.PANEL_SUCCESS  # instead of "green"

    # Use indicators with fallbacks:
    symbol = Indicators.get("PASS")  # returns "✓" or "OK"

    # Apply theme to console:
    console = Console(theme=get_scc_theme())
    console.print("[scc.success]✓ Passed[/scc.success]")
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import TextIO

    from rich.theme import Theme


# ═══════════════════════════════════════════════════════════════════════════════
# Unicode Detection (internal, no external dependencies)
# ═══════════════════════════════════════════════════════════════════════════════
# NOTE: This logic is kept in sync with console.py's _supports_unicode_for_stream.
# Duplicated here to keep theme.py a leaf module with no UI imports.


def _supports_unicode_for_stream(stream: "TextIO") -> bool:
    """Check if a stream supports Unicode characters.

    This is stream-aware (matching _supports_colors_for_stream pattern in console.py)
    to handle cases where different streams have different encodings.

    Args:
        stream: A file-like object with an 'encoding' attribute.

    Returns:
        True if UTF-8 encoding is available on the stream.
    """
    encoding = getattr(stream, "encoding", None) or ""
    if encoding.lower() in ("utf-8", "utf8"):
        return True

    # Check locale environment variables as fallback (LC_ALL > LC_CTYPE > LANG)
    locale_var = (
        os.environ.get("LC_ALL") or os.environ.get("LC_CTYPE") or os.environ.get("LANG", "")
    )
    return "utf-8" in locale_var.lower() or "utf8" in locale_var.lower()


def _supports_unicode() -> bool:
    """Check if stderr supports Unicode characters.

    IMPORTANT: Defaults to stderr since that's where Rich UI renders.
    This avoids false negatives when stdout is piped (e.g., `scc ... | jq`).

    For explicit stream checking, use _supports_unicode_for_stream().

    Returns:
        True if UTF-8 encoding is available on stderr.
    """
    return _supports_unicode_for_stream(sys.stderr)


# Cached at module load time for consistent behavior.
# IMPORTANT: In UI code, prefer passing `unicode=caps.unicode` explicitly
# to Indicators.get() and get_brand_header() rather than relying on this default.
_UNICODE_SUPPORTED: bool = _supports_unicode()


# ═══════════════════════════════════════════════════════════════════════════════
# Color Definitions
# ═══════════════════════════════════════════════════════════════════════════════


class Colors:
    """Semantic color names for the SCC CLI.

    All color values are Rich-compatible color strings.
    Use these instead of hardcoded color names for consistency.

    Example:
        panel = Panel(content, border_style=Colors.SUCCESS)
    """

    # Brand colors
    BRAND = "cyan"
    BRAND_BOLD = "bold cyan"

    # Semantic colors
    SUCCESS = "green"
    SUCCESS_BOLD = "bold green"
    WARNING = "yellow"
    WARNING_BOLD = "bold yellow"
    ERROR = "red"
    ERROR_BOLD = "bold red"
    INFO = "blue"
    INFO_BOLD = "bold blue"

    # Text colors
    PRIMARY = "white"
    SECONDARY = "dim"
    MUTED = "dim white"

    # State colors
    RUNNING = "green"
    STOPPED = "dim"
    PAUSED = "yellow"


# ═══════════════════════════════════════════════════════════════════════════════
# Panel Border Styles
# ═══════════════════════════════════════════════════════════════════════════════


class Borders:
    """Panel border styles for consistent UI.

    Maps semantic panel types to their border colors.
    All values derive from Colors to maintain single source of truth.
    Use with Panel(..., border_style=Borders.PANEL_SUCCESS).

    Example:
        panel = Panel(content, border_style=Borders.PANEL_INFO)
    """

    # Panel borders (derived from Colors - single source of truth)
    PANEL_INFO = Colors.BRAND  # cyan
    PANEL_SUCCESS = Colors.SUCCESS  # green
    PANEL_WARNING = Colors.WARNING  # yellow
    PANEL_ERROR = Colors.ERROR  # red
    PANEL_NEUTRAL = Colors.INFO  # blue
    PANEL_MUTED = Colors.SECONDARY  # dim

    # Footer separator character (width computed at render time via console.width)
    FOOTER_SEPARATOR = "─" if _UNICODE_SUPPORTED else "-"


# ═══════════════════════════════════════════════════════════════════════════════
# Status Indicators
# ═══════════════════════════════════════════════════════════════════════════════


class Indicators:
    """Status indicator symbols with ASCII fallbacks.

    Use get() method to automatically select Unicode or ASCII based on
    terminal capabilities detected at module load.

    Example:
        symbol = Indicators.get("PASS")  # "✓" or "OK"
        print(f"{Indicators.get('RUNNING')} Container active")
    """

    # Mapping of indicator name -> (unicode, ascii)
    _SYMBOLS: dict[str, tuple[str, str]] = {
        # Success/failure
        "PASS": ("✓", "OK"),
        "FAIL": ("✗", "FAIL"),
        "CHECK": ("✓", "[x]"),
        "CROSS": ("✗", "[!]"),
        # Warning/info
        "WARNING": ("!", "!"),
        "INFO": ("i", "i"),
        # Status
        "RUNNING": ("●", "[*]"),
        "STOPPED": ("○", "[ ]"),
        "PAUSED": ("◐", "[~]"),
        # Navigation
        "CURSOR": ("❯", ">"),
        "TEXT_CURSOR": ("▏", "|"),
        "ARROW": ("→", "->"),
        "BULLET": ("•", "*"),
        "SCROLL_UP": ("↑", "^"),
        "SCROLL_DOWN": ("↓", "v"),
        # Progress
        "PENDING": ("⏳", "..."),
        "SPINNER": ("◌", "o"),
        # Layout elements
        "INFO_ICON": ("ℹ", "i"),  # Circled info icon for hints
        "SEARCH_ICON": ("🔍", "[?]"),  # Search/filter indicator
        "VERTICAL_LINE": ("│", "|"),  # Table column separator
        "HORIZONTAL_LINE": ("─", "-"),  # Section separator
    }

    @classmethod
    def get(cls, name: str, *, unicode: bool | None = None) -> str:
        """Get indicator symbol with automatic fallback.

        Args:
            name: Indicator name (e.g., "PASS", "RUNNING").
            unicode: Override unicode detection. If None, uses module default.

        Returns:
            Unicode or ASCII symbol based on terminal capabilities.

        Raises:
            KeyError: If indicator name is not found.
        """
        if name not in cls._SYMBOLS:
            raise KeyError(f"Unknown indicator: {name}")

        use_unicode = unicode if unicode is not None else _UNICODE_SUPPORTED
        unicode_char, ascii_char = cls._SYMBOLS[name]
        return unicode_char if use_unicode else ascii_char

    @classmethod
    def has(cls, name: str) -> bool:
        """Check if an indicator name exists.

        Use this to safely check before calling get() if you want to
        avoid KeyError exceptions.

        Args:
            name: Indicator name to check.

        Returns:
            True if the indicator exists, False otherwise.
        """
        return name in cls._SYMBOLS

    @classmethod
    def all_names(cls) -> list[str]:
        """Get all available indicator names."""
        return list(cls._SYMBOLS.keys())


# ═══════════════════════════════════════════════════════════════════════════════
# Spinner Names
# ═══════════════════════════════════════════════════════════════════════════════


class Spinners:
    """Contextual spinner names for different operation types.

    All values are valid Rich spinner names.
    See: https://rich.readthedocs.io/en/stable/reference/spinner.html

    Example:
        with console.status("Building...", spinner=Spinners.BUILD):
            build_project()
    """

    # Default spinner
    DEFAULT = "dots"

    # Context-specific spinners
    DOCKER = "dots12"  # Docker/container operations
    NETWORK = "dots8Bit"  # Network/fetch operations
    BUILD = "bouncingBar"  # Build/compile operations
    SEARCH = "point"  # Search/scan operations
    SETUP = "arc"  # Setup/initialization


# ═══════════════════════════════════════════════════════════════════════════════
# Rich Theme Definition
# ═══════════════════════════════════════════════════════════════════════════════

# Delayed import to keep module load fast when Theme isn't needed
_theme_instance: Theme | None = None


def get_scc_theme() -> Theme:
    """Get the SCC Rich Theme instance (lazy-loaded).

    Returns:
        Rich Theme with semantic style names.

    Example:
        console = Console(theme=get_scc_theme())
        console.print("[scc.success]✓ Passed[/scc.success]")
    """
    global _theme_instance
    if _theme_instance is None:
        from rich.theme import Theme

        _theme_instance = Theme(
            {
                # Brand
                "scc.brand": Colors.BRAND,
                "scc.brand.bold": Colors.BRAND_BOLD,
                # Semantic
                "scc.success": Colors.SUCCESS,
                "scc.success.bold": Colors.SUCCESS_BOLD,
                "scc.warning": Colors.WARNING,
                "scc.warning.bold": Colors.WARNING_BOLD,
                "scc.error": Colors.ERROR,
                "scc.error.bold": Colors.ERROR_BOLD,
                "scc.info": Colors.INFO,
                "scc.info.bold": Colors.INFO_BOLD,
                # Text
                "scc.primary": Colors.PRIMARY,
                "scc.secondary": Colors.SECONDARY,
                "scc.muted": Colors.MUTED,
                # Status
                "scc.running": Colors.RUNNING,
                "scc.stopped": Colors.STOPPED,
                "scc.paused": Colors.PAUSED,
            }
        )
    return _theme_instance


# ═══════════════════════════════════════════════════════════════════════════════
# ASCII Art Branding (Optional)
# ═══════════════════════════════════════════════════════════════════════════════


def get_brand_header(*, unicode: bool | None = None) -> str:
    """Get minimal brand header for --version and doctor output.

    Args:
        unicode: Override unicode detection. If None, uses module default.

    Returns:
        Brand header string with proper box-drawing characters.
    """
    use_unicode = unicode if unicode is not None else _UNICODE_SUPPORTED

    if use_unicode:
        return """\
╭───────────────────────────────────────╮
│  SCC  Sandboxed Claude CLI            │
╰───────────────────────────────────────╯"""
    else:
        return """\
+---------------------------------------+
|  SCC  Sandboxed Claude CLI            |
+---------------------------------------+"""
