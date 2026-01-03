"""Git interactive UI functions - user-facing workflows with console output.

These functions combine domain logic with Rich console output for
interactive user workflows. They use:
- services/git/ for data operations
- ui/git_render.py for pure rendering
- panels, theme for consistent styling

Extracted from git.py to achieve "no Rich imports in git.py" criterion.
"""

import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from rich import box
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from ..confirm import Confirm
from ..core.constants import WORKTREE_BRANCH_PREFIX
from ..core.errors import (
    CloneError,
    NotAGitRepoError,
    WorktreeCreationError,
    WorktreeExistsError,
)
from ..panels import (
    create_error_panel,
    create_info_panel,
    create_success_panel,
    create_warning_panel,
)
from ..services.git.branch import (
    PROTECTED_BRANCHES,
    get_current_branch,
    get_default_branch,
    get_uncommitted_files,
    sanitize_branch_name,
)
from ..services.git.core import has_remote, is_git_repo
from ..services.git.worktree import (
    WorktreeInfo,
    get_worktree_status,
    get_worktrees_data,
)
from ..theme import Indicators, Spinners
from ..utils.locks import file_lock, lock_path
from .git_render import render_worktrees_table

# ═══════════════════════════════════════════════════════════════════════════════
# Branch Safety - Interactive UI
# ═══════════════════════════════════════════════════════════════════════════════


def check_branch_safety(path: Path, console: Console) -> bool:
    """Check if current branch is safe for Claude Code work.

    Display a visual "speed bump" for protected branches with
    interactive options to create a feature branch or continue.

    Args:
        path: Path to the git repository.
        console: Rich console for output.

    Returns:
        True if safe to proceed, False if user cancelled.
    """
    if not is_git_repo(path):
        return True

    current = get_current_branch(path)

    if current in PROTECTED_BRANCHES:
        console.print()

        # Visual speed bump - warning panel
        warning = create_warning_panel(
            "Protected Branch",
            f"You are on branch '{current}'\n\n"
            "For safety, Claude Code work should happen on a feature branch.\n"
            "Direct pushes to protected branches are blocked by git hooks.",
            "Create a feature branch for isolated, safe development",
        )
        console.print(warning)
        console.print()

        # Interactive options table
        options_table = Table(
            box=box.SIMPLE,
            show_header=False,
            padding=(0, 2),
            expand=False,
        )
        options_table.add_column("Option", style="yellow", width=10)
        options_table.add_column("Action", style="white")
        options_table.add_column("Description", style="dim")

        options_table.add_row("[1]", "Create branch", "New feature branch (recommended)")
        options_table.add_row("[2]", "Continue", "Stay on protected branch (pushes blocked)")
        options_table.add_row("[3]", "Cancel", "Exit without starting")

        console.print(options_table)
        console.print()

        choice = Prompt.ask(
            "[cyan]Select option[/cyan]",
            choices=["1", "2", "3", "create", "continue", "cancel"],
            default="1",
        )

        if choice in ["1", "create"]:
            console.print()
            name = Prompt.ask("[cyan]Feature name[/cyan]")
            safe_name = sanitize_branch_name(name)
            branch_name = f"{WORKTREE_BRANCH_PREFIX}{safe_name}"

            with console.status(
                f"[cyan]Creating branch {branch_name}...[/cyan]", spinner=Spinners.SETUP
            ):
                try:
                    subprocess.run(
                        ["git", "-C", str(path), "checkout", "-b", branch_name],
                        check=True,
                        capture_output=True,
                        timeout=10,
                    )
                except subprocess.CalledProcessError:
                    console.print()
                    console.print(
                        create_error_panel(
                            "Branch Creation Failed",
                            f"Could not create branch '{branch_name}'",
                            "Check if the branch already exists or if there are uncommitted changes",
                        )
                    )
                    return False

            console.print()
            console.print(
                create_success_panel(
                    "Branch Created",
                    {
                        "Branch": branch_name,
                        "Base": current,
                    },
                )
            )
            return True

        elif choice in ["2", "continue"]:
            console.print()
            console.print(
                "[dim]→ Continuing on protected branch. "
                "Push attempts will be blocked by git hooks.[/dim]"
            )
            return True

        else:
            return False

    return True


# ═══════════════════════════════════════════════════════════════════════════════
# Worktree Operations - Beautiful UI
# ═══════════════════════════════════════════════════════════════════════════════


def create_worktree(
    repo_path: Path,
    name: str,
    base_branch: str | None = None,
    console: Console | None = None,
) -> Path:
    """Create a new git worktree with visual progress feedback.

    Args:
        repo_path: Path to the main repository.
        name: Feature name for the worktree.
        base_branch: Branch to base the worktree on (default: main/master).
        console: Rich console for output.

    Returns:
        Path to the created worktree.

    Raises:
        NotAGitRepoError: Path is not a git repository.
        WorktreeExistsError: Worktree already exists.
        WorktreeCreationError: Failed to create worktree.
    """
    if console is None:
        console = Console()

    # Validate repository
    if not is_git_repo(repo_path):
        raise NotAGitRepoError(path=str(repo_path))

    safe_name = sanitize_branch_name(name)
    if not safe_name:
        raise ValueError(f"Invalid worktree name: {name!r}")

    branch_name = f"{WORKTREE_BRANCH_PREFIX}{safe_name}"

    # Determine worktree location
    worktree_base = repo_path.parent / f"{repo_path.name}-worktrees"
    worktree_path = worktree_base / safe_name

    lock_file = lock_path("worktree", repo_path)
    with file_lock(lock_file):
        if worktree_path.exists():
            raise WorktreeExistsError(path=str(worktree_path))

        # Determine base branch
        if not base_branch:
            base_branch = get_default_branch(repo_path)

        console.print()
        console.print(
            create_info_panel(
                "Creating Worktree", f"Feature: {safe_name}", f"Location: {worktree_path}"
            )
        )
        console.print()

        worktree_created = False

        def _install_deps() -> None:
            success = install_dependencies(worktree_path, console)
            if not success:
                raise WorktreeCreationError(
                    name=safe_name,
                    user_message="Dependency install failed for the new worktree",
                    suggested_action="Install dependencies manually and retry if needed",
                )

        # Multi-step progress - conditionally include fetch if remote exists
        steps: list[tuple[str, Callable[[], None]]] = []

        # Only fetch if the repository has a remote origin
        if has_remote(repo_path):
            steps.append(("Fetching latest changes", lambda: _fetch_branch(repo_path, base_branch)))

        steps.extend(
            [
                (
                    "Creating worktree",
                    lambda: _create_worktree_dir(
                        repo_path, worktree_path, branch_name, base_branch, worktree_base
                    ),
                ),
                ("Installing dependencies", _install_deps),
            ]
        )

        try:
            for step_name, step_func in steps:
                with console.status(f"[cyan]{step_name}...[/cyan]", spinner=Spinners.SETUP):
                    try:
                        step_func()
                    except subprocess.CalledProcessError as e:
                        raise WorktreeCreationError(
                            name=safe_name,
                            command=" ".join(e.cmd) if hasattr(e, "cmd") else None,
                            stderr=e.stderr.decode() if e.stderr else None,
                        )
                console.print(f"  [green]{Indicators.get('PASS')}[/green] {step_name}")
                if step_name == "Creating worktree":
                    worktree_created = True
        except KeyboardInterrupt:
            if worktree_created or worktree_path.exists():
                _cleanup_partial_worktree(repo_path, worktree_path)
            raise
        except WorktreeCreationError:
            if worktree_created or worktree_path.exists():
                _cleanup_partial_worktree(repo_path, worktree_path)
            raise

        console.print()
        console.print(
            create_success_panel(
                "Worktree Ready",
                {
                    "Path": str(worktree_path),
                    "Branch": branch_name,
                    "Base": base_branch,
                    "Next": f"cd {worktree_path}",
                },
            )
        )

        return worktree_path


def _fetch_branch(repo_path: Path, branch: str) -> None:
    """Fetch a branch from origin.

    Raises:
        WorktreeCreationError: If fetch fails (network error, branch not found, etc.)
    """
    result = subprocess.run(
        ["git", "-C", str(repo_path), "fetch", "origin", branch],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        error_msg = result.stderr.strip() if result.stderr else "Unknown fetch error"
        lower = error_msg.lower()
        user_message = f"Failed to fetch branch '{branch}'"
        suggested_action = "Check the branch name and your network connection"

        if "couldn't find remote ref" in lower or "remote ref" in lower and "not found" in lower:
            user_message = f"Branch '{branch}' not found on origin"
            suggested_action = "Check the branch name or fetch remote branches"
        elif "could not resolve host" in lower or "failed to connect" in lower:
            user_message = "Network error while fetching from origin"
            suggested_action = "Check your network or VPN connection"
        elif "permission denied" in lower or "authentication" in lower:
            user_message = "Authentication error while fetching from origin"
            suggested_action = "Check your git credentials and remote access"

        raise WorktreeCreationError(
            name=branch,
            user_message=user_message,
            suggested_action=suggested_action,
            command=f"git -C {repo_path} fetch origin {branch}",
            stderr=error_msg,
        )


def _cleanup_partial_worktree(repo_path: Path, worktree_path: Path) -> None:
    """Best-effort cleanup for partially created worktrees."""
    try:
        subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "worktree",
                "remove",
                "--force",
                str(worktree_path),
            ],
            capture_output=True,
            timeout=30,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    shutil.rmtree(worktree_path, ignore_errors=True)

    try:
        subprocess.run(
            ["git", "-C", str(repo_path), "worktree", "prune"],
            capture_output=True,
            timeout=30,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        pass


def _create_worktree_dir(
    repo_path: Path,
    worktree_path: Path,
    branch_name: str,
    base_branch: str,
    worktree_base: Path,
) -> None:
    """Create the worktree directory."""
    worktree_base.mkdir(parents=True, exist_ok=True)

    try:
        subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "worktree",
                "add",
                "-b",
                branch_name,
                str(worktree_path),
                f"origin/{base_branch}",
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
    except subprocess.CalledProcessError:
        # Try without origin/ prefix
        subprocess.run(
            [
                "git",
                "-C",
                str(repo_path),
                "worktree",
                "add",
                "-b",
                branch_name,
                str(worktree_path),
                base_branch,
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )


def list_worktrees(
    repo_path: Path,
    console: Console | None = None,
    *,
    verbose: bool = False,
) -> list[WorktreeInfo]:
    """List all worktrees for a repository with beautiful table display.

    Args:
        repo_path: Path to the repository.
        console: Rich console for output (if None, return data only).
        verbose: If True, fetch git status for each worktree (slower).

    Returns:
        List of WorktreeInfo objects.
    """
    worktrees = get_worktrees_data(repo_path)

    # Detect current worktree
    cwd = os.getcwd()
    for wt in worktrees:
        if os.path.realpath(wt.path) == os.path.realpath(cwd):
            wt.is_current = True
            break

    # Fetch status if verbose
    if verbose:
        for wt in worktrees:
            staged, modified, untracked, timed_out = get_worktree_status(wt.path)
            wt.staged_count = staged
            wt.modified_count = modified
            wt.untracked_count = untracked
            wt.status_timed_out = timed_out
            wt.has_changes = (staged + modified + untracked) > 0

    if console is not None:
        render_worktrees_table(worktrees, console, verbose=verbose)

        # Summary if any timed out (only when verbose and console provided)
        if verbose:
            timeout_count = sum(1 for wt in worktrees if wt.status_timed_out)
            if timeout_count > 0:
                console.print(
                    f"[dim]Note: {timeout_count} worktree(s) timed out computing status.[/dim]",
                )

    return worktrees


def cleanup_worktree(
    repo_path: Path,
    name: str,
    force: bool,
    console: Console,
    *,
    skip_confirm: bool = False,
    dry_run: bool = False,
) -> bool:
    """Clean up a worktree with safety checks and visual feedback.

    Show uncommitted changes before deletion to prevent accidental data loss.

    Args:
        repo_path: Path to the main repository.
        name: Name of the worktree to remove.
        force: If True, remove even if worktree has uncommitted changes.
        console: Rich console for output.
        skip_confirm: If True, skip interactive confirmations (--yes flag).
        dry_run: If True, show what would be removed but don't actually remove.

    Returns:
        True if worktree was removed (or would be in dry-run mode), False otherwise.
    """
    safe_name = sanitize_branch_name(name)
    branch_name = f"{WORKTREE_BRANCH_PREFIX}{safe_name}"
    worktree_base = repo_path.parent / f"{repo_path.name}-worktrees"
    worktree_path = worktree_base / safe_name

    if not worktree_path.exists():
        console.print()
        console.print(
            create_warning_panel(
                "Worktree Not Found",
                f"No worktree found at: {worktree_path}",
                "Use 'scc worktrees <repo>' to list available worktrees",
            )
        )
        return False

    console.print()
    if dry_run:
        console.print(
            create_info_panel(
                "Dry Run: Cleanup Worktree",
                f"Worktree: {safe_name}",
                f"Path: {worktree_path}",
            )
        )
    else:
        console.print(
            create_info_panel(
                "Cleanup Worktree", f"Worktree: {safe_name}", f"Path: {worktree_path}"
            )
        )
    console.print()

    # Check for uncommitted changes - show evidence
    if not force:
        uncommitted = get_uncommitted_files(worktree_path)

        if uncommitted:
            # Build a tree of files that will be lost
            tree = Tree(f"[red bold]Uncommitted Changes ({len(uncommitted)})[/red bold]")

            for f in uncommitted[:10]:  # Show max 10
                tree.add(Text(f, style="dim"))

            if len(uncommitted) > 10:
                tree.add(Text(f"...and {len(uncommitted) - 10} more", style="dim italic"))

            console.print(tree)
            console.print()
            console.print("[red bold]These changes will be permanently lost.[/red bold]")
            console.print()

            # Skip confirmation prompt if --yes was provided
            if not skip_confirm:
                if not Confirm.ask("[yellow]Delete worktree anyway?[/yellow]", default=False):
                    console.print("[dim]Cleanup cancelled.[/dim]")
                    return False

    # Dry run: show what would be removed without actually removing
    if dry_run:
        console.print("  [cyan]Would remove:[/cyan]")
        console.print(f"    - Worktree: {worktree_path}")
        console.print(f"    - Branch: {branch_name} [dim](if confirmed)[/dim]")
        console.print()
        console.print("[dim]Dry run complete. No changes made.[/dim]")
        return True

    # Remove worktree
    with console.status("[cyan]Removing worktree...[/cyan]", spinner=Spinners.DEFAULT):
        try:
            force_flag = ["--force"] if force else []
            subprocess.run(
                ["git", "-C", str(repo_path), "worktree", "remove", str(worktree_path)]
                + force_flag,
                check=True,
                capture_output=True,
                timeout=30,
            )
        except subprocess.CalledProcessError:
            # Fallback: manual removal
            shutil.rmtree(worktree_path, ignore_errors=True)
            subprocess.run(
                ["git", "-C", str(repo_path), "worktree", "prune"],
                capture_output=True,
                timeout=10,
            )

    console.print(f"  [green]{Indicators.get('PASS')}[/green] Worktree removed")

    # Ask about branch deletion (auto-delete if --yes was provided)
    console.print()
    branch_deleted = False
    should_delete_branch = skip_confirm or Confirm.ask(
        f"[cyan]Also delete branch '{branch_name}'?[/cyan]", default=False
    )
    if should_delete_branch:
        with console.status("[cyan]Deleting branch...[/cyan]", spinner=Spinners.DEFAULT):
            subprocess.run(
                ["git", "-C", str(repo_path), "branch", "-D", branch_name],
                capture_output=True,
                timeout=10,
            )
        console.print(f"  [green]{Indicators.get('PASS')}[/green] Branch deleted")
        branch_deleted = True

    console.print()
    console.print(
        create_success_panel(
            "Cleanup Complete",
            {
                "Removed": str(worktree_path),
                "Branch": "deleted" if branch_deleted else "kept",
            },
        )
    )

    return True


# ═══════════════════════════════════════════════════════════════════════════════
# Dependency Installation
# ═══════════════════════════════════════════════════════════════════════════════


def _run_install_cmd(
    cmd: list[str],
    path: Path,
    console: Console | None,
    timeout: int = 300,
) -> bool:
    """Run an install command and warn on failure. Returns True if successful."""
    try:
        result = subprocess.run(cmd, cwd=path, capture_output=True, text=True, timeout=timeout)
        if result.returncode != 0 and console:
            error_detail = result.stderr.strip() if result.stderr else ""
            message = f"'{' '.join(cmd)}' failed with exit code {result.returncode}"
            if error_detail:
                message += f": {error_detail[:100]}"  # Truncate long errors
            console.print(
                create_warning_panel(
                    "Dependency Install Warning",
                    message,
                    "You may need to install dependencies manually",
                )
            )
            return False
        return True
    except subprocess.TimeoutExpired:
        if console:
            console.print(
                create_warning_panel(
                    "Dependency Install Timeout",
                    f"'{' '.join(cmd)}' timed out after {timeout}s",
                    "You may need to install dependencies manually",
                )
            )
        return False


def install_dependencies(path: Path, console: Console | None = None) -> bool:
    """Detect and install project dependencies.

    Support Node.js (npm/yarn/pnpm/bun), Python (pip/poetry/uv), and
    Java (Maven/Gradle). Warn user if any install fails rather than
    silently ignoring.

    Args:
        path: Path to the project directory.
        console: Rich console for output (optional).
    """
    success = True

    # Node.js
    if (path / "package.json").exists():
        if (path / "pnpm-lock.yaml").exists():
            cmd = ["pnpm", "install"]
        elif (path / "bun.lockb").exists():
            cmd = ["bun", "install"]
        elif (path / "yarn.lock").exists():
            cmd = ["yarn", "install"]
        else:
            cmd = ["npm", "install"]

        success = _run_install_cmd(cmd, path, console, timeout=300) and success

    # Python
    if (path / "pyproject.toml").exists():
        if shutil.which("poetry"):
            success = (
                _run_install_cmd(["poetry", "install"], path, console, timeout=300) and success
            )
        elif shutil.which("uv"):
            success = (
                _run_install_cmd(["uv", "pip", "install", "-e", "."], path, console, timeout=300)
                and success
            )
    elif (path / "requirements.txt").exists():
        success = (
            _run_install_cmd(
                ["pip", "install", "-r", "requirements.txt"],
                path,
                console,
                timeout=300,
            )
            and success
        )

    # Java/Maven
    if (path / "pom.xml").exists():
        success = (
            _run_install_cmd(["mvn", "dependency:resolve"], path, console, timeout=600) and success
        )

    # Java/Gradle
    if (path / "build.gradle").exists() or (path / "build.gradle.kts").exists():
        gradle_cmd = "./gradlew" if (path / "gradlew").exists() else "gradle"
        success = (
            _run_install_cmd([gradle_cmd, "dependencies"], path, console, timeout=600) and success
        )

    return success


# ═══════════════════════════════════════════════════════════════════════════════
# Repository Cloning
# ═══════════════════════════════════════════════════════════════════════════════


def clone_repo(url: str, base_path: str, console: Console | None = None) -> str:
    """Clone a repository with progress feedback.

    Args:
        url: Repository URL (HTTPS or SSH).
        base_path: Base directory for cloning.
        console: Rich console for output.

    Returns:
        Path to the cloned repository.

    Raises:
        CloneError: Failed to clone repository.
    """
    if console is None:
        console = Console()

    base = Path(base_path).expanduser()
    base.mkdir(parents=True, exist_ok=True)

    # Extract repo name from URL
    name = url.rstrip("/").split("/")[-1]
    if name.endswith(".git"):
        name = name[:-4]

    target = base / name

    if target.exists():
        # Already cloned
        console.print(f"[dim]Repository already exists at {target}[/dim]")
        return str(target)

    console.print()
    console.print(create_info_panel("Cloning Repository", url, f"Target: {target}"))
    console.print()

    with console.status("[cyan]Cloning...[/cyan]", spinner=Spinners.NETWORK):
        try:
            subprocess.run(
                ["git", "clone", url, str(target)],
                check=True,
                capture_output=True,
                timeout=300,
            )
        except subprocess.CalledProcessError as e:
            raise CloneError(
                url=url,
                command=f"git clone {url}",
                stderr=e.stderr.decode() if e.stderr else None,
            )

    console.print(f"  [green]{Indicators.get('PASS')}[/green] Repository cloned")
    console.print()
    console.print(
        create_success_panel(
            "Clone Complete",
            {
                "Repository": name,
                "Path": str(target),
            },
        )
    )

    return str(target)


# ═══════════════════════════════════════════════════════════════════════════════
# Git Hooks Installation
# ═══════════════════════════════════════════════════════════════════════════════


def install_hooks(console: Console) -> None:
    """Install global git hooks for branch protection.

    Configure the global core.hooksPath and install a pre-push hook
    that prevents direct pushes to protected branches.

    Args:
        console: Rich console for output.
    """

    hooks_dir = Path.home() / ".config" / "git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    pre_push_content = """#!/bin/bash
# SCC - Pre-push hook
# Prevents direct pushes to protected branches

PROTECTED_BRANCHES="main master develop production staging"

current_branch=$(git symbolic-ref HEAD 2>/dev/null | sed -e 's,.*/\\(.*\\),\\1,')

for protected in $PROTECTED_BRANCHES; do
    if [ "$current_branch" = "$protected" ]; then
        echo ""
        echo "BLOCKED: Direct push to '$protected' is not allowed"
        echo ""
        echo "Please push to a feature branch instead:"
        echo "  git checkout -b scc/<feature-name>"
        echo "  git push -u origin scc/<feature-name>"
        echo ""
        exit 1
    fi
done

while read local_ref local_sha remote_ref remote_sha; do
    remote_branch=$(echo "$remote_ref" | sed -e 's,.*/\\(.*\\),\\1,')

    for protected in $PROTECTED_BRANCHES; do
        if [ "$remote_branch" = "$protected" ]; then
            echo ""
            echo "BLOCKED: Push to protected branch '$protected'"
            echo ""
            exit 1
        fi
    done
done

exit 0
"""

    pre_push_path = hooks_dir / "pre-push"

    console.print()
    console.print(
        create_info_panel(
            "Installing Git Hooks",
            "Branch protection hooks will be installed globally",
            f"Location: {hooks_dir}",
        )
    )
    console.print()

    with console.status("[cyan]Installing hooks...[/cyan]", spinner=Spinners.SETUP):
        pre_push_path.write_text(pre_push_content)
        pre_push_path.chmod(0o755)

        # Configure git to use global hooks
        subprocess.run(
            ["git", "config", "--global", "core.hooksPath", str(hooks_dir)],
            capture_output=True,
        )

    console.print(f"  [green]{Indicators.get('PASS')}[/green] Pre-push hook installed")
    console.print()
    console.print(
        create_success_panel(
            "Hooks Installed",
            {
                "Location": str(hooks_dir),
                "Protected branches": "main, master, develop, production, staging",
            },
        )
    )
