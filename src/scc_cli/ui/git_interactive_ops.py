"""Git interactive operations — cleanup, hooks, and dependency installation.

Extracted from git_interactive.py to keep that module focused on
worktree creation, branch safety, and repository cloning.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

from rich.console import Console
from rich.text import Text
from rich.tree import Tree

from ..core.constants import WORKTREE_BRANCH_PREFIX
from ..panels import (
    create_info_panel,
    create_success_panel,
    create_warning_panel,
)
from ..services.git.branch import (
    get_uncommitted_files,
    sanitize_branch_name,
)
from ..theme import Indicators, Spinners

if TYPE_CHECKING:
    pass


def _get_confirm_with_layout() -> Any:
    """Late-bound lookup through git_interactive for test-patch compatibility."""
    from . import git_interactive as _gi_mod

    return _gi_mod.confirm_with_layout


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
                if not _get_confirm_with_layout()(
                    console,
                    "[yellow]Delete worktree anyway?[/yellow]",
                    default=False,
                ):
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
    should_delete_branch = skip_confirm or _get_confirm_with_layout()(
        console,
        f"[cyan]Also delete branch '{branch_name}'?[/cyan]",
        default=False,
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
