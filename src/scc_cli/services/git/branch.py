"""Branch operations - safety checks, naming, queries.

Pure functions with no UI dependencies.
"""

import re
from pathlib import Path

from ...core.constants import WORKTREE_BRANCH_PREFIX
from ...subprocess_utils import run_command, run_command_bool, run_command_lines

PROTECTED_BRANCHES = ("main", "master", "develop", "production", "staging")


def is_protected_branch(branch: str) -> bool:
    """Check if branch is protected.

    Protected branches are: main, master, develop, production, staging.
    """
    return branch in PROTECTED_BRANCHES


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


def get_uncommitted_files(path: Path) -> list[str]:
    """Get list of uncommitted files in a repository."""
    lines = run_command_lines(
        ["git", "-C", str(path), "status", "--porcelain"],
        timeout=5,
    )
    # Each line is "XY filename" where XY is 2-char status code
    return [line[3:] for line in lines if len(line) > 3]


def list_branches_without_worktrees(repo_path: Path) -> list[str]:
    """List remote branches that don't have local worktrees.

    Args:
        repo_path: Path to the repository.

    Returns:
        List of branch names (without origin/ prefix) that have no worktrees.
    """
    from .worktree import get_worktrees_data

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
    worktrees = get_worktrees_data(repo_path)
    worktree_branches = {wt.branch for wt in worktrees if wt.branch}

    # Return branches without worktrees
    return sorted(remote_branches - worktree_branches)
