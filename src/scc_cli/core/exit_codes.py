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

Preferred Usage:
  - Use specific codes (EXIT_NOT_FOUND, EXIT_TOOL, EXIT_CONFIG, etc.)
  - Avoid EXIT_ERROR - use a specific code instead
  - EXIT_VALIDATION maps to EXIT_TOOL (validation is a tool concern)
  - EXIT_INTERNAL maps to EXIT_PREREQ (internal errors are system issues)

Note: Click/Typer argument parsing errors (EXIT_USAGE) occur before
commands run, so they emit to stderr without JSON envelope.
"""

# Success
EXIT_SUCCESS = 0  # Command completed successfully

# Primary exit codes (1-6) - use these in new code
EXIT_NOT_FOUND = 1  # Target not found (worktree, session, workspace)
EXIT_USAGE = 2  # Invalid usage/arguments (Click default)
EXIT_CONFIG = 3  # Config or network error
EXIT_TOOL = 4  # External tool failed (git error, docker error, not a git repo)
EXIT_PREREQ = 5  # Prerequisites not met (Docker, Git not installed)
EXIT_GOVERNANCE = 6  # Blocked by governance policy

# Cancellation (SIGINT convention)
EXIT_CANCELLED = 130  # User cancelled operation (SIGINT)

# Deprecated aliases - prefer specific codes above
# These exist for backward compatibility and will be removed in a future version
EXIT_ERROR = EXIT_NOT_FOUND  # DEPRECATED: Use EXIT_NOT_FOUND or a specific code
EXIT_VALIDATION = EXIT_TOOL  # DEPRECATED: Use EXIT_TOOL instead
EXIT_INTERNAL = EXIT_PREREQ  # DEPRECATED: Use EXIT_PREREQ instead

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
    # Validation errors (treated as tool errors)
    "ValidationError": EXIT_TOOL,
    # Governance errors
    "PolicyViolationError": EXIT_GOVERNANCE,
    # Prerequisite errors
    "PrerequisiteError": EXIT_PREREQ,
    "DockerNotFoundError": EXIT_PREREQ,
    "GitNotFoundError": EXIT_PREREQ,
    # Internal errors (treated as prerequisite/system errors)
    "InternalError": EXIT_PREREQ,
    # Usage errors
    "UsageError": EXIT_USAGE,
}


def get_exit_code_for_exception(exc: Exception) -> int:
    """Return the appropriate exit code for an exception type.

    Walk up the exception's MRO to find a matching type in EXIT_CODE_MAP.
    Fall back to EXIT_NOT_FOUND if no specific mapping exists.

    Args:
        exc: The exception instance to map.

    Returns:
        The standardized exit code for the exception type.
    """
    for cls in type(exc).__mro__:
        if cls.__name__ in EXIT_CODE_MAP:
            return EXIT_CODE_MAP[cls.__name__]

    # Fallback for unmapped exceptions
    return EXIT_NOT_FOUND


# Error footer mappings - actionable hints for common error scenarios
# Use [dim]Try:[/dim] prefix to keep the command visible while dimming the prefix
ERROR_FOOTERS: dict[int, str] = {
    EXIT_NOT_FOUND: "[dim]Try:[/dim] [cyan]scc status[/cyan] or check your selection",
    EXIT_USAGE: "[dim]Try:[/dim] [cyan]scc <command> --help[/cyan]",
    EXIT_CONFIG: "[dim]Try:[/dim] [cyan]scc setup[/cyan] or [cyan]scc reset --config[/cyan]",
    EXIT_TOOL: "[dim]Try:[/dim] [cyan]scc doctor[/cyan]",
    EXIT_PREREQ: "[dim]Try:[/dim] [cyan]scc doctor[/cyan]",
    EXIT_GOVERNANCE: "[dim]Try:[/dim] [cyan]scc unblock[/cyan] or [cyan]scc exceptions create[/cyan]",
}


def get_error_footer(exit_code: int, exc: Exception | None = None) -> str | None:
    """Return an actionable hint for a given exit code.

    These footers help users recover from errors by suggesting relevant commands.
    For governance errors, includes the specific target in the hint if available.

    Args:
        exit_code: The exit code to get a footer for.
        exc: Optional exception to extract contextual info (e.g., blocked item).

    Returns:
        A rich-formatted hint string, or None if no hint is available.

    Examples:
        >>> get_error_footer(EXIT_PREREQ)
        "[dim]Try:[/dim] [cyan]scc doctor[/cyan]"
        >>> get_error_footer(EXIT_SUCCESS)
        None
    """
    # For governance errors, try to include the specific target
    if exit_code == EXIT_GOVERNANCE and exc is not None:
        target = getattr(exc, "item", None)
        if target:
            return (
                f"[dim]Try:[/dim] [cyan]scc unblock {target}[/cyan] "
                f"or [cyan]scc exceptions create[/cyan]"
            )

    return ERROR_FOOTERS.get(exit_code)
