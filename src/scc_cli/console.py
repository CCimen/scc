"""Centralized console infrastructure with capability detection.

This module provides:
- TerminalCaps: Unified capability detection computed once per command
- Gated console factory respecting NO_COLOR, JSON mode, TTY state
- PlainTextStatus: Graceful degradation for non-TTY environments
- err_line(): Centralized stderr output (uses sys.stderr.write, not print)

The key rule: TerminalCaps.detect() is called ONCE at command entry point,
then passed down to all functions. No scattered TTY checks.

Usage:
    # At command entry:
    caps = TerminalCaps.detect(json_mode=ctx.json_mode)

    # In functions:
    with human_status("Processing...", caps) as status:
        do_work()

    # For direct stderr output (use sparingly):
    err_line("→ Starting operation...")
"""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, Protocol

from rich.console import Console

if TYPE_CHECKING:
    from collections.abc import Generator
    from typing import TextIO


# ═══════════════════════════════════════════════════════════════════════════════
# Centralized stderr output - single choke point for plain text
# ═══════════════════════════════════════════════════════════════════════════════


def err_line(text: str) -> None:
    """Write a line to stderr.

    This is the single choke point for plain text stderr output.
    Uses sys.stderr.write() directly to avoid print() entirely.

    Args:
        text: The text to write to stderr (newline appended automatically).
    """
    sys.stderr.write(text + "\n")
    sys.stderr.flush()  # Ensure immediate visibility in CI/buffered environments


# ═══════════════════════════════════════════════════════════════════════════════
# Stream-aware capability detection
# ═══════════════════════════════════════════════════════════════════════════════


def _supports_colors_for_stream(stream: TextIO) -> bool:
    """Check if colors should be enabled for a specific stream.

    CRITICAL: This checks the SPECIFIC stream's TTY status, not stdout.
    With our stderr contract (stdout=JSON, stderr=human UI), stdout may be
    piped while stderr is still a TTY. Checking stdout would incorrectly
    disable colors in `scc start --json | jq` scenarios.

    Args:
        stream: The stream to check (typically sys.stderr for Rich output).

    Returns:
        True if colors should be enabled for this stream.
    """
    if os.environ.get("NO_COLOR"):
        return False

    if os.environ.get("FORCE_COLOR"):
        return True

    return hasattr(stream, "isatty") and stream.isatty()


def _is_ci_environment() -> bool:
    """Detect if running in a CI environment.

    Checks common CI environment variables set by various CI systems:
    - CI (GitHub Actions, GitLab CI, CircleCI, Travis CI, etc.)
    - CONTINUOUS_INTEGRATION (Travis CI)
    - BUILD_NUMBER (Jenkins)
    - GITHUB_ACTIONS (GitHub Actions specific)
    - GITLAB_CI (GitLab CI specific)

    Returns:
        True if CI environment detected, False otherwise.
    """
    ci_vars = ["CI", "CONTINUOUS_INTEGRATION", "BUILD_NUMBER", "GITHUB_ACTIONS", "GITLAB_CI"]

    for var in ci_vars:
        value = os.getenv(var, "").lower()
        if value in ("1", "true", "yes"):
            return True

    return False


def _supports_unicode_for_stream(stream: TextIO) -> bool:
    """Check if a stream supports Unicode characters.

    This is stream-aware (matching _supports_colors_for_stream pattern)
    to handle cases where different streams have different encodings.

    Args:
        stream: The stream to check (typically sys.stderr for Rich output).

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


# ═══════════════════════════════════════════════════════════════════════════════
# Terminal Capabilities Dataclass
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class TerminalCaps:
    """All terminal capability checks in one place.

    This dataclass is IMMUTABLE (frozen=True) and should be computed ONCE
    at command entry point, then passed down to all functions.

    Attributes:
        can_render: Whether Rich UI (panels, tables) can display.
                   True when stderr is TTY and not in JSON mode.
        can_animate: Whether spinners/progress bars can display.
                    True when can_render AND TERM != dumb.
        can_prompt: Whether interactive prompts are allowed.
                   True when stdin is TTY, not JSON, not CI, not --no-interactive.
        colors: Whether colors should be enabled for stderr output.
        unicode: Whether Unicode characters are supported.
    """

    can_render: bool
    can_animate: bool
    can_prompt: bool
    colors: bool
    unicode: bool

    @classmethod
    def detect(
        cls,
        json_mode: bool = False,
        no_interactive: bool = False,
    ) -> TerminalCaps:
        """Detect all capabilities once at command entry.

        This method should be called ONCE at the beginning of a command,
        and the resulting TerminalCaps object passed to all functions.

        Args:
            json_mode: Whether --json flag is set.
            no_interactive: Whether --no-interactive flag is set.

        Returns:
            TerminalCaps with all capabilities computed.

        Example:
            caps = TerminalCaps.detect(json_mode=args.json)
            with human_status("Processing...", caps):
                do_work()
        """
        stderr_tty = sys.stderr.isatty()
        stdin_tty = sys.stdin.isatty()
        # Check for dumb, unknown, or empty TERM values
        term = (os.environ.get("TERM") or "").lower()
        term_dumb = term in ("dumb", "unknown", "")

        # can_render: Rich UI (panels, tables) can display
        can_render = stderr_tty and not json_mode

        return cls(
            can_render=can_render,
            can_animate=can_render and not term_dumb,
            # can_prompt requires BOTH stdin AND stderr to be TTYs:
            # - stdin: for reading user input
            # - stderr: for displaying prompts (Rich prompts go to stderr)
            can_prompt=stdin_tty
            and stderr_tty
            and not json_mode
            and not _is_ci_environment()
            and not no_interactive,
            colors=_supports_colors_for_stream(sys.stderr),
            unicode=_supports_unicode_for_stream(sys.stderr),
        )

    @classmethod
    def for_json_mode(cls) -> TerminalCaps:
        """Create TerminalCaps for JSON output mode.

        Convenience method that returns capabilities with all rendering disabled.
        Unicode detection still uses stderr in case internal strings need formatting.
        """
        return cls(
            can_render=False,
            can_animate=False,
            can_prompt=False,
            colors=False,
            unicode=_supports_unicode_for_stream(sys.stderr),
        )

    @classmethod
    def for_testing(
        cls,
        *,
        can_render: bool = True,
        can_animate: bool = True,
        can_prompt: bool = True,
        colors: bool = True,
        unicode: bool = True,
    ) -> TerminalCaps:
        """Create TerminalCaps with explicit values for testing.

        Use this in tests to control capabilities without environment dependencies.
        """
        return cls(
            can_render=can_render,
            can_animate=can_animate,
            can_prompt=can_prompt,
            colors=colors,
            unicode=unicode,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Status Objects - Unified interface for all status display modes
# ═══════════════════════════════════════════════════════════════════════════════


class StatusLike(Protocol):
    """Protocol for status objects yielded by human_status().

    All status implementations (Rich Status, PlainTextStatus, NullStatus)
    support this interface, enabling type-safe usage with autocomplete.

    Example:
        with human_status("Working...", caps) as status:
            status.update("Step 1")  # IDE autocomplete works here
    """

    def update(self, message: str) -> None:
        """Update the displayed status message."""
        ...


class NullStatus:
    """No-op status object that provides the same interface as Rich Status.

    Used when status display is disabled in JSON mode or other contexts
    where we don't want any output. For static text mode that needs
    completion messages, use StaticRichStatus instead.
    """

    def update(self, message: str) -> None:
        """No-op update method for interface compatibility.

        Args:
            message: Ignored - no display update occurs.
        """
        pass  # Intentionally empty - no output wanted


class StaticRichStatus:
    """Static status indicator using Rich formatting (no animation).

    Used when can_render=True but can_animate=False (e.g., TERM=dumb).
    Provides start/completion messages using Rich markup, preventing
    CI logs from appearing "hung" when animations are disabled.

    Output format:
        [dim]{message}...[/dim]             (on enter)
        [green]✓ {message} done[/green]     (on success)
        [red]✗ {message} failed[/red]       (on error)

    This ensures static mode has the same completion semantics as
    PlainTextStatus, but with Rich formatting.
    """

    def __init__(self, message: str, console: Console) -> None:
        """Initialize StaticRichStatus.

        Args:
            message: The status message to display.
            console: Rich Console to write output to.
        """
        self.message = message
        self.console = console
        # Import from theme to get Unicode-aware indicators
        from .theme import Indicators

        self.check = Indicators.get("PASS")  # "✓" or "OK"
        self.cross = Indicators.get("FAIL")  # "✗" or "FAIL"

    def update(self, message: str) -> None:
        """Update the status message (prints new message if changed).

        Only prints if the message actually changed to prevent log spam
        in CI environments where loops might call update() frequently.

        Args:
            message: The new status message to display.
        """
        if message != self.message:
            self.message = message
            self.console.print(f"[dim]{message}...[/dim]")

    def __enter__(self) -> StaticRichStatus:
        """Print start message to console."""
        self.console.print(f"[dim]{self.message}...[/dim]")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> Literal[False]:
        """Print completion or failure message to console."""
        if exc_val:
            self.console.print(f"[red]{self.cross} {self.message} failed[/red]")
            # Print brief error summary (one line)
            error_str = str(exc_val)
            if error_str:
                self.console.print(f"[dim]  Error: {error_str}[/dim]")
        else:
            self.console.print(f"[green]{self.check} {self.message} done[/green]")
        return False  # Don't suppress exceptions


class PlainTextStatus:
    """Plain text status indicator for non-TTY environments.

    When Rich spinners can't be used (non-TTY, JSON mode), this class provides
    a simple text-based alternative that shows progress without silence.

    Output format:
        → {message}...     (on enter)
        ✓ {message} done   (on success)
        ✗ {message} failed (on error)

    This prevents CI logs from appearing "hung" when Rich output is disabled.
    """

    def __init__(self, message: str, *, use_unicode: bool = True) -> None:
        """Initialize PlainTextStatus.

        Args:
            message: The status message to display.
            use_unicode: Whether to use Unicode symbols (→, ✓, ✗) or ASCII (>, OK, FAIL).
        """
        self.message = message
        self.arrow = "→" if use_unicode else ">"
        self.check = "✓" if use_unicode else "OK"
        self.cross = "✗" if use_unicode else "FAIL"

    def update(self, message: str) -> None:
        """Update the status message (compatibility with Rich Status interface).

        Only prints if the message actually changed to prevent log spam
        in CI environments where loops might call update() frequently.

        Args:
            message: The new status message to display.
        """
        if message != self.message:
            self.message = message
            err_line(f"{self.arrow} {message}...")

    def __enter__(self) -> PlainTextStatus:
        """Print start message to stderr."""
        err_line(f"{self.arrow} {self.message}...")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> Literal[False]:
        """Print completion or failure message to stderr."""
        if exc_val:
            err_line(f"{self.cross} {self.message} failed")
            # Print brief error summary (one line)
            error_str = str(exc_val)
            if error_str:
                err_line(f"  Error: {error_str}")
        else:
            err_line(f"{self.check} {self.message} done")
        return False  # Don't suppress exceptions


# ═══════════════════════════════════════════════════════════════════════════════
# Gated Console Factory
# ═══════════════════════════════════════════════════════════════════════════════

# Singleton consoles - created once, reused everywhere
_console: Console | None = None
_err_console: Console | None = None


def _resolve_force_terminal() -> bool | None:
    """Resolve force_terminal value from environment variables.

    Respects the standard FORCE_COLOR and NO_COLOR environment variables:
    - NO_COLOR takes precedence: disables colors AND terminal features
    - FORCE_COLOR enables terminal features even when not a TTY

    Returns:
        False if NO_COLOR is set (disable terminal features).
        True if FORCE_COLOR is set (and NO_COLOR is not).
        None otherwise (let Rich auto-detect).
    """
    if os.environ.get("NO_COLOR"):
        return False  # Explicitly disable terminal features
    if os.environ.get("FORCE_COLOR"):
        return True  # Force terminal features on
    return None  # Auto-detect


def get_console() -> Console:
    """Get the gated stdout console.

    This console respects NO_COLOR/FORCE_COLOR and is primarily for compatibility.
    Most output should go to stderr via get_err_console().

    Returns:
        Console configured for stdout.
    """
    global _console
    if _console is None:
        _console = Console(
            force_terminal=_resolve_force_terminal(),
            no_color=bool(os.environ.get("NO_COLOR")),
        )
    return _console


def get_err_console() -> Console:
    """Get the gated stderr console.

    This is the PRIMARY console for all human-readable Rich output.
    With our stderr contract:
    - stdout: JSON only (or nothing in human mode)
    - stderr: All Rich panels, spinners, prompts

    Applies the SCC theme for semantic style names (scc.success, scc.error, etc.).

    Returns:
        Console configured for stderr with SCC theme applied.
    """
    global _err_console
    if _err_console is None:
        # Lazy import to keep module load fast
        from scc_cli.theme import get_scc_theme

        _err_console = Console(
            stderr=True,
            force_terminal=_resolve_force_terminal(),
            no_color=bool(os.environ.get("NO_COLOR")),
            theme=get_scc_theme(),
        )
    return _err_console


def _reset_consoles_for_testing() -> None:
    """Reset console singletons for test isolation.

    Call this in test fixtures when toggling environment variables
    (NO_COLOR, FORCE_COLOR) to ensure fresh console instances that
    respect the new environment state.

    WARNING: Only use in tests! Production code should never call this.
    """
    global _console, _err_console
    _console = None
    _err_console = None


# ═══════════════════════════════════════════════════════════════════════════════
# Human Status Wrapper
# ═══════════════════════════════════════════════════════════════════════════════


@contextmanager
def human_status(
    message: str,
    caps: TerminalCaps,
    *,
    spinner: str = "dots",
) -> Generator[StatusLike, None, None]:
    """Context manager for status display with graceful degradation.

    When can_animate is True, displays a Rich spinner.
    When can_animate is False but can_render is True, displays static text
    with start/completion messages (using StaticRichStatus).
    When can_render is False, uses PlainTextStatus for minimal feedback.

    Args:
        message: The status message to display.
        caps: Terminal capabilities (from TerminalCaps.detect()).
        spinner: Rich spinner name (default "dots").

    Yields:
        A StatusLike object: Rich Status (animating), StaticRichStatus (static),
        or PlainTextStatus (non-TTY).

    Example:
        with human_status("Processing files", caps) as status:
            for file in files:
                process(file)
    """
    if caps.can_animate:
        # Full Rich spinner
        console = get_err_console()
        with console.status(message, spinner=spinner) as status:
            yield status
    elif caps.can_render:
        # Static text (no animation, but Rich formatting works)
        # Use StaticRichStatus for start/completion semantics matching PlainTextStatus
        console = get_err_console()
        with StaticRichStatus(message, console) as status:
            yield status
    else:
        # Plain text fallback for non-TTY
        with PlainTextStatus(message, use_unicode=caps.unicode) as status:
            yield status


# ═══════════════════════════════════════════════════════════════════════════════
# No-op context manager for JSON mode
# ═══════════════════════════════════════════════════════════════════════════════


@contextmanager
def silent_status() -> Generator[None, None, None]:
    """No-op context manager for JSON mode.

    Use this ONLY when json_mode=True and you need a status context
    but all output should be suppressed. For non-JSON modes, use
    human_status() which handles graceful degradation automatically.
    """
    yield None
