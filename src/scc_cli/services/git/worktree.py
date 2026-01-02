"""Worktree operations - data structures and queries.

Pure functions with no UI dependencies.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from ...core.constants import WORKTREE_BRANCH_PREFIX
from .branch import get_default_branch, sanitize_branch_name


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


def get_worktrees_data(repo_path: Path) -> list[WorktreeInfo]:
    """Get raw worktree data from git.

    This is the public API for getting worktree data.
    Previously named _get_worktrees_data (private).
    """
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
    worktrees = get_worktrees_data(repo_path)
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
    worktrees = get_worktrees_data(repo_path)

    for wt in worktrees:
        if wt.branch == default_branch:
            return wt

    return None
