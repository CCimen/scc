"""Branding utilities for SCC CLI.

This module provides minimal, professional branding elements for CLI output:
- Version display headers
- Doctor command headers
- Unicode-safe fallbacks for all terminals

The aesthetic is professional/minimal to suit enterprise team adoption.
"""

from __future__ import annotations

from ..platform import supports_unicode


def get_version_header(version: str) -> str:
    """Generate version display header with unicode/ASCII fallback.

    Args:
        version: The version string to display (e.g., "1.4.0").

    Returns:
        Formatted header string with box-drawing or ASCII characters.
    """
    # Pad version to ensure consistent width (assumes version <= 10 chars)
    v_padded = f"v{version}".ljust(10)

    if supports_unicode():
        return (
            "╭───────────────────────────────────────╮\n"
            f"│  [cyan bold]SCC[/cyan bold]  Sandboxed Code CLI   [dim]{v_padded}[/dim] │\n"
            "╰───────────────────────────────────────╯"
        )
    else:
        return (
            "+---------------------------------------+\n"
            f"|  [cyan bold]SCC[/cyan bold]  Sandboxed Code CLI   [dim]{v_padded}[/dim] |\n"
            "+---------------------------------------+"
        )


def get_doctor_header() -> str:
    """Generate doctor command header with unicode/ASCII fallback.

    Returns:
        Formatted header string for doctor output.
    """
    if supports_unicode():
        return (
            "╭───────────────────────────────────────╮\n"
            "│  [cyan bold]SCC Doctor[/cyan bold]  System Health Check     │\n"
            "╰───────────────────────────────────────╯"
        )
    else:
        return (
            "+---------------------------------------+\n"
            "|  [cyan bold]SCC Doctor[/cyan bold]  System Health Check      |\n"
            "+---------------------------------------+"
        )


def get_brand_tagline(provider_id: str | None = None) -> str:
    """Get the brand tagline for SCC.

    Args:
        provider_id: Optional provider ID. When given, the provider's
            display name is appended to the tagline.

    Returns:
        The official tagline string.
    """
    base = "Safe development environment manager"
    if provider_id is not None:
        from scc_cli.core.provider_resolution import get_provider_display_name

        return f"{base} for {get_provider_display_name(provider_id)}"
    return base
