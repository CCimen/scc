"""
JSON output mode infrastructure.

Provide context management for JSON output mode with automatic stderr suppression.
Use ContextVar for thread-safe, async-compatible state isolation.

Usage:
    from scc_cli.output_mode import json_output_mode, is_json_mode, print_json, print_human

    # In command handler:
    with json_output_mode():
        # All stderr chatter is suppressed here
        result = do_work()
        print_json(build_envelope(Kind.X, data=result))

    # Outside JSON mode (normal human output):
    print_human("Processing...")  # Only prints if not in JSON mode
"""

import json
import sys
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, TextIO

from rich.console import Console

# ═══════════════════════════════════════════════════════════════════════════════
# Context Variables (Thread-safe, Async-compatible)
# ═══════════════════════════════════════════════════════════════════════════════

_json_mode: ContextVar[bool] = ContextVar("json_mode", default=False)
_json_command_mode: ContextVar[bool] = ContextVar("json_command_mode", default=False)
_pretty_mode: ContextVar[bool] = ContextVar("pretty_mode", default=False)

# Console instances for stdout and stderr
# Rich Console requires file= in constructor, not in print()
console = Console()
err_console = Console(stderr=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Context Managers
# ═══════════════════════════════════════════════════════════════════════════════


@contextmanager
def json_output_mode() -> Generator[None, None, None]:
    """Context manager for JSON output mode.

    While active:
    - is_json_mode() returns True
    - print_human() becomes a no-op
    - All stderr chatter should be suppressed

    The context is properly reset even if an exception occurs,
    thanks to ContextVar's token-based reset mechanism.
    """
    token = _json_mode.set(True)
    try:
        yield
    finally:
        _json_mode.reset(token)


@contextmanager
def json_command_mode() -> Generator[None, None, None]:
    """Context manager for JSON command handling.

    This signals that errors should be handled by json_command instead of
    the generic error handler, allowing consistent JSON envelopes.
    """
    token = _json_command_mode.set(True)
    try:
        yield
    finally:
        _json_command_mode.reset(token)


@contextmanager
def pretty_output_mode() -> Generator[None, None, None]:
    """Context manager for pretty-printed JSON output.

    Enables indented JSON output. Usually combined with json_output_mode.
    """
    token = _pretty_mode.set(True)
    try:
        yield
    finally:
        _pretty_mode.reset(token)


# ═══════════════════════════════════════════════════════════════════════════════
# State Query Functions
# ═══════════════════════════════════════════════════════════════════════════════


def is_json_mode() -> bool:
    """Check if JSON output mode is active."""
    return _json_mode.get()


def is_json_command_mode() -> bool:
    """Check if JSON command handling mode is active."""
    return _json_command_mode.get()


def is_pretty_mode() -> bool:
    """Check if pretty-print mode is active for JSON output."""
    return _pretty_mode.get()


def set_pretty_mode(value: bool) -> None:
    """Set pretty-print mode for JSON output.

    Note: This is a direct setter that doesn't use context management.
    Use pretty_output_mode() context manager when possible for proper cleanup.

    Args:
        value: True to enable pretty-printing, False to disable.
    """
    _pretty_mode.set(value)


# ═══════════════════════════════════════════════════════════════════════════════
# Output Functions
# ═══════════════════════════════════════════════════════════════════════════════


def print_human(message: str, file: TextIO | None = None, **kwargs: Any) -> None:
    """Print human-readable output.

    This is a no-op when JSON mode is active, ensuring clean JSON output
    without any interleaved human-readable messages.

    Args:
        message: The message to print (Rich markup supported)
        file: Output target. Use sys.stderr for warnings/errors.
            Note: Rich Console requires file in constructor, not print(),
            so we use a separate err_console for stderr output.
        **kwargs: Additional arguments passed to console.print()
    """
    if not is_json_mode():
        # Select appropriate console based on file parameter
        target = err_console if file is sys.stderr else console
        target.print(message, **kwargs)


def print_json(envelope: dict[str, Any]) -> None:
    """Print JSON envelope to stdout.

    Output format:
    - Compact (no indentation) by default for CI/scripting efficiency
    - Pretty-printed (2-space indent) when pretty mode is active

    Args:
        envelope: The JSON envelope to output
    """
    if is_pretty_mode():
        # Pretty mode: indented for human readability
        output = json.dumps(envelope, indent=2)
    else:
        # Compact mode: minimal size for CI pipelines
        output = json.dumps(envelope, separators=(",", ":"))

    print(output)
