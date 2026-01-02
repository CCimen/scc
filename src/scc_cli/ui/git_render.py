"""Git rendering functions - pure UI components for git data display.

Pure functions with no side effects beyond console output. These take
data structures (like WorktreeInfo) and render them to Rich consoles.

Extracted from git.py to separate rendering from domain logic.
"""

from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from ..panels import create_warning_panel
from ..services.git.branch import PROTECTED_BRANCHES, get_display_branch
from ..services.git.worktree import WorktreeInfo


def format_git_status(wt: WorktreeInfo) -> Text:
    """Format git status as compact symbols: +N!N?N, . for clean, or ... for timeout.

    Args:
        wt: WorktreeInfo object with status fields populated.

    Returns:
        Rich Text with styled git status symbols.
    """
    # Show ellipsis if status timed out
    if wt.status_timed_out:
        return Text("...", style="dim")

    if wt.staged_count == 0 and wt.modified_count == 0 and wt.untracked_count == 0:
        return Text(".", style="green")

    parts = Text()
    if wt.staged_count > 0:
        parts.append(f"+{wt.staged_count}", style="green")
    if wt.modified_count > 0:
        parts.append(f"!{wt.modified_count}", style="yellow")
    if wt.untracked_count > 0:
        parts.append(f"?{wt.untracked_count}", style="dim")
    return parts


def render_worktrees_table(
    worktrees: list[WorktreeInfo],
    console: Console,
    *,
    verbose: bool = False,
) -> None:
    """Render worktrees in a responsive table.

    Args:
        worktrees: List of WorktreeInfo objects to display.
        console: Rich console for output.
        verbose: If True, show git status symbols.
    """
    if not worktrees:
        console.print()
        console.print(
            create_warning_panel(
                "No Worktrees",
                "No git worktrees found for this repository.",
                "Create one with: scc worktree <repo> <feature-name>",
            )
        )
        return

    console.print()

    # Responsive: check terminal width
    width = console.width
    wide_mode = width >= 110

    # Create table with adaptive columns
    table = Table(
        title="[bold cyan]Git Worktrees[/bold cyan]",
        box=box.ROUNDED,
        header_style="bold cyan",
        show_lines=False,
        expand=True,
        padding=(0, 1),
    )

    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("Branch", style="cyan", no_wrap=True)

    if verbose:
        table.add_column("Status", no_wrap=True, width=10)

    if wide_mode:
        table.add_column("Path", style="dim", overflow="ellipsis", ratio=2)
        if not verbose:
            table.add_column("Status", style="dim", no_wrap=True, width=12)
    else:
        table.add_column("Path", style="dim", overflow="ellipsis", max_width=40)

    for idx, wt in enumerate(worktrees, 1):
        # Style the branch name with @ prefix for current
        is_detached = not wt.branch
        is_protected = wt.branch in PROTECTED_BRANCHES if wt.branch else False
        # Use display-friendly name (strip SCC prefix)
        branch_value = get_display_branch(wt.branch) if wt.branch else "detached"

        # Add @ prefix for current worktree
        if wt.is_current:
            branch_display = Text("@ ", style="green bold")
            branch_display.append(branch_value, style="cyan bold")
        elif is_protected or is_detached:
            branch_display = Text(branch_value, style="yellow")
        else:
            branch_display = Text(branch_value, style="cyan")

        # Determine text status (for non-verbose wide mode)
        text_status = wt.status or ("detached" if is_detached else "active")
        if is_protected:
            text_status = "protected"

        status_style = {
            "active": "green",
            "protected": "yellow",
            "detached": "yellow",
            "bare": "dim",
        }.get(text_status, "dim")

        if verbose:
            # Verbose mode: show git status symbols
            git_status = format_git_status(wt)
            if wide_mode:
                table.add_row(
                    str(idx),
                    branch_display,
                    git_status,
                    wt.path,
                )
            else:
                table.add_row(
                    str(idx),
                    branch_display,
                    git_status,
                    wt.path,
                )
        elif wide_mode:
            table.add_row(
                str(idx),
                branch_display,
                wt.path,
                Text(text_status, style=status_style),
            )
        else:
            table.add_row(
                str(idx),
                branch_display,
                wt.path,
            )

    console.print(table)
    console.print()


def render_worktrees(
    worktrees: list[WorktreeInfo],
    console: Console,
    *,
    verbose: bool = False,
) -> None:
    """Render worktrees with beautiful formatting.

    Public interface used by cli.py for consistent styling across the application.

    Args:
        worktrees: List of WorktreeInfo objects to display.
        console: Rich console for output.
        verbose: If True, show git status symbols.
    """
    render_worktrees_table(worktrees, console, verbose=verbose)
