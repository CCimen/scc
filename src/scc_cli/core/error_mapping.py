"""Shared error mapping helpers for CLI output."""

from __future__ import annotations

from typing import Any

from scc_cli.core.errors import ConfigError, PolicyViolationError, PrerequisiteError, SCCError
from scc_cli.core.exit_codes import (
    EXIT_CONFIG,
    EXIT_ERROR,
    EXIT_GOVERNANCE,
    EXIT_PREREQ,
    EXIT_VALIDATION,
)


def to_exit_code(exc: Exception) -> int:
    """Map exceptions to standardized exit codes.

    This mirrors legacy json_command handling to preserve behavior.
    """
    if isinstance(exc, PolicyViolationError):
        return EXIT_GOVERNANCE
    if isinstance(exc, PrerequisiteError):
        return EXIT_PREREQ
    if isinstance(exc, ConfigError):
        return EXIT_CONFIG
    if isinstance(exc, SCCError):
        return getattr(exc, "exit_code", EXIT_ERROR)
    if "Validation" in type(exc).__name__:
        return EXIT_VALIDATION
    return EXIT_ERROR


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
