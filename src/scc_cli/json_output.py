"""
JSON envelope builder for CLI output.

Provide structured, versioned JSON envelopes for machine-readable output.
All JSON output MUST use this builder to ensure consistency.

Usage:
    from scc_cli.json_output import build_envelope
    from scc_cli.kinds import Kind

    envelope = build_envelope(Kind.TEAM_LIST, data={"teams": [...]})
"""

from datetime import datetime, timezone
from typing import Any

from . import __version__
from .core.errors import SCCError
from .kinds import Kind

# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

API_VERSION = "scc.cli/v1"


# ═══════════════════════════════════════════════════════════════════════════════
# Envelope Builder
# ═══════════════════════════════════════════════════════════════════════════════


def build_envelope(
    kind: Kind,
    *,
    data: dict[str, Any] | None = None,
    ok: bool = True,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build a JSON envelope with standard structure.

    All JSON output follows this contract for consistency and parseability.

    Args:
        kind: The envelope kind (from Kind enum)
        data: The command-specific payload
        ok: Whether the operation was successful
        errors: List of error messages (sets ok=False if non-empty)
        warnings: List of warning messages

    Returns:
        A structured envelope dict ready for JSON serialization:
        {
            "apiVersion": "scc.cli/v1",
            "kind": "TeamList",
            "metadata": {
                "generatedAt": "2025-12-23T10:00:00Z",
                "cliVersion": "1.2.3"
            },
            "status": {
                "ok": true,
                "errors": [],
                "warnings": []
            },
            "data": { ... }
        }
    """
    # Normalize optional parameters
    if data is None:
        data = {}
    if errors is None:
        errors = []
    if warnings is None:
        warnings = []

    # If errors provided, ok should be False
    if errors and ok:
        ok = False

    # Generate ISO 8601 timestamp in UTC
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "apiVersion": API_VERSION,
        "kind": str(kind.value) if hasattr(kind, "value") else str(kind),
        "metadata": {
            "generatedAt": generated_at,
            "cliVersion": __version__,
        },
        "status": {
            "ok": ok,
            "errors": errors,
            "warnings": warnings,
        },
        "data": data,
    }


def build_error_envelope(exc: Exception) -> dict[str, Any]:
    """Build a JSON error envelope from an exception.

    This is the canonical error format for JSON mode output.
    All errors should go through this function to ensure consistency.

    Args:
        exc: The exception to convert to JSON envelope

    Returns:
        A structured error envelope dict ready for JSON serialization:
        {
            "apiVersion": "scc.cli/v1",
            "kind": "Error",
            "metadata": { ... },
            "status": {
                "ok": false,
                "errors": ["Error message"],
                "warnings": []
            },
            "data": {
                "error_type": "SCCError",
                "user_message": "...",
                "suggested_action": "...",
                "debug_context": "..."  # Only for SCCError
            }
        }
    """
    # Generate ISO 8601 timestamp in UTC
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build error data depending on exception type
    error_data: dict[str, Any] = {
        "error_type": type(exc).__name__,
    }

    if isinstance(exc, SCCError):
        error_data["user_message"] = exc.user_message
        if exc.suggested_action:
            error_data["suggested_action"] = exc.suggested_action
        if exc.debug_context:
            error_data["debug_context"] = exc.debug_context
        error_message = exc.user_message
    else:
        error_message = str(exc)

    return {
        "apiVersion": API_VERSION,
        "kind": str(Kind.ERROR.value),
        "metadata": {
            "generatedAt": generated_at,
            "cliVersion": __version__,
        },
        "status": {
            "ok": False,
            "errors": [error_message],
            "warnings": [],
        },
        "data": error_data,
    }
