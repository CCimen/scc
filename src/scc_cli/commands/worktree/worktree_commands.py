"""Worktree commands for git worktree management."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
from rich.status import Status

from ... import config, deps, docker, git
from ...cli_common import console, err_console, handle_errors
from ...confirm import Confirm
from ...core.constants import WORKTREE_BRANCH_PREFIX
from ...core.errors import NotAGitRepoError, WorkspaceNotFoundError
from ...core.exit_codes import EXIT_CANCELLED
from ...json_command import json_command
from ...kinds import Kind
from ...output_mode import is_json_mode
from ...panels import create_success_panel, create_warning_panel
from ...theme import Indicators, Spinners
from ...ui.gate import InteractivityContext
from ...ui.picker import TeamSwitchRequested, pick_worktree
from ._helpers import build_worktree_list_data

if TYPE_CHECKING:
    pass


@handle_errors
def worktree_create_cmd(
    workspace: str = typer.Argument(..., help="Path to the main repository"),
    name: str = typer.Argument(..., help="Name for the worktree/feature"),
    base_branch: str | None = typer.Option(
        None, "-b", "--base", help="Base branch (default: current)"
    ),
    start_claude: bool = typer.Option(
        True, "--start/--no-start", help="Start Claude after creating"
    ),
    install_deps: bool = typer.Option(
        False, "--install-deps", help="Install dependencies after creating worktree"
    ),
) -> None:
    """Create a new worktree for parallel development."""
    from ...cli_helpers import is_interactive

    workspace_path = Path(workspace).expanduser().resolve()

    if not workspace_path.exists():
        raise WorkspaceNotFoundError(path=str(workspace_path))

    # Handle non-git repo: offer to initialize in interactive mode
    if not git.is_git_repo(workspace_path):
        if is_interactive():
            err_console.print(f"[yellow]'{workspace_path}' is not a git repository.[/yellow]")
            if Confirm.ask("[cyan]Initialize git repository here?[/cyan]", default=True):
                if git.init_repo(workspace_path):
                    err_console.print("[green]+ Git repository initialized[/green]")
                else:
                    err_console.print("[red]Failed to initialize git repository[/red]")
                    raise typer.Exit(1)
            else:
                err_console.print("[dim]Skipped git initialization.[/dim]")
                raise typer.Exit(0)
        else:
            raise NotAGitRepoError(path=str(workspace_path))

    # Handle repo with no commits: offer to create initial commit
    if not git.has_commits(workspace_path):
        if is_interactive():
            err_console.print(
                "[yellow]Repository has no commits. Worktrees require at least one commit.[/yellow]"
            )
            if Confirm.ask("[cyan]Create an empty initial commit?[/cyan]", default=True):
                success, error_msg = git.create_empty_initial_commit(workspace_path)
                if success:
                    err_console.print("[green]+ Initial commit created[/green]")
                else:
                    err_console.print(f"[red]Failed to create commit:[/red] {error_msg}")
                    err_console.print(
                        "[dim]Fix the issue above and try again, or create a commit manually.[/dim]"
                    )
                    raise typer.Exit(1)
            else:
                err_console.print(
                    "[dim]Skipped initial commit. Create one to enable worktrees:[/dim]"
                )
                err_console.print("  [cyan]git commit --allow-empty -m 'Initial commit'[/cyan]")
                raise typer.Exit(0)
        else:
            err_console.print(
                create_warning_panel(
                    "No Commits",
                    "Repository has no commits. Worktrees require at least one commit.",
                    "Run: git commit --allow-empty -m 'Initial commit'",
                )
            )
            raise typer.Exit(1)

    worktree_path = git.create_worktree(workspace_path, name, base_branch)

    console.print(
        create_success_panel(
            "Worktree Created",
            {
                "Path": str(worktree_path),
                "Branch": f"{WORKTREE_BRANCH_PREFIX}{name}",
                "Base": base_branch or "current branch",
            },
        )
    )

    # Install dependencies if requested
    if install_deps:
        with Status(
            "[cyan]Installing dependencies...[/cyan]", console=console, spinner=Spinners.SETUP
        ):
            success = deps.auto_install_dependencies(worktree_path)
        if success:
            console.print(f"[green]{Indicators.get('PASS')} Dependencies installed[/green]")
        else:
            console.print("[yellow]! Could not detect package manager or install failed[/yellow]")

    if start_claude:
        console.print()
        if Confirm.ask("[cyan]Start Claude Code in this worktree?[/cyan]", default=True):
            docker.check_docker_available()
            # For worktrees, mount the common parent (contains .git/worktrees/)
            # but set CWD to the worktree path
            mount_path, _ = git.get_workspace_mount_path(worktree_path)
            docker_cmd, _ = docker.get_or_create_container(
                workspace=mount_path,
                branch=f"{WORKTREE_BRANCH_PREFIX}{name}",
            )
            # Load org config for safety-net policy injection
            org_config = config.load_cached_org_config()
            # Pass container_workdir explicitly for correct CWD in worktree
            docker.run(docker_cmd, org_config=org_config, container_workdir=worktree_path)


@json_command(Kind.WORKTREE_LIST)
@handle_errors
def worktree_list_cmd(
    workspace: str = typer.Argument(".", help="Path to the repository"),
    interactive: bool = typer.Option(
        False, "-i", "--interactive", help="Interactive mode: select a worktree to work with"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show git status (staged/modified/untracked)"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON (implies --json)"),
) -> dict[str, Any] | None:
    """List all worktrees for a repository.

    With -i/--interactive, select a worktree and print its path
    (useful for piping: cd $(scc worktree list -i))

    With -v/--verbose, show git status for each worktree:
      +N = staged changes, !N = modified files, ?N = untracked files
    """
    workspace_path = Path(workspace).expanduser().resolve()

    if not workspace_path.exists():
        raise WorkspaceNotFoundError(path=str(workspace_path))

    worktree_list = git.list_worktrees(workspace_path, verbose=verbose)

    # Convert WorktreeInfo dataclasses to dicts for JSON serialization
    worktree_dicts = [asdict(wt) for wt in worktree_list]
    data = build_worktree_list_data(worktree_dicts, str(workspace_path))

    if is_json_mode():
        return data

    if not worktree_list:
        console.print(
            create_warning_panel(
                "No Worktrees",
                "No worktrees found for this repository.",
                "Create one with: scc worktree create <repo> <name>",
            )
        )
        return None

    # Interactive mode: use worktree picker
    if interactive:
        try:
            selected = pick_worktree(
                worktree_list,
                title="Select Worktree",
                subtitle=f"{len(worktree_list)} worktrees in {workspace_path.name}",
            )
            if selected:
                # Print just the path for scripting: cd $(scc worktree list -i)
                print(selected.path)  # noqa: T201
        except TeamSwitchRequested:
            console.print("[dim]Use 'scc team switch' to change teams[/dim]")
        return None

    # Use the beautiful worktree rendering from git.py
    git.render_worktrees(worktree_list, console)

    return data


@handle_errors
def worktree_switch_cmd(
    target: str = typer.Argument(
        None,
        help="Target: worktree name, '-' (previous via $OLDPWD), '^' (main branch)",
    ),
    workspace: str = typer.Option(".", "-w", "--workspace", help="Path to the repository"),
) -> None:
    """Switch to a worktree. Prints path for shell integration.

    Shortcuts:
      - : Previous directory (uses shell $OLDPWD)
      ^ : Main/default branch worktree
      <name> : Fuzzy match worktree by branch or directory name

    Shell integration (add to ~/.bashrc or ~/.zshrc):
      wt() { cd "$(scc worktree switch "$@")" || return 1; }

    Examples:
      scc worktree switch feature-auth  # Switch to feature-auth worktree
      scc worktree switch -             # Switch to previous directory
      scc worktree switch ^             # Switch to main branch worktree
      scc worktree switch               # Interactive picker
    """
    import os

    workspace_path = Path(workspace).expanduser().resolve()

    if not workspace_path.exists():
        raise WorkspaceNotFoundError(path=str(workspace_path))

    if not git.is_git_repo(workspace_path):
        raise NotAGitRepoError(path=str(workspace_path))

    # No target: interactive picker
    if target is None:
        worktree_list = git.list_worktrees(workspace_path)
        if not worktree_list:
            err_console.print(
                create_warning_panel(
                    "No Worktrees",
                    "No worktrees found for this repository.",
                    "Create one with: scc worktree create <repo> <name>",
                ),
            )
            raise typer.Exit(1)

        try:
            selected = pick_worktree(
                worktree_list,
                title="Select Worktree",
                subtitle=f"{len(worktree_list)} worktrees",
            )
            if selected:
                print(selected.path)  # noqa: T201
            else:
                raise typer.Exit(EXIT_CANCELLED)
        except TeamSwitchRequested:
            err_console.print("[dim]Use 'scc team switch' to change teams[/dim]")
            raise typer.Exit(1)
        return

    # Handle special shortcuts
    if target == "-":
        # Previous directory via shell's OLDPWD
        oldpwd = os.environ.get("OLDPWD")
        if not oldpwd:
            err_console.print(
                create_warning_panel(
                    "No Previous Directory",
                    "Shell $OLDPWD is not set.",
                    "This typically means you haven't changed directories yet.",
                ),
            )
            raise typer.Exit(1)
        print(oldpwd)  # noqa: T201
        return

    if target == "^":
        # Main/default branch worktree
        main_wt = git.find_main_worktree(workspace_path)
        if not main_wt:
            default_branch = git.get_default_branch(workspace_path)
            err_console.print(
                create_warning_panel(
                    "No Main Worktree",
                    f"No worktree found for default branch '{default_branch}'.",
                    "The main branch may not have a separate worktree.",
                ),
            )
            raise typer.Exit(1)
        print(main_wt.path)  # noqa: T201
        return

    # Fuzzy match worktree
    exact_match, matches = git.find_worktree_by_query(workspace_path, target)

    if exact_match:
        print(exact_match.path)  # noqa: T201
        return

    if not matches:
        # Skip branch check for special targets (handled earlier: -, ^, @)
        if target not in ("^", "-", "@") and not target.startswith("@{"):
            # Check if EXACT branch exists without worktree
            branches = git.list_branches_without_worktrees(workspace_path)
            if target in branches:  # Exact match only - no substring matching
                ctx = InteractivityContext.create()
                if ctx.allows_prompt():
                    if Confirm.ask(
                        f"[cyan]No worktree for '{target}'. Create one?[/cyan]",
                        default=False,  # Explicit > implicit
                    ):
                        worktree_path = git.create_worktree(
                            workspace_path,
                            name=target,
                            base_branch=target,
                        )
                        print(worktree_path)  # noqa: T201
                        return
                    else:
                        # User declined - use EXIT_CANCELLED so shell wrappers don't cd
                        err_console.print("[dim]Cancelled.[/dim]")
                        raise typer.Exit(EXIT_CANCELLED)
                else:
                    # Non-interactive: hint at explicit command
                    err_console.print(
                        create_warning_panel(
                            "Branch Exists, No Worktree",
                            f"Branch '{target}' exists but has no worktree.",
                            f"Use: scc worktree create <repo> {target} --base {target}",
                        ),
                    )
                    raise typer.Exit(1)

        # Original "not found" error with select --branches hint
        err_console.print(
            create_warning_panel(
                "Worktree Not Found",
                f"No worktree matches '{target}'.",
                "Tip: Use 'scc worktree select --branches' to pick from remote branches.",
            ),
        )
        raise typer.Exit(1)

    # Multiple matches: show picker or list
    ctx = InteractivityContext.create()
    if ctx.allows_prompt():
        try:
            selected = pick_worktree(
                matches,
                title="Multiple Matches",
                subtitle=f"'{target}' matches {len(matches)} worktrees",
                initial_filter=target,
            )
            if selected:
                print(selected.path)  # noqa: T201
            else:
                raise typer.Exit(EXIT_CANCELLED)
        except TeamSwitchRequested:
            raise typer.Exit(EXIT_CANCELLED)
    else:
        # Non-interactive: print ranked matches with explicit selection commands
        match_lines = []
        for i, wt in enumerate(matches):
            display_branch = git.get_display_branch(wt.branch)
            dir_name = Path(wt.path).name
            if i == 0:
                # Highlight top match (would be auto-selected interactively)
                match_lines.append(
                    f"  1. [bold]{display_branch}[/] -> {dir_name}  [dim]<- best match[/]"
                )
            else:
                match_lines.append(f"  {i + 1}. {display_branch} -> {dir_name}")

        # Get the top match for the suggested command
        top_match_dir = Path(matches[0].path).name

        err_console.print(
            create_warning_panel(
                "Ambiguous Match",
                f"'{target}' matches {len(matches)} worktrees (ranked by relevance):",
                "\n".join(match_lines)
                + f"\n\n[dim]Use explicit directory name: scc worktree switch {top_match_dir}[/]",
            ),
        )
        raise typer.Exit(1)


@handle_errors
def worktree_select_cmd(
    workspace: str = typer.Argument(".", help="Path to the repository"),
    branches: bool = typer.Option(
        False, "-b", "--branches", help="Include branches without worktrees"
    ),
) -> None:
    """Interactive worktree selector. Prints path to stdout.

    Select a worktree from an interactive list. The selected path is printed
    to stdout for shell integration.

    With --branches, also shows remote branches that don't have worktrees.
    Selecting a branch prompts to create a new worktree.

    Shell integration (add to ~/.bashrc or ~/.zshrc):
      wt() { cd "$(scc worktree select "$@")" || return 1; }

    Examples:
      scc worktree select              # Pick from worktrees
      scc worktree select --branches   # Include branches for quick creation
    """
    workspace_path = Path(workspace).expanduser().resolve()

    if not workspace_path.exists():
        raise WorkspaceNotFoundError(path=str(workspace_path))

    if not git.is_git_repo(workspace_path):
        raise NotAGitRepoError(path=str(workspace_path))

    worktree_list = git.list_worktrees(workspace_path)

    # Build combined list if including branches
    from ...git import WorktreeInfo

    items: list[WorktreeInfo] = list(worktree_list)
    branch_items: list[str] = []

    if branches:
        branch_items = git.list_branches_without_worktrees(workspace_path)
        # Create placeholder WorktreeInfo for branches (with empty path)
        for branch in branch_items:
            items.append(
                WorktreeInfo(
                    path="",  # Empty path indicates this is a branch, not worktree
                    branch=branch,
                    status="branch",  # Mark as branch-only
                )
            )

    if not items:
        err_console.print(
            create_warning_panel(
                "No Worktrees or Branches",
                "No worktrees found and no remote branches available.",
                "Create a worktree with: scc worktree create <repo> <name>",
            ),
        )
        raise typer.Exit(1)

    try:
        selected = pick_worktree(
            items,
            title="Select Worktree",
            subtitle=f"{len(worktree_list)} worktrees"
            + (f", {len(branch_items)} branches" if branch_items else ""),
        )

        if not selected:
            raise typer.Exit(EXIT_CANCELLED)

        # If selected item is a worktree (has path), print it
        if selected.path:
            print(selected.path)  # noqa: T201
            return

        # Selected a branch without worktree - offer to create
        if Confirm.ask(
            f"[cyan]Create worktree for branch '{selected.branch}'?[/cyan]",
            default=True,
            console=console,
        ):
            with Status(
                "[cyan]Creating worktree...[/cyan]",
                console=console,
                spinner=Spinners.SETUP,
            ):
                worktree_path = git.create_worktree(
                    workspace_path,
                    selected.branch,
                    base_branch=selected.branch,
                )
            err_console.print(
                create_success_panel(
                    "Worktree Created",
                    {"Branch": selected.branch, "Path": str(worktree_path)},
                )
            )
            print(worktree_path)  # noqa: T201
        else:
            raise typer.Exit(EXIT_CANCELLED)

    except TeamSwitchRequested:
        err_console.print("[dim]Use 'scc team switch' to change teams[/dim]")
        raise typer.Exit(EXIT_CANCELLED)


@handle_errors
def worktree_enter_cmd(
    target: str = typer.Argument(
        None,
        help="Target: worktree name, '-' (previous), '^' (main branch)",
    ),
    workspace: str = typer.Option(".", "-w", "--workspace", help="Path to the repository"),
) -> None:
    """Enter a worktree in a new subshell.

    Unlike 'switch', this command opens a new shell in the worktree directory.
    No shell configuration is required - just type 'exit' to return.

    The $SCC_WORKTREE environment variable is set to the worktree name.

    Shortcuts:
      - : Previous directory (uses shell $OLDPWD)
      ^ : Main/default branch worktree
      <name> : Fuzzy match worktree by branch or directory name

    Examples:
      scc worktree enter feature-auth  # Enter feature-auth in new shell
      scc worktree enter               # Interactive picker
      scc worktree enter ^             # Enter main branch worktree
    """
    import os
    import subprocess

    workspace_path = Path(workspace).expanduser().resolve()

    if not workspace_path.exists():
        raise WorkspaceNotFoundError(path=str(workspace_path))

    if not git.is_git_repo(workspace_path):
        raise NotAGitRepoError(path=str(workspace_path))

    # Resolve target to worktree path
    worktree_path: Path | None = None
    worktree_name: str = ""

    if target is None:
        # No target: interactive picker
        worktree_list = git.list_worktrees(workspace_path)
        if not worktree_list:
            err_console.print(
                create_warning_panel(
                    "No Worktrees",
                    "No worktrees found for this repository.",
                    "Create one with: scc worktree create <repo> <name>",
                ),
            )
            raise typer.Exit(1)

        try:
            selected = pick_worktree(
                worktree_list,
                title="Enter Worktree",
                subtitle="Select a worktree to enter",
            )
            if selected:
                worktree_path = Path(selected.path)
                worktree_name = selected.branch or Path(selected.path).name
            else:
                raise typer.Exit(EXIT_CANCELLED)
        except TeamSwitchRequested:
            err_console.print("[dim]Use 'scc team switch' to change teams[/dim]")
            raise typer.Exit(1)
    elif target == "-":
        # Previous directory
        oldpwd = os.environ.get("OLDPWD")
        if not oldpwd:
            err_console.print(
                create_warning_panel(
                    "No Previous Directory",
                    "Shell $OLDPWD is not set.",
                    "This typically means you haven't changed directories yet.",
                ),
            )
            raise typer.Exit(1)
        worktree_path = Path(oldpwd)
        worktree_name = worktree_path.name
    elif target == "^":
        # Main branch worktree
        main_branch = git.get_default_branch(workspace_path)
        worktree_list = git.list_worktrees(workspace_path)
        for wt in worktree_list:
            if wt.branch == main_branch or wt.branch in {"main", "master"}:
                worktree_path = Path(wt.path)
                worktree_name = wt.branch or worktree_path.name
                break
        if not worktree_path:
            err_console.print(
                create_warning_panel(
                    "Main Branch Not Found",
                    f"No worktree found for main branch ({main_branch}).",
                    "The main worktree may be in a different location.",
                ),
            )
            raise typer.Exit(1)
    else:
        # Fuzzy match target
        matched, _matches = git.find_worktree_by_query(workspace_path, target)
        if matched:
            worktree_path = Path(matched.path)
            worktree_name = matched.branch or Path(matched.path).name
        else:
            err_console.print(
                create_warning_panel(
                    "Worktree Not Found",
                    f"No worktree matching '{target}'.",
                    "Run 'scc worktree list' to see available worktrees.",
                ),
            )
            raise typer.Exit(1)

    # Verify worktree path exists
    if not worktree_path or not worktree_path.exists():
        err_console.print(
            create_warning_panel(
                "Worktree Missing",
                f"Worktree path does not exist: {worktree_path}",
                "The worktree may have been removed. Run 'scc worktree prune'.",
            ),
        )
        raise typer.Exit(1)

    # Print entry message to stderr (stdout stays clean)
    err_console.print(f"[cyan]Entering worktree:[/cyan] {worktree_path}")
    err_console.print("[dim]Type 'exit' to return.[/dim]")
    err_console.print()

    # Set up environment with SCC_WORKTREE variable
    env = os.environ.copy()
    env["SCC_WORKTREE"] = worktree_name

    # Get user's shell (default to /bin/bash on Unix, cmd.exe on Windows)
    import platform

    if platform.system() == "Windows":
        shell = os.environ.get("COMSPEC", "cmd.exe")
    else:
        shell = os.environ.get("SHELL", "/bin/bash")

    # Run subshell in worktree directory
    try:
        subprocess.run([shell], cwd=str(worktree_path), env=env)
    except FileNotFoundError:
        err_console.print(f"[red]Shell not found: {shell}[/red]")
        raise typer.Exit(1)

    # After subshell exits, print a message
    err_console.print()
    err_console.print("[dim]Exited worktree subshell[/dim]")


@handle_errors
def worktree_remove_cmd(
    workspace: str = typer.Argument(..., help="Path to the main repository"),
    name: str = typer.Argument(..., help="Name of the worktree to remove"),
    force: bool = typer.Option(
        False, "-f", "--force", help="Force removal even with uncommitted changes"
    ),
    yes: bool = typer.Option(False, "-y", "--yes", help="Skip all confirmation prompts"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be removed without removing"
    ),
) -> None:
    """Remove a worktree.

    By default, prompts for confirmation if there are uncommitted changes and
    asks whether to delete the associated branch.

    Use --yes to skip prompts (auto-confirms all actions).
    Use --dry-run to preview what would be removed.
    Use --force to remove even with uncommitted changes (still prompts unless --yes).
    """
    workspace_path = Path(workspace).expanduser().resolve()

    if not workspace_path.exists():
        raise WorkspaceNotFoundError(path=str(workspace_path))

    # cleanup_worktree handles all output including success panels
    git.cleanup_worktree(workspace_path, name, force, console, skip_confirm=yes, dry_run=dry_run)


@handle_errors
def worktree_prune_cmd(
    workspace: str = typer.Argument(".", help="Path to the repository"),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-n", help="Show what would be pruned without pruning"
    ),
) -> None:
    """Remove stale worktree entries from git.

    Prunes worktree references for directories that no longer exist.
    Use --dry-run to preview what would be removed.
    """
    workspace_path = Path(workspace).expanduser().resolve()

    if not git.is_git_repo(workspace_path):
        raise NotAGitRepoError(path=str(workspace_path))

    cmd = ["git", "-C", str(workspace_path), "worktree", "prune"]
    if dry_run:
        cmd.append("--dry-run")
        cmd.append("--verbose")  # Show what would be pruned

    from ...subprocess_utils import run_command

    output = run_command(cmd, timeout=30)

    if output and output.strip():
        # Parse output to count pruned entries (lines containing "Removing")
        lines = output.strip().splitlines()
        prune_count = sum(1 for line in lines if "Removing" in line or "removing" in line)

        if dry_run:
            err_console.print(
                f"[yellow]Would prune {prune_count} stale worktree "
                f"{'entry' if prune_count == 1 else 'entries'}:[/yellow]"
            )
        else:
            err_console.print(
                f"[green]Pruned {prune_count} stale worktree "
                f"{'entry' if prune_count == 1 else 'entries'}.[/green]"
            )
        # Show the details
        for line in lines:
            err_console.print(f"  [dim]{line}[/dim]")
    else:
        err_console.print("[green]No stale worktree entries found.[/green]")
