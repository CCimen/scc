"""Core business logic and shared foundations.

This package contains domain-agnostic foundations:
- errors: Exception hierarchy
- constants: Application constants
- exit_codes: CLI exit code definitions

These modules have no CLI dependencies and can be used by
both CLI and non-CLI code (tests, background tasks, etc.).
"""

from __future__ import annotations

from . import personal_profiles

# Explicit public API exports
from .constants import CLI_VERSION
from .errors import (
    ConfigError,
    InternalError,
    PolicyViolationError,
    PrerequisiteError,
    ProfileNotFoundError,
    SCCError,
    ToolError,
    UsageError,
)
from .exit_codes import (
    EXIT_CANCELLED,
    EXIT_CODE_MAP,
    EXIT_CONFIG,
    EXIT_ERROR,
    EXIT_GOVERNANCE,
    EXIT_INTERNAL,
    EXIT_NOT_FOUND,
    EXIT_PREREQ,
    EXIT_SUCCESS,
    EXIT_TOOL,
    EXIT_USAGE,
    EXIT_VALIDATION,
    get_exit_code_for_exception,
)

__all__ = [
    # Version
    "CLI_VERSION",
    # Errors
    "SCCError",
    "UsageError",
    "PrerequisiteError",
    "ToolError",
    "ConfigError",
    "PolicyViolationError",
    "ProfileNotFoundError",
    "InternalError",
    # Exit codes
    "EXIT_SUCCESS",
    "EXIT_NOT_FOUND",
    "EXIT_ERROR",
    "EXIT_USAGE",
    "EXIT_CONFIG",
    "EXIT_TOOL",
    "EXIT_VALIDATION",
    "EXIT_PREREQ",
    "EXIT_INTERNAL",
    "EXIT_GOVERNANCE",
    "EXIT_CANCELLED",
    "EXIT_CODE_MAP",
    "get_exit_code_for_exception",
    "personal_profiles",
]
