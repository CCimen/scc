"""
Exit codes for SCC CLI.

Standardized exit codes following Unix conventions with semantic meaning.
All commands MUST use these constants for consistency.

Note: Click/Typer argument parsing errors (EXIT_USAGE) occur before
commands run, so they emit to stderr without JSON envelope.
"""

# Success
EXIT_SUCCESS = 0  # Command completed successfully

# Errors (1-6)
EXIT_ERROR = 1  # General/unexpected error
EXIT_USAGE = 2  # Invalid usage/arguments (Click default)
EXIT_CONFIG = 3  # Config or network error
EXIT_VALIDATION = 4  # Validation failed (schema, semantic checks)
EXIT_PREREQ = 5  # Prerequisites not met (Docker, Git)
EXIT_GOVERNANCE = 6  # Blocked by governance policy

# Cancellation (SIGINT convention)
EXIT_CANCELLED = 130  # User cancelled operation (SIGINT)

# Map exception types to exit codes (for json_command decorator)
# Note: Import from errors module only when needed to avoid circular imports
EXIT_CODE_MAP = {
    "ConfigError": EXIT_CONFIG,
    "ProfileNotFoundError": EXIT_CONFIG,
    "ValidationError": EXIT_VALIDATION,
    "PolicyViolationError": EXIT_GOVERNANCE,
    "PrerequisiteError": EXIT_PREREQ,
    "DockerNotFoundError": EXIT_PREREQ,
    "GitNotFoundError": EXIT_PREREQ,
    "UsageError": EXIT_USAGE,
}


def get_exit_code_for_exception(exc: Exception) -> int:
    """Return the appropriate exit code for an exception type.

    Walk up the exception's MRO to find a matching type in EXIT_CODE_MAP.
    Fall back to EXIT_ERROR if no specific mapping exists.

    Args:
        exc: The exception instance to map.

    Returns:
        The standardized exit code for the exception type.
    """
    for cls in type(exc).__mro__:
        if cls.__name__ in EXIT_CODE_MAP:
            return EXIT_CODE_MAP[cls.__name__]

    return EXIT_ERROR
