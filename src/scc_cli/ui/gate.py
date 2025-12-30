"""Interactivity gate - policy enforcement for interactive UI.

This module implements the interactivity decision system that determines
whether interactive UI (pickers, lists, prompts) can be shown. It enforces
a strict priority order to ensure predictable behavior in all contexts.

Priority Order (highest to lowest):
1. JSON mode (--json) → Always False
2. Explicit --no-interactive flag → Always False
3. CI environment detection → False
4. Non-TTY stdin → False
5. Explicit --interactive flag → True (if TTY available)
6. Default → True (if TTY available)

Fast Fail Validation:
Conflicting flags (--json with --interactive/--select) raise UsageError
immediately rather than silently ignoring the interactive flag.

Example:
    >>> ctx = InteractivityContext.create(json_mode=False)
    >>> if ctx.allows_prompt():
    ...     result = pick_team(teams)
    ... else:
    ...     raise UsageError("--team-name required")
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, TypeVar

from rich.console import Console

from ..exit_codes import EXIT_SUCCESS, EXIT_USAGE

if TYPE_CHECKING:
    pass

T = TypeVar("T")

# Console for error output
_stderr_console = Console(stderr=True)


class InteractivityMode(Enum):
    """Resolved interactivity mode after gate evaluation."""

    INTERACTIVE = auto()  # Full interactive UI allowed
    NON_INTERACTIVE = auto()  # Text output only, fail on missing selection


def _is_ci_environment() -> bool:
    """Detect if running in a CI environment.

    Checks common CI environment variables set by various CI systems:
    - CI (GitHub Actions, GitLab CI, CircleCI, Travis CI, etc.)
    - CONTINUOUS_INTEGRATION (Travis CI)
    - BUILD_NUMBER (Jenkins)
    - GITHUB_ACTIONS (GitHub Actions specific)
    - GITLAB_CI (GitLab CI specific)

    Returns:
        True if CI environment detected, False otherwise.
    """
    ci_vars = ["CI", "CONTINUOUS_INTEGRATION", "BUILD_NUMBER", "GITHUB_ACTIONS", "GITLAB_CI"]

    for var in ci_vars:
        value = os.getenv(var, "").lower()
        if value in ("1", "true", "yes"):
            return True

    return False


def _is_tty_available() -> bool:
    """Check if stdin is a TTY (terminal).

    Returns:
        True if stdin is a terminal, False if piped/redirected.
    """
    return sys.stdin.isatty()


def validate_mode_flags(
    *,
    json_mode: bool = False,
    interactive: bool = False,
    select: bool = False,
    dashboard: bool = False,
) -> None:
    """Validate that mode flags don't conflict - fail fast if they do.

    This validation should be called as early as possible after option parsing,
    before any UI/gating code runs. It ensures users get immediate feedback
    about conflicting flags rather than silent behavior.

    Args:
        json_mode: Whether --json flag is set.
        interactive: Whether --interactive/-i flag is set.
        select: Whether --select flag is set.
        dashboard: Whether --dashboard flag is set.

    Raises:
        UsageError: If JSON mode is combined with any interactive flag.

    Example:
        >>> validate_mode_flags(json_mode=True, interactive=True)
        Traceback (most recent call last):
            ...
        UsageError: Cannot use --json with --interactive
    """
    from ..errors import UsageError

    if not json_mode:
        return  # No conflict possible without JSON mode

    # Collect all conflicting flags
    conflicts: list[str] = []
    if interactive:
        conflicts.append("--interactive")
    if select:
        conflicts.append("--select")
    if dashboard:
        conflicts.append("--dashboard")

    if conflicts:
        flags_str = ", ".join(conflicts)
        raise UsageError(
            user_message=f"Cannot use --json with {flags_str}",
            suggested_action=(
                "Remove one of the conflicting flags. "
                "Use --json for machine-readable output OR interactive flags for user prompts, not both."
            ),
        )


def is_interactive_allowed(
    *,
    json_mode: bool = False,
    no_interactive_flag: bool = False,
    interactive_flag: bool = False,
) -> bool:
    """Check if interactive UI is allowed based on priority order.

    Priority (from highest to lowest):
    1. JSON mode (--json) → False
    2. Explicit --no-interactive flag → False
    3. CI environment detection → False
    4. Non-TTY stdin → False
    5. Explicit --interactive flag → True (if TTY available)
    6. Default → True (if TTY available)

    Args:
        json_mode: Whether --json flag is set.
        no_interactive_flag: Whether --no-interactive flag is set.
        interactive_flag: Whether --interactive flag is set.

    Returns:
        True if interactive prompts are permitted, False otherwise.

    Example:
        >>> is_interactive_allowed(json_mode=True)
        False
        >>> is_interactive_allowed()  # in TTY, no CI
        True
    """
    # Priority 1: JSON mode always blocks
    if json_mode:
        return False

    # Priority 2: Explicit --no-interactive blocks
    if no_interactive_flag:
        return False

    # Priority 3: CI environment blocks
    if _is_ci_environment():
        return False

    # Priority 4: Non-TTY blocks
    if not _is_tty_available():
        return False

    # Priority 5 & 6: TTY available, allow interactive
    # (--interactive flag doesn't change anything here since TTY is required anyway)
    return True


@dataclass(frozen=True)
class InteractivityContext:
    """Immutable context for interactivity decisions throughout a command.

    Create once at command entry point, pass to all UI functions.
    This ensures consistent behavior across all UI components.

    Attributes:
        mode: Resolved interactivity mode (INTERACTIVE or NON_INTERACTIVE).
        is_json_output: Whether --json flag is set (for output formatting).
        force_yes: Whether --yes flag is set (skip confirmations).
    """

    mode: InteractivityMode
    is_json_output: bool
    force_yes: bool

    @classmethod
    def create(
        cls,
        *,
        json_mode: bool = False,
        no_interactive: bool = False,
        force_interactive: bool = False,
        force_yes: bool = False,
    ) -> InteractivityContext:
        """Create context from command-line flags.

        This is the primary factory method for creating InteractivityContext.
        Call once at the entry point of a command and pass down to all UI functions.

        Args:
            json_mode: Whether --json flag is set.
            no_interactive: Whether --no-interactive flag is set.
            force_interactive: Whether --interactive/-i flag is set.
            force_yes: Whether --yes/-y flag is set.

        Returns:
            Configured InteractivityContext with resolved mode.
        """
        allowed = is_interactive_allowed(
            json_mode=json_mode,
            no_interactive_flag=no_interactive,
            interactive_flag=force_interactive,
        )

        mode = InteractivityMode.INTERACTIVE if allowed else InteractivityMode.NON_INTERACTIVE

        return cls(
            mode=mode,
            is_json_output=json_mode,
            force_yes=force_yes,
        )

    def allows_prompt(self) -> bool:
        """Whether interactive prompts are permitted.

        Returns:
            True if interactive UI can be shown, False if must use explicit args.
        """
        return self.mode == InteractivityMode.INTERACTIVE and not self.is_json_output

    def requires_confirmation(self) -> bool:
        """Whether destructive actions need confirmation.

        Returns:
            True if confirmation dialog should be shown, False if --yes bypasses it.
        """
        return not self.force_yes and self.allows_prompt()


def require_selection_or_prompt(
    selection: T | None,
    picker_fn: Callable[[], T | None],
    arg_name: str,
    *,
    ctx: InteractivityContext,
) -> T:
    """Get selection from explicit arg, picker, or fail with usage error.

    This is the primary entry point for commands that support both
    explicit arguments and interactive selection. It implements the
    "graceful degradation" pattern:
    1. If explicit value provided, use it (works in all modes)
    2. If no value but interactive allowed, show picker
    3. If no value and not interactive, fail with helpful error

    Args:
        selection: Explicit value from command-line argument (None if not provided).
        picker_fn: Function to call for interactive selection.
        arg_name: Name of the argument for error messages (e.g., "team-name").
        ctx: Interactivity context with mode and flags.

    Returns:
        The selected value (from arg or picker).

    Raises:
        SystemExit: With EXIT_USAGE if selection required but interactive forbidden.
        SystemExit: With EXIT_SUCCESS (0) if user cancels picker.

    Example:
        >>> ctx = InteractivityContext.create(json_mode=False)
        >>> team = require_selection_or_prompt(
        ...     selection=args.team_name,
        ...     picker_fn=lambda: pick_team(teams),
        ...     arg_name="team-name",
        ...     ctx=ctx,
        ... )
    """
    # Case 1: Explicit selection provided - use it directly
    if selection is not None:
        return selection

    # Case 2: No selection, but interactive allowed - show picker
    if ctx.allows_prompt():
        result = picker_fn()
        if result is None:
            # User cancelled - exit cleanly
            raise SystemExit(EXIT_SUCCESS)
        return result

    # Case 3: No selection and not interactive - fail with helpful error
    _print_missing_selection_error(arg_name, ctx)
    raise SystemExit(EXIT_USAGE)


def _print_missing_selection_error(arg_name: str, ctx: InteractivityContext) -> None:
    """Print helpful error message for missing selection.

    This function implements the standard "what/why/next" error pattern:
    - What: Clear problem statement (red Error: prefix)
    - Why: Context-aware explanation (dim text explaining the cause)
    - Next: Actionable steps (bold header with bullet points)

    All user-facing validation errors in the UI module should follow
    this pattern for consistency.

    Args:
        arg_name: Name of the missing argument.
        ctx: Context for determining why interactive is blocked.
    """
    # Determine why interactive is blocked
    if ctx.is_json_output:
        why = "In JSON output mode, explicit arguments are required."
    elif _is_ci_environment():
        why = "In CI environment, interactive prompts are disabled."
    elif not _is_tty_available():
        why = "Input is not from a terminal, interactive prompts unavailable."
    else:
        why = "Interactive mode is disabled."

    _stderr_console.print(f"[red]Error:[/red] Missing required argument: --{arg_name}")
    _stderr_console.print()
    _stderr_console.print(f"[dim]{why}[/dim]")
    _stderr_console.print()
    _stderr_console.print("[bold]Next steps:[/bold]")
    _stderr_console.print(f"  • Run with --{arg_name} <value> to specify explicitly")
    _stderr_console.print("  • Run in a TTY without --json for interactive selection")
    _stderr_console.print(f"  • Run 'scc {arg_name.split('-')[0]} list' to see available options")
