"""Worktree commands for git worktree management."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer
from rich.status import Status

from ... import config
from ...application import worktree as worktree_use_cases
from ...application.start_session import (
    StartSessionDependencies,
    StartSessionRequest,
    prepare_start_session,
    start_session,
)
from ...bootstrap import get_default_adapters
from ...cli_common import console, err_console, handle_errors
from ...confirm import Confirm
from ...core.constants import WORKTREE_BRANCH_PREFIX
from ...core.errors import NotAGitRepoError, WorkspaceNotFoundError
from ...core.exit_codes import EXIT_CANCELLED
from ...git import WorktreeInfo
from ...json_command import json_command
from ...kinds import Kind
from ...marketplace.materialize import materialize_marketplace
from ...marketplace.resolve import resolve_effective_config
from ...output_mode import is_json_mode
from ...panels import create_success_panel, create_warning_panel
from ...theme import Indicators, Spinners
from ...ui import cleanup_worktree, render_worktrees
from ...ui.gate import InteractivityContext
from ...ui.picker import TeamSwitchRequested, pick_worktree
from ._helpers import build_worktree_list_data

if TYPE_CHECKING:
    pass


def _build_worktree_dependencies() -> tuple[worktree_use_cases.WorktreeDependencies, Any]:
    adapters = get_default_adapters()
    dependencies = worktree_use_cases.WorktreeDependencies(
        git_client=adapters.git_client,
        dependency_installer=adapters.dependency_installer,
    )
    return dependencies, adapters


def _to_worktree_info(summary: worktree_use_cases.WorktreeSummary) -> WorktreeInfo:
    return WorktreeInfo(
        path=str(summary.path),
        branch=summary.branch,
        status=summary.status,
        is_current=summary.is_current,
        has_changes=summary.has_changes,
        staged_count=summary.staged_count,
        modified_count=summary.modified_count,
        untracked_count=summary.untracked_count,
        status_timed_out=summary.status_timed_out,
    )


def _serialize_worktree_summary(summary: worktree_use_cases.WorktreeSummary) -> dict[str, Any]:
    return {
        "path": str(summary.path),
        "branch": summary.branch,
        "status": summary.status,
        "is_current": summary.is_current,
        "has_changes": summary.has_changes,
        "staged_count": summary.staged_count,
        "modified_count": summary.modified_count,
        "untracked_count": summary.untracked_count,
        "status_timed_out": summary.status_timed_out,
    }


def _prompt_for_worktree(
    prompt: worktree_use_cases.WorktreeSelectionPrompt,
) -> worktree_use_cases.WorktreeSelectionItem | None:
    items = [option.value for option in prompt.request.options if option.value is not None]
    worktree_infos: list[WorktreeInfo] = []
    for item in items:
        if item.worktree is None:
            worktree_infos.append(WorktreeInfo(path="", branch=item.branch, status="branch"))
            continue
        worktree_infos.append(_to_worktree_info(item.worktree))

    selected = pick_worktree(
        worktree_infos,
        title=prompt.request.title,
        subtitle=prompt.request.subtitle,
        initial_filter=prompt.initial_filter,
    )
    if selected is None:
        return None

    try:
        index = worktree_infos.index(selected)
    except ValueError:
        return None
    if index >= len(items):
        return None
    return items[index]


def _render_worktree_ready(result: worktree_use_cases.WorktreeCreateResult) -> None:
    console.print()
    console.print(
        create_success_panel(
            "Worktree Ready",
            {
                "Path": str(result.worktree_path),
                "Branch": result.branch_name,
                "Base": result.base_branch,
                "Next": f"cd {result.worktree_path}",
            },
        )
    )


def _raise_worktree_warning(outcome: worktree_use_cases.WorktreeWarningOutcome) -> None:
    if outcome.warning.title == "Cancelled":
        err_console.print("[dim]Cancelled.[/dim]")
        raise typer.Exit(outcome.exit_code)
    hint = outcome.warning.suggestion or ""
    err_console.print(create_warning_panel(outcome.warning.title, outcome.warning.message, hint))
    raise typer.Exit(outcome.exit_code)


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

    dependencies, adapters = _build_worktree_dependencies()
    git_client = dependencies.git_client

    # Handle non-git repo: offer to initialize in interactive mode
    if not git_client.is_git_repo(workspace_path):
        if is_interactive():
            err_console.print(f"[yellow]'{workspace_path}' is not a git repository.[/yellow]")
            if Confirm.ask("[cyan]Initialize git repository here?[/cyan]", default=True):
                if git_client.init_repo(workspace_path):
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
    if not git_client.has_commits(workspace_path):
        if is_interactive():
            err_console.print(
                "[yellow]Repository has no commits. Worktrees require at least one commit.[/yellow]"
            )
            if Confirm.ask("[cyan]Create an empty initial commit?[/cyan]", default=True):
                success, error_msg = git_client.create_empty_initial_commit(workspace_path)
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

    result = worktree_use_cases.create_worktree(
        worktree_use_cases.WorktreeCreateRequest(
            workspace_path=workspace_path,
            name=name,
            base_branch=base_branch,
            install_dependencies=True,
        ),
        dependencies=dependencies,
    )

    _render_worktree_ready(result)

    console.print(
        create_success_panel(
            "Worktree Created",
            {
                "Path": str(result.worktree_path),
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
            install_result = dependencies.dependency_installer.install(result.worktree_path)
        if install_result.success:
            console.print(f"[green]{Indicators.get('PASS')} Dependencies installed[/green]")
        else:
            console.print("[yellow]! Could not detect package manager or install failed[/yellow]")

    if start_claude:
        console.print()
        if Confirm.ask("[cyan]Start Claude Code in this worktree?[/cyan]", default=True):
            adapters.sandbox_runtime.ensure_available()
            start_dependencies = StartSessionDependencies(
                filesystem=adapters.filesystem,
                remote_fetcher=adapters.remote_fetcher,
                clock=adapters.clock,
                git_client=adapters.git_client,
                agent_runner=adapters.agent_runner,
                sandbox_runtime=adapters.sandbox_runtime,
                resolve_effective_config=resolve_effective_config,
                materialize_marketplace=materialize_marketplace,
            )
            start_request = StartSessionRequest(
                workspace_path=result.worktree_path,
                workspace_arg=str(result.worktree_path),
                entry_dir=result.worktree_path,
                team=None,
                session_name=None,
                resume=False,
                fresh=False,
                offline=False,
                standalone=config.is_standalone_mode(),
                dry_run=False,
                allow_suspicious=False,
                org_config=config.load_cached_org_config(),
            )
            start_plan = prepare_start_session(start_request, dependencies=start_dependencies)
            start_session(start_plan, dependencies=start_dependencies)


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

    dependencies, _ = _build_worktree_dependencies()
    result = worktree_use_cases.list_worktrees(
        worktree_use_cases.WorktreeListRequest(
            workspace_path=workspace_path,
            verbose=verbose,
            current_dir=Path.cwd(),
        ),
        git_client=dependencies.git_client,
    )

    worktree_dicts = [_serialize_worktree_summary(summary) for summary in result.worktrees]
    data = build_worktree_list_data(worktree_dicts, str(workspace_path))

    if is_json_mode():
        return data

    if not result.worktrees:
        console.print(
            create_warning_panel(
                "No Worktrees",
                "No worktrees found for this repository.",
                "Create one with: scc worktree create <repo> <name>",
            )
        )
        return None

    worktree_infos = [_to_worktree_info(summary) for summary in result.worktrees]

    # Interactive mode: use worktree picker
    if interactive:
        try:
            selected = pick_worktree(
                worktree_infos,
                title="Select Worktree",
                subtitle=f"{len(worktree_infos)} worktrees in {workspace_path.name}",
            )
            if selected:
                # Print just the path for scripting: cd $(scc worktree list -i)
                print(selected.path)  # noqa: T201
        except TeamSwitchRequested:
            console.print("[dim]Use 'scc team switch' to change teams[/dim]")
        return None

    # Use the worktree rendering from the UI layer
    render_worktrees(worktree_infos, console)

    return data


@handle_errors
def worktree_switch_cmd(
    target: str | None = typer.Argument(
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

    dependencies, _ = _build_worktree_dependencies()
    ctx = InteractivityContext.create()
    oldpwd = os.environ.get("OLDPWD")
    selection: worktree_use_cases.WorktreeSelectionItem | None = None

    request = worktree_use_cases.WorktreeSwitchRequest(
        workspace_path=workspace_path,
        target=target,
        oldpwd=oldpwd,
        interactive_allowed=ctx.allows_prompt(),
        current_dir=Path.cwd(),
    )

    while True:
        outcome = worktree_use_cases.switch_worktree(request, dependencies=dependencies)

        if isinstance(outcome, worktree_use_cases.WorktreeSelectionPrompt):
            try:
                selection = _prompt_for_worktree(outcome)
            except TeamSwitchRequested:
                err_console.print("[dim]Use 'scc team switch' to change teams[/dim]")
                raise typer.Exit(EXIT_CANCELLED)
            if selection is None:
                raise typer.Exit(EXIT_CANCELLED)
            request = worktree_use_cases.WorktreeSwitchRequest(
                workspace_path=workspace_path,
                target=target,
                oldpwd=oldpwd,
                interactive_allowed=ctx.allows_prompt(),
                current_dir=Path.cwd(),
                selection=selection,
            )
            continue

        if isinstance(outcome, worktree_use_cases.WorktreeConfirmation):
            confirmed = Confirm.ask(
                f"[cyan]{outcome.request.prompt}[/cyan]",
                default=outcome.default_response,
            )
            request = worktree_use_cases.WorktreeSwitchRequest(
                workspace_path=workspace_path,
                target=target,
                oldpwd=oldpwd,
                interactive_allowed=ctx.allows_prompt(),
                current_dir=Path.cwd(),
                confirm_create=confirmed,
            )
            continue

        if isinstance(outcome, worktree_use_cases.WorktreeCreateResult):
            _render_worktree_ready(outcome)
            print(outcome.worktree_path)  # noqa: T201
            return

        if isinstance(outcome, worktree_use_cases.WorktreeResolution):
            print(outcome.worktree_path)  # noqa: T201
            return

        if isinstance(outcome, worktree_use_cases.WorktreeWarningOutcome):
            _raise_worktree_warning(outcome)


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

    dependencies, _ = _build_worktree_dependencies()
    selection: worktree_use_cases.WorktreeSelectionItem | None = None

    request = worktree_use_cases.WorktreeSelectRequest(
        workspace_path=workspace_path,
        include_branches=branches,
        current_dir=Path.cwd(),
    )

    while True:
        outcome = worktree_use_cases.select_worktree(request, dependencies=dependencies)

        if isinstance(outcome, worktree_use_cases.WorktreeSelectionPrompt):
            try:
                selection = _prompt_for_worktree(outcome)
            except TeamSwitchRequested:
                err_console.print("[dim]Use 'scc team switch' to change teams[/dim]")
                raise typer.Exit(EXIT_CANCELLED)
            if selection is None:
                raise typer.Exit(EXIT_CANCELLED)
            request = worktree_use_cases.WorktreeSelectRequest(
                workspace_path=workspace_path,
                include_branches=branches,
                current_dir=Path.cwd(),
                selection=selection,
            )
            continue

        if isinstance(outcome, worktree_use_cases.WorktreeConfirmation):
            if selection is None:
                raise ValueError("Selection required to confirm worktree creation")
            confirmed = Confirm.ask(
                f"[cyan]{outcome.request.prompt}[/cyan]",
                default=outcome.default_response,
                console=console,
            )
            request = worktree_use_cases.WorktreeSelectRequest(
                workspace_path=workspace_path,
                include_branches=branches,
                current_dir=Path.cwd(),
                selection=selection,
                confirm_create=confirmed,
            )
            continue

        if isinstance(outcome, worktree_use_cases.WorktreeCreateResult):
            _render_worktree_ready(outcome)
            branch_label = selection.branch if selection is not None else outcome.worktree_name
            err_console.print(
                create_success_panel(
                    "Worktree Created",
                    {"Branch": branch_label, "Path": str(outcome.worktree_path)},
                )
            )
            print(outcome.worktree_path)  # noqa: T201
            return

        if isinstance(outcome, worktree_use_cases.WorktreeResolution):
            print(outcome.worktree_path)  # noqa: T201
            return

        if isinstance(outcome, worktree_use_cases.WorktreeWarningOutcome):
            _raise_worktree_warning(outcome)


@handle_errors
def worktree_enter_cmd(
    target: str | None = typer.Argument(
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
    import platform
    import subprocess

    workspace_path = Path(workspace).expanduser().resolve()

    if not workspace_path.exists():
        raise WorkspaceNotFoundError(path=str(workspace_path))

    dependencies, _ = _build_worktree_dependencies()
    ctx = InteractivityContext.create()
    selection: worktree_use_cases.WorktreeSelectionItem | None = None

    request = worktree_use_cases.WorktreeEnterRequest(
        workspace_path=workspace_path,
        target=target,
        oldpwd=os.environ.get("OLDPWD"),
        interactive_allowed=ctx.allows_prompt(),
        current_dir=Path.cwd(),
        env=dict(os.environ),
        platform_system=platform.system(),
    )

    while True:
        outcome = worktree_use_cases.enter_worktree_shell(request, dependencies=dependencies)

        if isinstance(outcome, worktree_use_cases.WorktreeSelectionPrompt):
            try:
                selection = _prompt_for_worktree(outcome)
            except TeamSwitchRequested:
                err_console.print("[dim]Use 'scc team switch' to change teams[/dim]")
                raise typer.Exit(1)
            if selection is None:
                raise typer.Exit(EXIT_CANCELLED)
            request = worktree_use_cases.WorktreeEnterRequest(
                workspace_path=workspace_path,
                target=target,
                oldpwd=request.oldpwd,
                interactive_allowed=ctx.allows_prompt(),
                current_dir=Path.cwd(),
                env=request.env,
                platform_system=request.platform_system,
                selection=selection,
            )
            continue

        if isinstance(outcome, worktree_use_cases.WorktreeWarningOutcome):
            _raise_worktree_warning(outcome)

        if isinstance(outcome, worktree_use_cases.WorktreeShellResult):
            worktree_path = outcome.worktree_path
            err_console.print(f"[cyan]Entering worktree:[/cyan] {worktree_path}")
            err_console.print("[dim]Type 'exit' to return.[/dim]")
            err_console.print()

            try:
                subprocess.run(
                    outcome.shell_command.argv,
                    cwd=str(outcome.shell_command.workdir),
                    env=outcome.shell_command.env,
                )
            except FileNotFoundError:
                shell = outcome.shell_command.argv[0]
                err_console.print(f"[red]Shell not found: {shell}[/red]")
                raise typer.Exit(1)

            err_console.print()
            err_console.print("[dim]Exited worktree subshell[/dim]")
            return


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
    cleanup_worktree(workspace_path, name, force, console, skip_confirm=yes, dry_run=dry_run)


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

    dependencies, _ = _build_worktree_dependencies()
    if not dependencies.git_client.is_git_repo(workspace_path):
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
