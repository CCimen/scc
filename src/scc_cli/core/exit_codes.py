"""
Exit codes for SCC CLI.

Standardized exit codes following Unix conventions with semantic meaning.
All commands MUST use these constants for consistency.

Exit Code Semantics:
  0: Success - command completed successfully
  1: Not Found - target not found (worktree name, session id, workspace missing)
  2: Usage Error - bad flags, invalid inputs, missing required args
  3: Config Error - config problems, network errors
  4: Tool Error - external tool failed (git error, docker error, not a git repo)
  5: Prerequisite Error - missing tools (Docker, Git not installed)
  6: Governance Error - blocked by policy
  130: Cancelled - user cancelled operation (SIGINT)

Note: Click/Typer argument parsing errors (EXIT_USAGE) occur before
commands run, so they emit to stderr without JSON envelope.
"""

# Success
EXIT_SUCCESS = 0  # Command completed successfully

# Errors (1-6) - ordered by severity/specificity
EXIT_NOT_FOUND = 1  # Target not found (worktree, session, workspace)
EXIT_ERROR = 1  # Alias for backwards compatibility (general/unexpected error)
EXIT_USAGE = 2  # Invalid usage/arguments (Click default)
EXIT_CONFIG = 3  # Config or network error
EXIT_TOOL = 4  # External tool failed (git error, docker error, not a git repo)
EXIT_VALIDATION = 4  # Alias: validation failures are tool errors
EXIT_PREREQ = 5  # Prerequisites not met (Docker, Git not installed)
EXIT_INTERNAL = 5  # Alias: internal errors also use 5
EXIT_GOVERNANCE = 6  # Blocked by governance policy

# Cancellation (SIGINT convention)
EXIT_CANCELLED = 130  # User cancelled operation (SIGINT)

# Map exception types to exit codes (for json_command decorator)
# Note: Import from errors module only when needed to avoid circular imports
EXIT_CODE_MAP = {
    # Tool errors (external commands failed)
    "ToolError": EXIT_TOOL,
    "WorkspaceError": EXIT_TOOL,
    "WorkspaceNotFoundError": EXIT_TOOL,
    "NotAGitRepoError": EXIT_TOOL,
    "GitWorktreeError": EXIT_TOOL,
    # Config errors
    "ConfigError": EXIT_CONFIG,
    "ProfileNotFoundError": EXIT_CONFIG,
    # Validation errors
    "ValidationError": EXIT_VALIDATION,
    # Governance errors
    "PolicyViolationError": EXIT_GOVERNANCE,
    # Prerequisite errors
    "PrerequisiteError": EXIT_PREREQ,
    "DockerNotFoundError": EXIT_PREREQ,
    "GitNotFoundError": EXIT_PREREQ,
    # Usage errors
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
