"""
Git operations including worktree management and safety checks.

UI Philosophy:
- Consistent visual language with semantic colors
- Responsive layouts (80-120+ columns)
- Clear hierarchy: errors > warnings > info > success
- Interactive flows with visual "speed bumps" for dangerous ops
"""

import subprocess
import shutil
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich import box

from .errors import (
    GitNotFoundError,
    NotAGitRepoError,
    CloneError,
    WorktreeExistsError,
    WorktreeCreationError,
    GitWorktreeError,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

PROTECTED_BRANCHES = ["main", "master", "develop", "production", "staging"]
BRANCH_PREFIX = "claude/"


# ═══════════════════════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class WorktreeInfo:
    """Information about a git worktree."""
    path: str
    branch: str
    status: str = ""
    is_current: bool = False
    has_changes: bool = False


# ═══════════════════════════════════════════════════════════════════════════════
# UI Helpers - Aesthetic Components
# ═══════════════════════════════════════════════════════════════════════════════

def _render_branch_badge(branch: str, is_protected: bool = False, is_current: bool = False) -> Text:
    """Render a styled branch name badge."""
    text = Text()
    if is_current:
        text.append("● ", style="green")
    if is_protected:
        text.append(branch, style="bold yellow")
        text.append(" ", style="dim")
        text.append("protected", style="dim yellow")
    else:
        text.append(branch, style="cyan")
    return text


def _render_path_truncated(path: str, max_width: int = 50) -> Text:
    """Render a path with smart truncation from the left."""
    if len(path) <= max_width:
        return Text(path, style="dim")
    # Truncate from left, keep the meaningful part
    truncated = "…" + path[-(max_width - 1):]
    return Text(truncated, style="dim")


def _create_info_panel(title: str, content: str, subtitle: str = "") -> Panel:
    """Create an info panel with cyan styling."""
    body = Text()
    body.append(content)
    if subtitle:
        body.append("\n")
        body.append(subtitle, style="dim")
    return Panel(
        body,
        title=f"[bold cyan]{title}[/bold cyan]",
        border_style="cyan",
        padding=(0, 1),
    )


def _create_warning_panel(title: str, message: str, hint: str = "") -> Panel:
    """Create a warning panel with yellow styling."""
    body = Text()
    body.append(message, style="bold")
    if hint:
        body.append("\n\n")
        body.append("→ ", style="dim")
        body.append(hint, style="yellow")
    return Panel(
        body,
        title=f"[bold yellow]⚠ {title}[/bold yellow]",
        border_style="yellow",
        padding=(0, 1),
    )


def _create_success_panel(title: str, items: dict) -> Panel:
    """Create a success panel with key-value summary."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim", no_wrap=True)
    grid.add_column(style="white")

    for key, value in items.items():
        grid.add_row(f"{key}:", str(value))

    return Panel(
        grid,
        title=f"[bold green]✓ {title}[/bold green]",
        border_style="green",
        padding=(0, 1),
    )


def _create_error_panel(title: str, message: str, hint: str = "") -> Panel:
    """Create an error panel with red styling."""
    body = Text()
    body.append(message, style="bold")
    if hint:
        body.append("\n\n")
        body.append("→ Fix: ", style="green")
        body.append(hint)
    return Panel(
        body,
        title=f"[bold red]✖ {title}[/bold red]",
        border_style="red",
        padding=(0, 1),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Git Detection & Basic Operations
# ═══════════════════════════════════════════════════════════════════════════════

def check_git_available() -> None:
    """
    Check if Git is installed and available.

    Raises:
        GitNotFoundError: Git is not installed or not in PATH
    """
    if shutil.which("git") is None:
        raise GitNotFoundError()


def check_git_installed() -> bool:
    """Check if Git is installed (boolean for doctor command)."""
    return shutil.which("git") is not None


def get_git_version() -> Optional[str]:
    """Get Git version string for display."""
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            # Returns something like "git version 2.40.0"
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def is_git_repo(path: Path) -> bool:
    """Check if path is inside a git repository."""
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--git-dir"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_current_branch(path: Path) -> Optional[str]:
    """Get the current branch name."""
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def get_default_branch(path: Path) -> str:
    """Get the default branch (main or master)."""
    try:
        # Try to get from remote HEAD
        result = subprocess.run(
            ["git", "-C", str(path), "symbolic-ref", "refs/remotes/origin/HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip().split("/")[-1]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Fallback: check if main or master exists
    for branch in ["main", "master"]:
        try:
            result = subprocess.run(
                ["git", "-C", str(path), "rev-parse", "--verify", branch],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return branch
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    return "main"


def sanitize_branch_name(name: str) -> str:
    """Sanitize a name for use as a branch name."""
    import re
    # Convert to lowercase, replace spaces with hyphens
    safe = name.lower().replace(" ", "-")
    # Remove invalid characters
    safe = re.sub(r"[^a-z0-9-]", "", safe)
    # Remove multiple hyphens
    safe = re.sub(r"-+", "-", safe)
    # Remove leading/trailing hyphens
    safe = safe.strip("-")
    return safe


def get_uncommitted_files(path: Path) -> List[str]:
    """Get list of uncommitted files in a repository."""
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return [line[3:] for line in result.stdout.strip().split("\n") if line]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return []


# ═══════════════════════════════════════════════════════════════════════════════
# Branch Safety - Interactive UI
# ═══════════════════════════════════════════════════════════════════════════════

def check_branch_safety(path: Path, console: Console) -> bool:
    """
    Check if current branch is safe for Claude Code work.

    Displays a visual "speed bump" for protected branches with
    interactive options to create a feature branch or continue.
    """
    if not is_git_repo(path):
        return True

    current = get_current_branch(path)

    if current in PROTECTED_BRANCHES:
        console.print()

        # Visual speed bump - warning panel
        warning = _create_warning_panel(
            "Protected Branch",
            f"You are on branch '{current}'\n\n"
            "For safety, Claude Code work should happen on a feature branch.\n"
            "Direct pushes to protected branches are blocked by git hooks.",
            "Create a feature branch for isolated, safe development"
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
            branch_name = f"{BRANCH_PREFIX}{safe_name}"

            with console.status(f"[cyan]Creating branch {branch_name}...[/cyan]", spinner="dots"):
                try:
                    subprocess.run(
                        ["git", "-C", str(path), "checkout", "-b", branch_name],
                        check=True,
                        capture_output=True,
                        timeout=10,
                    )
                except subprocess.CalledProcessError as e:
                    console.print()
                    console.print(_create_error_panel(
                        "Branch Creation Failed",
                        f"Could not create branch '{branch_name}'",
                        "Check if the branch already exists or if there are uncommitted changes"
                    ))
                    return False

            console.print()
            console.print(_create_success_panel("Branch Created", {
                "Branch": branch_name,
                "Base": current,
            }))
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
    base_branch: Optional[str] = None,
    console: Optional[Console] = None,
) -> Path:
    """
    Create a new git worktree with visual progress feedback.

    Args:
        repo_path: Path to the main repository
        name: Feature name for the worktree
        base_branch: Branch to base the worktree on (default: main/master)
        console: Rich console for output

    Returns:
        Path to the created worktree

    Raises:
        NotAGitRepoError: Path is not a git repository
        WorktreeExistsError: Worktree already exists
        WorktreeCreationError: Failed to create worktree
    """
    if console is None:
        console = Console()

    # Validate repository
    if not is_git_repo(repo_path):
        raise NotAGitRepoError(path=str(repo_path))

    safe_name = sanitize_branch_name(name)
    branch_name = f"{BRANCH_PREFIX}{safe_name}"

    # Determine worktree location
    worktree_base = repo_path.parent / f"{repo_path.name}-worktrees"
    worktree_path = worktree_base / safe_name

    # Check if already exists
    if worktree_path.exists():
        raise WorktreeExistsError(path=str(worktree_path))

    # Determine base branch
    if not base_branch:
        base_branch = get_default_branch(repo_path)

    console.print()
    console.print(_create_info_panel(
        "Creating Worktree",
        f"Feature: {safe_name}",
        f"Location: {worktree_path}"
    ))
    console.print()

    # Multi-step progress
    steps = [
        ("Fetching latest changes", lambda: _fetch_branch(repo_path, base_branch)),
        ("Creating worktree", lambda: _create_worktree_dir(repo_path, worktree_path, branch_name, base_branch, worktree_base)),
        ("Installing dependencies", lambda: install_dependencies(worktree_path, console)),
    ]

    for step_name, step_func in steps:
        with console.status(f"[cyan]{step_name}...[/cyan]", spinner="dots"):
            try:
                step_func()
            except subprocess.CalledProcessError as e:
                raise WorktreeCreationError(
                    name=safe_name,
                    command=" ".join(e.cmd) if hasattr(e, 'cmd') else None,
                    stderr=e.stderr.decode() if e.stderr else None,
                )
        console.print(f"  [green]✓[/green] {step_name}")

    console.print()
    console.print(_create_success_panel("Worktree Ready", {
        "Path": str(worktree_path),
        "Branch": branch_name,
        "Base": base_branch,
        "Next": f"cd {worktree_path}",
    }))

    return worktree_path


def _fetch_branch(repo_path: Path, branch: str) -> None:
    """Fetch a branch from origin."""
    subprocess.run(
        ["git", "-C", str(repo_path), "fetch", "origin", branch],
        capture_output=True,
        timeout=30,
    )


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
                "git", "-C", str(repo_path),
                "worktree", "add",
                "-b", branch_name,
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
                "git", "-C", str(repo_path),
                "worktree", "add",
                "-b", branch_name,
                str(worktree_path),
                base_branch,
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )


def list_worktrees(repo_path: Path, console: Optional[Console] = None) -> List[WorktreeInfo]:
    """
    List all worktrees for a repository with beautiful table display.

    Args:
        repo_path: Path to the repository
        console: Rich console for output (if None, returns data only)

    Returns:
        List of WorktreeInfo objects
    """
    worktrees = _get_worktrees_data(repo_path)

    if console is not None:
        _render_worktrees_table(worktrees, console)

    return worktrees


def render_worktrees(worktrees: List[WorktreeInfo], console: Console) -> None:
    """
    Public interface to render worktrees with beautiful formatting.

    Used by cli.py for consistent styling across the application.
    """
    _render_worktrees_table(worktrees, console)


def _get_worktrees_data(repo_path: Path) -> List[WorktreeInfo]:
    """Get raw worktree data from git."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_path), "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return []

        worktrees = []
        current = {}

        for line in result.stdout.split("\n"):
            if line.startswith("worktree "):
                if current:
                    worktrees.append(WorktreeInfo(
                        path=current.get("path", ""),
                        branch=current.get("branch", ""),
                        status=current.get("status", ""),
                    ))
                current = {"path": line[9:], "branch": "", "status": ""}
            elif line.startswith("branch "):
                current["branch"] = line[7:].replace("refs/heads/", "")
            elif line == "bare":
                current["status"] = "bare"
            elif line == "detached":
                current["status"] = "detached"

        if current:
            worktrees.append(WorktreeInfo(
                path=current.get("path", ""),
                branch=current.get("branch", ""),
                status=current.get("status", ""),
            ))

        return worktrees

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _render_worktrees_table(worktrees: List[WorktreeInfo], console: Console) -> None:
    """Render worktrees in a responsive table."""
    if not worktrees:
        console.print()
        console.print(_create_warning_panel(
            "No Worktrees",
            "No git worktrees found for this repository.",
            "Create one with: scc worktree <repo> <feature-name>"
        ))
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

    if wide_mode:
        table.add_column("Path", style="dim", overflow="ellipsis", ratio=2)
        table.add_column("Status", style="dim", no_wrap=True, width=12)
    else:
        table.add_column("Path", style="dim", overflow="ellipsis", max_width=40)

    for idx, wt in enumerate(worktrees, 1):
        # Style the branch name
        branch_text = wt.branch or Text("detached", style="yellow")
        is_protected = wt.branch in PROTECTED_BRANCHES

        if is_protected:
            branch_display = Text()
            branch_display.append(wt.branch, style="yellow")
        else:
            branch_display = Text(wt.branch, style="cyan")

        # Determine status
        status = wt.status or "active"
        if is_protected:
            status = "protected"

        status_style = {
            "active": "green",
            "protected": "yellow",
            "detached": "yellow",
            "bare": "dim",
        }.get(status, "dim")

        if wide_mode:
            table.add_row(
                str(idx),
                branch_display,
                wt.path,
                Text(status, style=status_style),
            )
        else:
            table.add_row(
                str(idx),
                branch_display,
                wt.path,
            )

    console.print(table)
    console.print()


def cleanup_worktree(
    repo_path: Path,
    name: str,
    force: bool,
    console: Console,
) -> bool:
    """
    Clean up a worktree with safety checks and visual feedback.

    Shows uncommitted changes before deletion to prevent accidental data loss.
    """
    safe_name = sanitize_branch_name(name)
    branch_name = f"{BRANCH_PREFIX}{safe_name}"
    worktree_base = repo_path.parent / f"{repo_path.name}-worktrees"
    worktree_path = worktree_base / safe_name

    if not worktree_path.exists():
        console.print()
        console.print(_create_warning_panel(
            "Worktree Not Found",
            f"No worktree found at: {worktree_path}",
            "Use 'scc worktrees <repo>' to list available worktrees"
        ))
        return False

    console.print()
    console.print(_create_info_panel(
        "Cleanup Worktree",
        f"Worktree: {safe_name}",
        f"Path: {worktree_path}"
    ))
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
                tree.add(Text(f"…and {len(uncommitted) - 10} more", style="dim italic"))

            console.print(tree)
            console.print()
            console.print("[red bold]These changes will be permanently lost.[/red bold]")
            console.print()

            if not Confirm.ask("[yellow]Delete worktree anyway?[/yellow]", default=False):
                console.print("[dim]Cleanup cancelled.[/dim]")
                return False

    # Remove worktree
    with console.status("[cyan]Removing worktree...[/cyan]", spinner="dots"):
        try:
            force_flag = ["--force"] if force else []
            subprocess.run(
                ["git", "-C", str(repo_path), "worktree", "remove", str(worktree_path)] + force_flag,
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

    console.print(f"  [green]✓[/green] Worktree removed")

    # Ask about branch deletion
    console.print()
    if Confirm.ask(f"[cyan]Also delete branch '{branch_name}'?[/cyan]", default=False):
        with console.status("[cyan]Deleting branch...[/cyan]", spinner="dots"):
            subprocess.run(
                ["git", "-C", str(repo_path), "branch", "-D", branch_name],
                capture_output=True,
                timeout=10,
            )
        console.print(f"  [green]✓[/green] Branch deleted")

    console.print()
    console.print(_create_success_panel("Cleanup Complete", {
        "Removed": str(worktree_path),
        "Branch": "deleted" if Confirm else "kept",
    }))

    return True


# ═══════════════════════════════════════════════════════════════════════════════
# Dependency Installation
# ═══════════════════════════════════════════════════════════════════════════════

def install_dependencies(path: Path, console: Optional[Console] = None) -> None:
    """
    Detect and install project dependencies.

    Supports: Node.js (npm/yarn/pnpm/bun), Python (pip/poetry/uv),
    Java (Maven/Gradle)
    """
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

        subprocess.run(cmd, cwd=path, capture_output=True, timeout=300)

    # Python
    if (path / "pyproject.toml").exists():
        if shutil.which("poetry"):
            subprocess.run(["poetry", "install"], cwd=path, capture_output=True, timeout=300)
        elif shutil.which("uv"):
            subprocess.run(["uv", "pip", "install", "-e", "."], cwd=path, capture_output=True, timeout=300)
    elif (path / "requirements.txt").exists():
        subprocess.run(["pip", "install", "-r", "requirements.txt"], cwd=path, capture_output=True, timeout=300)

    # Java/Maven
    if (path / "pom.xml").exists():
        subprocess.run(["mvn", "dependency:resolve"], cwd=path, capture_output=True, timeout=600)

    # Java/Gradle
    if (path / "build.gradle").exists() or (path / "build.gradle.kts").exists():
        gradle_cmd = "./gradlew" if (path / "gradlew").exists() else "gradle"
        subprocess.run([gradle_cmd, "dependencies"], cwd=path, capture_output=True, timeout=600)


# ═══════════════════════════════════════════════════════════════════════════════
# Repository Cloning
# ═══════════════════════════════════════════════════════════════════════════════

def clone_repo(url: str, base_path: str, console: Optional[Console] = None) -> str:
    """
    Clone a repository with progress feedback.

    Args:
        url: Repository URL (HTTPS or SSH)
        base_path: Base directory for cloning
        console: Rich console for output

    Returns:
        Path to the cloned repository

    Raises:
        CloneError: Failed to clone repository
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
    console.print(_create_info_panel(
        "Cloning Repository",
        url,
        f"Target: {target}"
    ))
    console.print()

    with console.status("[cyan]Cloning...[/cyan]", spinner="dots"):
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

    console.print(f"  [green]✓[/green] Repository cloned")
    console.print()
    console.print(_create_success_panel("Clone Complete", {
        "Repository": name,
        "Path": str(target),
    }))

    return str(target)


# ═══════════════════════════════════════════════════════════════════════════════
# Git Hooks Installation
# ═══════════════════════════════════════════════════════════════════════════════

def install_hooks(console: Console) -> None:
    """Install global git hooks for branch protection."""

    hooks_dir = Path.home() / ".config" / "git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    pre_push_content = '''#!/bin/bash
# Sundsvalls kommun - Pre-push hook
# Prevents direct pushes to protected branches

PROTECTED_BRANCHES="main master develop production staging"

current_branch=$(git symbolic-ref HEAD 2>/dev/null | sed -e 's,.*/\\(.*\\),\\1,')

for protected in $PROTECTED_BRANCHES; do
    if [ "$current_branch" = "$protected" ]; then
        echo ""
        echo "⛔ BLOCKED: Direct push to '$protected' is not allowed"
        echo ""
        echo "Please push to a feature branch instead:"
        echo "  git checkout -b claude/<feature-name>"
        echo "  git push -u origin claude/<feature-name>"
        echo ""
        exit 1
    fi
done

while read local_ref local_sha remote_ref remote_sha; do
    remote_branch=$(echo "$remote_ref" | sed -e 's,.*/\\(.*\\),\\1,')

    for protected in $PROTECTED_BRANCHES; do
        if [ "$remote_branch" = "$protected" ]; then
            echo ""
            echo "⛔ BLOCKED: Push to protected branch '$protected'"
            echo ""
            exit 1
        fi
    done
done

exit 0
'''

    pre_push_path = hooks_dir / "pre-push"

    console.print()
    console.print(_create_info_panel(
        "Installing Git Hooks",
        "Branch protection hooks will be installed globally",
        f"Location: {hooks_dir}"
    ))
    console.print()

    with console.status("[cyan]Installing hooks...[/cyan]", spinner="dots"):
        pre_push_path.write_text(pre_push_content)
        pre_push_path.chmod(0o755)

        # Configure git to use global hooks
        subprocess.run(
            ["git", "config", "--global", "core.hooksPath", str(hooks_dir)],
            capture_output=True,
        )

    console.print(f"  [green]✓[/green] Pre-push hook installed")
    console.print()
    console.print(_create_success_panel("Hooks Installed", {
        "Location": str(hooks_dir),
        "Protected branches": "main, master, develop, production, staging",
    }))
