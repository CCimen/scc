"""Shared error mapping helpers for CLI output."""

from __future__ import annotations

from typing import Any

from scc_cli.core.errors import SCCError
from scc_cli.core.exit_codes import EXIT_NOT_FOUND, EXIT_TOOL


def to_exit_code(exc: Exception) -> int:
    """Return the programmatic exit code for SCC and foreign exceptions."""
    if isinstance(exc, SCCError):
        return exc.exit_code
    # Non-SCC validation errors from remote config and schema tooling are tool failures.
    if "Validation" in type(exc).__name__:
        return EXIT_TOOL
    return EXIT_NOT_FOUND


def to_json_payload(exc: Exception) -> dict[str, Any]:
    """Return JSON-ready error data and messages."""
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
        "errors": [error_message],
        "data": error_data,
    }


def to_human_message(exc: Exception) -> str:
    """Return a human-readable error message."""
    if isinstance(exc, SCCError):
        return exc.user_message
    return str(exc)
