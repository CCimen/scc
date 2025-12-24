"""Provide deprecation warning infrastructure.

Provide consistent deprecation warnings that respect output modes.
Suppress warnings in JSON mode to maintain clean machine output.

Usage:
    from scc_cli.deprecation import warn_deprecated

    # In command handler:
    warn_deprecated("old-cmd", "new-cmd", remove_version="2.0")
"""

import os

from rich.console import Console

from .output_mode import is_json_mode

# Stderr console for deprecation warnings
_stderr_console = Console(stderr=True)

# ═══════════════════════════════════════════════════════════════════════════════
# Deprecation Warnings
# ═══════════════════════════════════════════════════════════════════════════════


def warn_deprecated(
    old_cmd: str,
    new_cmd: str,
    remove_version: str = "2.0",
) -> None:
    """Print deprecation warning to stderr.

    Warnings are suppressed when:
    - JSON output mode is active (clean machine output)
    - SCC_NO_DEPRECATION_WARN=1 environment variable is set

    Args:
        old_cmd: The deprecated command/option name
        new_cmd: The replacement command/option name
        remove_version: The version when old_cmd will be removed
    """
    # Suppress in JSON mode for clean machine output
    if is_json_mode():
        return

    # Allow users to suppress deprecation warnings
    if os.environ.get("SCC_NO_DEPRECATION_WARN") == "1":
        return

    _stderr_console.print(
        f"[yellow]DEPRECATION:[/yellow] '{old_cmd}' is deprecated. "
        f"Use '{new_cmd}' instead. Will be removed in v{remove_version}."
    )
