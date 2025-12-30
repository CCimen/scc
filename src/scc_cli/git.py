"""
Git operations including worktree management and safety checks.

UI Philosophy:
- Consistent visual language with semantic colors
- Responsive layouts (80-120+ columns)
- Clear hierarchy: errors > warnings > info > success
- Interactive flows with visual "speed bumps" for dangerous ops
"""

import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from rich import box
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from .constants import WORKTREE_BRANCH_PREFIX
from .errors import (
    CloneError,
    GitNotFoundError,
    NotAGitRepoError,
    WorktreeCreationError,
    WorktreeExistsError,
)
from .panels import (
    create_error_panel,
    create_info_panel,
    create_success_panel,
    create_warning_panel,
)
from .subprocess_utils import run_command, run_command_bool, run_command_lines
from .theme import Indicators, Spinners
from .utils.locks import file_lock, lock_path

# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

PROTECTED_BRANCHES = ("main", "master", "develop", "production", "staging")
BRANCH_PREFIX = WORKTREE_BRANCH_PREFIX  # Imported from constants.py
SCC_HOOK_MARKER = "# SCC-MANAGED-HOOK"  # Identifies hooks we can safely update


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
# Git Detection & Basic Operations
# ═══════════════════════════════════════════════════════════════════════════════


def check_git_available() -> None:
    """Check if Git is installed and available.

    Raises:
        GitNotFoundError: Git is not installed or not in PATH
    """
    if shutil.which("git") is None:
        raise GitNotFoundError()


def check_git_installed() -> bool:
    """Check if Git is installed (boolean for doctor command)."""
    return shutil.which("git") is not None


def get_git_version() -> str | None:
    """Get Git version string for display."""
    # Returns something like "git version 2.40.0"
    return run_command(["git", "--version"], timeout=5)


def is_git_repo(path: Path) -> bool:
    """Check if path is inside a git repository."""
    return run_command_bool(["git", "-C", str(path), "rev-parse", "--git-dir"], timeout=5)


def detect_workspace_root(start_dir: Path) -> tuple[Path | None, Path]:
    """Detect the workspace root from a starting directory.

    This function implements smart workspace detection for use cases where
    the user runs `scc start` from a subdirectory or git worktree.

    Resolution order:
    1) git rev-parse --show-toplevel (works for subdirs + worktrees)
    2) Parent-walk for .scc.yaml (repo root config marker)
    3) Parent-walk for .git (directory OR file - worktree-safe)
    4) None (no workspace detected)

    Args:
        start_dir: The directory to start detection from (usually cwd).

    Returns:
        Tuple of (root, start_cwd) where:
        - root: The detected workspace root, or None if not found
        - start_cwd: The original start_dir (preserved for container cwd)
    """
    start_dir = start_dir.resolve()

    # Priority 1: Use git rev-parse --show-toplevel (handles subdirs + worktrees)
    if check_git_installed():
        toplevel = run_command(
            ["git", "-C", str(start_dir), "rev-parse", "--show-toplevel"],
            timeout=5,
        )
        if toplevel:
            return (Path(toplevel.strip()), start_dir)

    # Priority 2: Parent-walk for .scc.yaml (SCC project marker)
    current = start_dir
    while current != current.parent:
        scc_config = current / ".scc.yaml"
        if scc_config.is_file():
            return (current, start_dir)
        current = current.parent

    # Priority 3: Parent-walk for .git (directory OR file - worktree-safe)
    current = start_dir
    while current != current.parent:
        git_marker = current / ".git"
        if git_marker.exists():  # Works for both directory and file
            return (current, start_dir)
        current = current.parent

    # No workspace detected
    return (None, start_dir)


def is_protected_branch(branch: str) -> bool:
    """Check if branch is protected.

    Protected branches are: main, master, develop, production, staging.
    """
    return branch in PROTECTED_BRANCHES


def is_scc_hook(hook_path: Path) -> bool:
    """Check if hook file is managed by SCC (has SCC marker).

    Returns:
        True if hook exists and contains SCC_HOOK_MARKER, False otherwise.
    """
    if not hook_path.exists():
        return False
    try:
        content = hook_path.read_text()
        return SCC_HOOK_MARKER in content
    except (OSError, PermissionError):
        return False


def install_pre_push_hook(repo_path: Path) -> tuple[bool, str]:
    """Install repo-local pre-push hook with strict rules.

    Installation conditions:
    1. User said yes in `scc setup` (hooks.enabled=true in config)
    2. Repo is recognized (has .git directory)

    Never:
    - Modify global git config
    - Overwrite existing non-SCC hooks

    Args:
        repo_path: Path to the git repository root

    Returns:
        Tuple of (success, message) describing the outcome
    """
    from .config import load_user_config

    # Condition 1: Check if hooks are enabled in user config
    config = load_user_config()
    if not config.get("hooks", {}).get("enabled", False):
        return (False, "Hooks not enabled in config")

    # Condition 2: Check if repo is recognized (has .git directory)
    git_dir = repo_path / ".git"
    if not git_dir.exists():
        return (False, "Not a git repository")

    # Determine hooks directory (repo-local, NOT global)
    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / "pre-push"

    # Check for existing hook
    if hook_path.exists():
        if is_scc_hook(hook_path):
            # Safe to update our own hook
            _write_scc_hook(hook_path)
            return (True, "Updated existing SCC hook")
        else:
            # DON'T overwrite user's hook
            return (
                False,
                f"Will not overwrite existing user hook at {hook_path}. "
                f"To manually add SCC protection, add '{SCC_HOOK_MARKER}' marker to your hook.",
            )

    # No existing hook - safe to create
    _write_scc_hook(hook_path)
    return (True, "Installed new SCC hook")


def _write_scc_hook(hook_path: Path) -> None:
    """Write SCC pre-push hook content.

    The hook blocks pushes to protected branches (main, master, develop, production, staging).
    """
    hook_content = f"""#!/bin/bash
{SCC_HOOK_MARKER}
# SCC pre-push hook - blocks pushes to protected branches
# This hook is managed by SCC. You can safely delete it to remove protection.

branch=$(git rev-parse --abbrev-ref HEAD)
protected_branches="main master develop production staging"

for protected in $protected_branches; do
    if [ "$branch" = "$protected" ]; then
        echo ""
        echo "❌ Direct push to '$branch' blocked by SCC"
        echo ""
        echo "Create a feature branch first:"
        echo "  git checkout -b feature/your-feature"
        echo "  git push -u origin feature/your-feature"
        echo ""
        exit 1
    fi
done

exit 0
"""
    hook_path.write_text(hook_content)
    hook_path.chmod(0o755)


def is_worktree(path: Path) -> bool:
    """Check if the path is a git worktree (not the main repository).

    Worktrees have a `.git` file (not directory) containing a gitdir pointer.
    """
    git_path = path / ".git"
    return git_path.is_file()  # Worktrees have .git as file, main repo has .git as dir


def get_worktree_main_repo(worktree_path: Path) -> Path | None:
    """Get the main repository path for a worktree.

    Parse the `.git` file to find the gitdir pointer and resolve
    back to the main repo location.

    Returns:
        Main repository path, or None if not a worktree or cannot determine.
    """
    git_file = worktree_path / ".git"

    if not git_file.is_file():
        return None

    try:
        content = git_file.read_text().strip()
        # Format: "gitdir: /path/to/main-repo/.git/worktrees/<name>"
        if content.startswith("gitdir:"):
            gitdir = content[7:].strip()
            gitdir_path = Path(gitdir)

            # Navigate from .git/worktrees/<name> up to repo root
            # gitdir_path = /repo/.git/worktrees/feature
            # We need /repo
            if "worktrees" in gitdir_path.parts:
                # Find the .git directory (parent of worktrees)
                git_dir = gitdir_path
                while git_dir.name != ".git" and git_dir != git_dir.parent:
                    git_dir = git_dir.parent
                if git_dir.name == ".git":
                    return git_dir.parent
    except (OSError, ValueError):
        pass

    return None


def get_workspace_mount_path(workspace: Path) -> tuple[Path, bool]:
    """Determine the optimal path to mount for Docker sandbox.

    For worktrees, return the common parent containing both repo and worktrees folder.
    For regular repos, return the workspace path as-is.

    This ensures git worktrees have access to the main repo's .git folder.
    The gitdir pointer in worktrees uses absolute paths, so Docker must mount
    the common parent to make those paths resolve correctly inside the container.

    Returns:
        Tuple of (mount_path, is_expanded) where is_expanded=True if we expanded
        the mount scope beyond the original workspace (for user awareness).

    Note:
        Docker sandbox uses "mirrored mounting" - the path inside the container
        matches the host path, so absolute gitdir pointers will resolve correctly.
    """
    if not is_worktree(workspace):
        return workspace, False

    main_repo = get_worktree_main_repo(workspace)
    if main_repo is None:
        return workspace, False

    # Find common parent of worktree and main repo
    # Worktree: /parent/repo-worktrees/feature
    # Main repo: /parent/repo
    # Common parent: /parent

    workspace_resolved = workspace.resolve()
    main_repo_resolved = main_repo.resolve()

    worktree_parts = workspace_resolved.parts
    repo_parts = main_repo_resolved.parts

    # Find common ancestor path
    common_parts = []
    for w_part, r_part in zip(worktree_parts, repo_parts):
        if w_part == r_part:
            common_parts.append(w_part)
        else:
            break

    if not common_parts:
        # No common ancestor - shouldn't happen, but fall back safely
        return workspace, False

    common_parent = Path(*common_parts)

    # Safety checks: don't mount system directories
    # Use resolved paths for proper symlink handling (cross-platform)
    try:
        resolved_parent = common_parent.resolve()
    except OSError:
        # Can't resolve path - fall back to safe option
        return workspace, False

    # System directories that should NEVER be mounted as common parent
    # Cross-platform: covers Linux, macOS, and WSL2
    blocked_roots = {
        # Root filesystem
        Path("/"),
        # User home parents (mounting all of /home or /Users is too broad)
        Path("/home"),
        Path("/Users"),
        # System directories (Linux + macOS)
        Path("/bin"),
        Path("/boot"),
        Path("/dev"),
        Path("/etc"),
        Path("/lib"),
        Path("/lib64"),
        Path("/opt"),
        Path("/proc"),
        Path("/root"),
        Path("/run"),
        Path("/sbin"),
        Path("/srv"),
        Path("/sys"),
        Path("/usr"),
        # Temp directories (sensitive, often contain secrets)
        Path("/tmp"),
        Path("/var"),
        # macOS specific
        Path("/System"),
        Path("/Library"),
        Path("/Applications"),
        Path("/Volumes"),
        Path("/private"),
        # WSL2 specific
        Path("/mnt"),
    }

    # Check if resolved path IS or IS UNDER a blocked root
    for blocked in blocked_roots:
        if resolved_parent == blocked:
            return workspace, False

        # Skip root "/" for is_relative_to check - all paths are under root!
        # We already checked exact match above.
        if blocked == Path("/"):
            continue

        # Use is_relative_to for "is under" check (Python 3.9+)
        try:
            if resolved_parent.is_relative_to(blocked):
                # Exception: allow paths under /home/<user>/... or /Users/<user>/...
                # (i.e., actual user workspaces, not the parent directories themselves)
                if blocked in (Path("/home"), Path("/Users")):
                    # /home/user/projects is OK (depth 4+)
                    # /home/user is too broad (depth 3)
                    if len(resolved_parent.parts) >= 4:
                        continue  # Allow: /home/user/projects or deeper

                # WSL2 exception: /mnt/<drive>/... where <drive> is single letter
                # This specifically targets Windows filesystem mounts, NOT arbitrary
                # Linux mount points like /mnt/nfs, /mnt/usb, /mnt/wsl, etc.
                if blocked == Path("/mnt"):
                    parts = resolved_parent.parts
                    # Validate: /mnt/<single-letter>/<something>/<something>
                    # parts[0]="/", parts[1]="mnt", parts[2]=drive, parts[3+]=path
                    if len(parts) >= 5:  # Conservative: require depth 5+
                        drive = parts[2] if len(parts) > 2 else ""
                        # WSL2 drives are single letters (c, d, e, etc.)
                        if len(drive) == 1 and drive.isalpha():
                            continue  # Allow: /mnt/c/Users/dev/projects

                return workspace, False
        except (ValueError, AttributeError):
            # is_relative_to raises ValueError if not relative
            # AttributeError on Python < 3.9 (fallback below)
            pass

    # Fallback depth check for edge cases not caught above
    # Require at least 3 path components: /, parent, child
    # This catches unusual paths not in the blocklist
    if len(resolved_parent.parts) < 3:
        return workspace, False

    return common_parent, True


def get_current_branch(path: Path) -> str | None:
    """Get the current branch name."""
    return run_command(["git", "-C", str(path), "branch", "--show-current"], timeout=5)


def get_default_branch(path: Path) -> str:
    """Get the default branch (main or master)."""
    # Try to get from remote HEAD
    output = run_command(
        ["git", "-C", str(path), "symbolic-ref", "refs/remotes/origin/HEAD"],
        timeout=5,
    )
    if output:
        return output.split("/")[-1]

    # Fallback: check if main or master exists
    for branch in ["main", "master"]:
        if run_command_bool(
            ["git", "-C", str(path), "rev-parse", "--verify", branch],
            timeout=5,
        ):
            return branch

    return "main"


def sanitize_branch_name(name: str) -> str:
    """Sanitize a name for use as a branch name."""
    # Convert to lowercase, replace spaces with hyphens
    safe = name.lower().replace(" ", "-")
    # Remove invalid characters
    safe = re.sub(r"[^a-z0-9-]", "", safe)
    # Remove multiple hyphens
    safe = re.sub(r"-+", "-", safe)
    # Remove leading/trailing hyphens
    safe = safe.strip("-")
    return safe


def get_uncommitted_files(path: Path) -> list[str]:
    """Get list of uncommitted files in a repository."""
    lines = run_command_lines(
        ["git", "-C", str(path), "status", "--porcelain"],
        timeout=5,
    )
    # Each line is "XY filename" where XY is 2-char status code
    return [line[3:] for line in lines if len(line) > 3]


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
            branch_name = f"{BRANCH_PREFIX}{safe_name}"

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
    branch_name = f"{BRANCH_PREFIX}{safe_name}"

    # Determine worktree location
    worktree_base = repo_path.parent / f"{repo_path.name}-worktrees"
    worktree_path = worktree_base / safe_name

    lock_file = lock_path("worktree", repo_path)
    with file_lock(lock_file):
        # Check if already exists
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

        # Multi-step progress
        steps: list[tuple[str, Callable[[], None]]] = [
            ("Fetching latest changes", lambda: _fetch_branch(repo_path, base_branch)),
            (
                "Creating worktree",
                lambda: _create_worktree_dir(
                    repo_path, worktree_path, branch_name, base_branch, worktree_base
                ),
            ),
            ("Installing dependencies", _install_deps),
        ]

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


def list_worktrees(repo_path: Path, console: Console | None = None) -> list[WorktreeInfo]:
    """List all worktrees for a repository with beautiful table display.

    Args:
        repo_path: Path to the repository.
        console: Rich console for output (if None, return data only).

    Returns:
        List of WorktreeInfo objects.
    """
    worktrees = _get_worktrees_data(repo_path)

    if console is not None:
        _render_worktrees_table(worktrees, console)

    return worktrees


def render_worktrees(worktrees: list[WorktreeInfo], console: Console) -> None:
    """Render worktrees with beautiful formatting.

    Public interface used by cli.py for consistent styling across the application.
    """
    _render_worktrees_table(worktrees, console)


def _get_worktrees_data(repo_path: Path) -> list[WorktreeInfo]:
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
        current: dict[str, str] = {}

        for line in result.stdout.split("\n"):
            if line.startswith("worktree "):
                if current:
                    worktrees.append(
                        WorktreeInfo(
                            path=current.get("path", ""),
                            branch=current.get("branch", ""),
                            status=current.get("status", ""),
                        )
                    )
                current = {"path": line[9:], "branch": "", "status": ""}
            elif line.startswith("branch "):
                current["branch"] = line[7:].replace("refs/heads/", "")
            elif line == "bare":
                current["status"] = "bare"
            elif line == "detached":
                current["status"] = "detached"

        if current:
            worktrees.append(
                WorktreeInfo(
                    path=current.get("path", ""),
                    branch=current.get("branch", ""),
                    status=current.get("status", ""),
                )
            )

        return worktrees

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _render_worktrees_table(worktrees: list[WorktreeInfo], console: Console) -> None:
    """Render worktrees in a responsive table."""
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

    if wide_mode:
        table.add_column("Path", style="dim", overflow="ellipsis", ratio=2)
        table.add_column("Status", style="dim", no_wrap=True, width=12)
    else:
        table.add_column("Path", style="dim", overflow="ellipsis", max_width=40)

    for idx, wt in enumerate(worktrees, 1):
        # Style the branch name
        is_detached = not wt.branch
        is_protected = wt.branch in PROTECTED_BRANCHES if wt.branch else False
        branch_value = wt.branch or "detached"

        if is_protected or is_detached:
            branch_display = Text(branch_value, style="yellow")
        else:
            branch_display = Text(branch_value, style="cyan")

        # Determine status
        status = wt.status or ("detached" if is_detached else "active")
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
    branch_name = f"{BRANCH_PREFIX}{safe_name}"
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
                tree.add(Text(f"…and {len(uncommitted) - 10} more", style="dim italic"))

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
        console.print(f"    • Worktree: {worktree_path}")
        console.print(f"    • Branch: {branch_name} [dim](if confirmed)[/dim]")
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
