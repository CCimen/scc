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
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from .confirm import Confirm
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
    # Status counts (populated with --verbose)
    staged_count: int = 0
    modified_count: int = 0
    untracked_count: int = 0
    status_timed_out: bool = False  # True if git status timed out


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


def has_commits(path: Path) -> bool:
    """Check if the git repository has at least one commit.

    This is important for worktree operations, which require at least
    one commit to function properly.

    Args:
        path: Path to the git repository.

    Returns:
        True if the repository has at least one commit, False otherwise.
    """
    if not is_git_repo(path):
        return False
    # rev-parse HEAD fails if there are no commits
    return run_command_bool(["git", "-C", str(path), "rev-parse", "HEAD"], timeout=5)


def init_repo(path: Path) -> bool:
    """Initialize a new git repository.

    Args:
        path: Path where to initialize the repository.

    Returns:
        True if initialization succeeded, False otherwise.
    """
    result = run_command(["git", "-C", str(path), "init"], timeout=10)
    return result is not None


def create_empty_initial_commit(path: Path) -> tuple[bool, str | None]:
    """Create an empty initial commit to enable worktree operations.

    Worktrees require at least one commit to function. This creates a
    minimal empty commit without staging any files, following the
    principle of not mutating user files without consent.

    Args:
        path: Path to the git repository.

    Returns:
        Tuple of (success, error_message). If success is False,
        error_message contains details (e.g., git identity not configured).
    """
    result = run_command(
        [
            "git",
            "-C",
            str(path),
            "commit",
            "--allow-empty",
            "-m",
            "Initial commit",
        ],
        timeout=10,
    )
    if result is None:
        # Check if it's a git identity issue
        name_check = run_command(["git", "-C", str(path), "config", "user.name"], timeout=5)
        email_check = run_command(["git", "-C", str(path), "config", "user.email"], timeout=5)
        if not name_check or not email_check:
            return (
                False,
                "Git identity not configured. Run:\n"
                "  git config --global user.name 'Your Name'\n"
                "  git config --global user.email 'you@example.com'",
            )
        return (False, "Failed to create initial commit")
    return (True, None)


def has_remote(path: Path, remote_name: str = "origin") -> bool:
    """Check if the repository has a specific remote configured.

    This is used to determine whether fetch operations should be attempted.
    Freshly initialized repositories have no remotes.

    Args:
        path: Path to the git repository.
        remote_name: Name of the remote to check (default: "origin").

    Returns:
        True if the remote exists, False otherwise.
    """
    if not is_git_repo(path):
        return False
    result = run_command(
        ["git", "-C", str(path), "remote", "get-url", remote_name],
        timeout=5,
    )
    return result is not None


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
        echo "  git checkout -b scc/your-feature"
        echo "  git push -u origin scc/your-feature"
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
    """Get the default branch for worktree creation.

    Resolution order:
    1. Current branch (respects user's git init.defaultBranch config)
    2. Remote origin HEAD (for cloned repositories)
    3. Check if main or master exists locally
    4. Fallback to "main"

    This order ensures freshly initialized repos use their actual branch
    name rather than assuming "main".
    """
    # Priority 1: Use current branch (best for local-only repos)
    current = get_current_branch(path)
    if current:
        return current

    # Priority 2: Try to get from remote HEAD (for cloned repos)
    output = run_command(
        ["git", "-C", str(path), "symbolic-ref", "refs/remotes/origin/HEAD"],
        timeout=5,
    )
    if output:
        return output.split("/")[-1]

    # Priority 3: Check if main or master exists locally
    for branch in ["main", "master"]:
        if run_command_bool(
            ["git", "-C", str(path), "rev-parse", "--verify", branch],
            timeout=5,
        ):
            return branch

    return "main"


def sanitize_branch_name(name: str) -> str:
    """Sanitize a name for use as a branch/directory name.

    Converts input to a safe format for git branch names and filesystem directories.
    Path separators (/ and \\) are replaced with hyphens to prevent collisions.

    Examples:
        >>> sanitize_branch_name("feature/auth")
        'feature-auth'
        >>> sanitize_branch_name("Feature Auth")
        'feature-auth'
    """
    safe = name.lower()
    # Replace path separators with hyphens FIRST (collision fix)
    safe = safe.replace("/", "-").replace("\\", "-")
    # Replace spaces with hyphens
    safe = safe.replace(" ", "-")
    # Remove invalid characters (only a-z, 0-9, - allowed)
    safe = re.sub(r"[^a-z0-9-]", "", safe)
    # Collapse multiple hyphens
    safe = re.sub(r"-+", "-", safe)
    # Strip leading/trailing hyphens
    return safe.strip("-")


def get_uncommitted_files(path: Path) -> list[str]:
    """Get list of uncommitted files in a repository."""
    lines = run_command_lines(
        ["git", "-C", str(path), "status", "--porcelain"],
        timeout=5,
    )
    # Each line is "XY filename" where XY is 2-char status code
    return [line[3:] for line in lines if len(line) > 3]


def get_worktree_status(worktree_path: str) -> tuple[int, int, int, bool]:
    """Get status counts for a worktree (staged, modified, untracked, timed_out).

    Parses git status --porcelain output where each line starts with:
    - XY where X is index status, Y is worktree status
    - X = staged changes (A, M, D, R, C)
    - Y = unstaged changes (M, D)
    - ?? = untracked files

    Args:
        worktree_path: Path to the worktree directory.

    Returns:
        Tuple of (staged_count, modified_count, untracked_count, timed_out).
    """
    try:
        result = subprocess.run(
            ["git", "-C", worktree_path, "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return 0, 0, 0, False

        lines = [line for line in result.stdout.split("\n") if line.strip()]
    except subprocess.TimeoutExpired:
        return 0, 0, 0, True

    staged = 0
    modified = 0
    untracked = 0

    for line in lines:
        if len(line) < 2:
            continue

        index_status = line[0]  # X - index/staging area
        worktree_status = line[1]  # Y - working tree

        if line.startswith("??"):
            untracked += 1
        else:
            # Staged: any change in index (not space or ?)
            if index_status not in (" ", "?"):
                staged += 1
            # Modified: any change in worktree (not space or ?)
            if worktree_status not in (" ", "?"):
                modified += 1

    return staged, modified, untracked, False


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
    worktrees = _get_worktrees_data(repo_path)

    # Detect current worktree
    import os

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
        _render_worktrees_table(worktrees, console, verbose=verbose)

        # Summary if any timed out (only when verbose and console provided)
        if verbose:
            timeout_count = sum(1 for wt in worktrees if wt.status_timed_out)
            if timeout_count > 0:
                console.print(
                    f"[dim]Note: {timeout_count} worktree(s) timed out computing status.[/dim]",
                )

    return worktrees


def render_worktrees(
    worktrees: list[WorktreeInfo],
    console: Console,
    *,
    verbose: bool = False,
) -> None:
    """Render worktrees with beautiful formatting.

    Public interface used by cli.py for consistent styling across the application.
    """
    _render_worktrees_table(worktrees, console, verbose=verbose)


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


def find_worktree_by_query(
    repo_path: Path,
    query: str,
) -> tuple[WorktreeInfo | None, list[WorktreeInfo]]:
    """Find a worktree by name, branch, or path using fuzzy matching.

    Resolution order (prefix-aware):
    1. Exact match on branch name (user typed full branch like 'scc/feature')
    2. Prefixed branch match (user typed 'feature', branch is 'scc/feature')
    3. Exact match on worktree directory name
    4. Branch starts with query (prefix stripped for comparison)
    5. Directory starts with query
    6. Query contained in branch name (prefix stripped)
    7. Query contained in directory name

    Args:
        repo_path: Path to the repository.
        query: Search query (branch name, directory name, or partial match).

    Returns:
        Tuple of (exact_match, all_matches). If exact_match is None,
        all_matches contains partial matches for disambiguation.
    """
    worktrees = _get_worktrees_data(repo_path)
    if not worktrees:
        return None, []

    query_lower = query.lower()
    query_sanitized = sanitize_branch_name(query).lower()
    prefix_lower = WORKTREE_BRANCH_PREFIX.lower()
    prefixed_query = f"{prefix_lower}{query_sanitized}"

    matches: list[WorktreeInfo] = []

    # Priority 1: Exact match on branch name (user typed full branch name)
    for wt in worktrees:
        branch_lower = wt.branch.lower()
        if branch_lower == query_lower:
            return wt, [wt]

    # Priority 2: Prefixed branch match (user typed feature name, branch is scc/feature)
    for wt in worktrees:
        branch_lower = wt.branch.lower()
        if branch_lower == prefixed_query:
            return wt, [wt]

    # Priority 3: Exact match on directory name
    for wt in worktrees:
        dir_name = Path(wt.path).name.lower()
        if dir_name == query_sanitized or dir_name == query_lower:
            return wt, [wt]

    # Priority 4: Branch starts with query (strip prefix for matching)
    for wt in worktrees:
        branch_lower = wt.branch.lower()
        display_branch = (
            branch_lower[len(prefix_lower) :]
            if branch_lower.startswith(prefix_lower)
            else branch_lower
        )
        if display_branch.startswith(query_sanitized):
            matches.append(wt)
    if len(matches) == 1:
        return matches[0], matches
    if matches:
        return None, matches

    # Priority 5: Directory starts with query
    for wt in worktrees:
        dir_name = Path(wt.path).name.lower()
        if dir_name.startswith(query_sanitized):
            matches.append(wt)
    if len(matches) == 1:
        return matches[0], matches
    if matches:
        return None, matches

    # Priority 6: Query contained in branch name (prefix stripped)
    for wt in worktrees:
        branch_lower = wt.branch.lower()
        display_branch = (
            branch_lower[len(prefix_lower) :]
            if branch_lower.startswith(prefix_lower)
            else branch_lower
        )
        if query_sanitized in display_branch:
            matches.append(wt)
    if len(matches) == 1:
        return matches[0], matches
    if matches:
        return None, matches

    # Priority 7: Query contained in directory name
    for wt in worktrees:
        dir_name = Path(wt.path).name.lower()
        if query_sanitized in dir_name:
            matches.append(wt)
    if len(matches) == 1:
        return matches[0], matches

    return None, matches


def find_main_worktree(repo_path: Path) -> WorktreeInfo | None:
    """Find the worktree for the default/main branch.

    Args:
        repo_path: Path to the repository.

    Returns:
        WorktreeInfo for the main branch worktree, or None if not found.
    """
    default_branch = get_default_branch(repo_path)
    worktrees = _get_worktrees_data(repo_path)

    for wt in worktrees:
        if wt.branch == default_branch:
            return wt

    return None


def list_branches_without_worktrees(repo_path: Path) -> list[str]:
    """List remote branches that don't have local worktrees.

    Args:
        repo_path: Path to the repository.

    Returns:
        List of branch names (without origin/ prefix) that have no worktrees.
    """
    # Get all remote branches
    remote_output = run_command(
        ["git", "-C", str(repo_path), "branch", "-r", "--format", "%(refname:short)"],
        timeout=10,
    )
    if not remote_output:
        return []

    remote_branches = set()
    for line in remote_output.strip().split("\n"):
        line = line.strip()
        if line and not line.endswith("/HEAD"):
            # Remove origin/ prefix
            if "/" in line:
                branch = line.split("/", 1)[1]
                remote_branches.add(branch)

    # Get worktree branches
    worktrees = _get_worktrees_data(repo_path)
    worktree_branches = {wt.branch for wt in worktrees if wt.branch}

    # Return branches without worktrees
    return sorted(remote_branches - worktree_branches)


def get_display_branch(branch: str) -> str:
    """Get user-friendly branch name (strip worktree prefixes if present).

    Strips both `scc/` (current) and `claude/` (legacy) prefixes for cleaner display.
    This is display-only; matching rules still require `scc/` prefix for new branches.

    Args:
        branch: The full branch name.

    Returns:
        Branch name with worktree prefix stripped for display.
    """
    # Strip both current (scc/) and legacy (claude/) prefixes for display
    for prefix in (WORKTREE_BRANCH_PREFIX, "claude/"):
        if branch.startswith(prefix):
            return branch[len(prefix) :]
    return branch


def _format_git_status(wt: WorktreeInfo) -> Text:
    """Format git status as compact symbols: +N!N?N, . for clean, or … for timeout."""
    # Show ellipsis if status timed out
    if wt.status_timed_out:
        return Text("…", style="dim")

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


def _render_worktrees_table(
    worktrees: list[WorktreeInfo],
    console: Console,
    *,
    verbose: bool = False,
) -> None:
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
            git_status = _format_git_status(wt)
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
