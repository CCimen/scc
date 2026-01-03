"""Core git operations - detection, initialization, repository management.

Pure functions with no UI dependencies.
"""

import shutil
from pathlib import Path

from ...core.errors import GitNotFoundError
from ...subprocess_utils import run_command, run_command_bool


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


def is_file_ignored(file_path: str | Path, repo_root: Path | None = None) -> bool:
    """Check if a file path is ignored by git.

    Uses git check-ignore to determine if the file would be ignored.
    Returns False if git is not available or not in a git repo (fail-open).

    Args:
        file_path: The file path to check.
        repo_root: The repository root. If None, uses current directory.

    Returns:
        True if the file is ignored by git, False otherwise.
    """
    import subprocess

    cwd = str(repo_root) if repo_root else None

    # Check if we're actually in a git repo
    if repo_root and not (repo_root / ".git").exists():
        return False

    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", str(file_path)],
            capture_output=True,
            cwd=cwd,
            timeout=5,
        )
        # Exit code 0 means file IS ignored
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # git not available or other error - fail silently (fail-open)
        return False
