"""Git worktree health checks for doctor module.

Checks for worktree health, version compatibility, and branch conflicts.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from ..types import CheckResult


def check_worktree_health(cwd: Path | None = None) -> CheckResult | None:
    """Check health of git worktrees in the current repository.

    Parses `git worktree list --porcelain` to detect:
    - Prunable worktrees (stale entries)
    - Locked worktrees (with lock reason)
    - Detached HEAD states
    - Branch conflicts (branch checked out elsewhere)

    Args:
        cwd: Directory to check (defaults to current working directory).

    Returns:
        CheckResult with worktree health status, or None if not in a git repo.
    """
    if cwd is None:
        cwd = Path.cwd()

    # Check if we're in a git repo
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--is-inside-work-tree"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            # Not a git repo - skip check
            return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None

    # Parse worktree list --porcelain
    worktree_data = _parse_worktree_porcelain(cwd)
    if not worktree_data:
        # No worktrees or failed to parse
        return CheckResult(
            name="Worktrees",
            passed=True,
            message="No worktrees configured (single checkout)",
        )

    # Count issues
    prunable_count = sum(1 for wt in worktree_data if wt.get("prunable"))
    locked_count = sum(1 for wt in worktree_data if wt.get("locked"))
    detached_count = sum(1 for wt in worktree_data if wt.get("detached"))

    # Build summary message
    issues = []
    if prunable_count > 0:
        issues.append(f"{prunable_count} prunable")
    if locked_count > 0:
        issues.append(f"{locked_count} locked")
    if detached_count > 0:
        issues.append(f"{detached_count} detached")

    total = len(worktree_data)

    if not issues:
        return CheckResult(
            name="Worktrees",
            passed=True,
            message=f"{total} worktree{'s' if total != 1 else ''}, all healthy",
        )

    # Build fix hints
    fix_hints = []
    fix_commands = []
    if prunable_count > 0:
        fix_hints.append("Remove stale worktree entries with prune")
        fix_commands.append("scc worktree prune")
    if locked_count > 0:
        # Find locked worktrees and show reasons
        for wt in worktree_data:
            if wt.get("locked"):
                reason = wt.get("lock_reason", "no reason given")
                path = Path(wt.get("path", "")).name
                fix_hints.append(f"'{path}' locked: {reason}")

    return CheckResult(
        name="Worktrees",
        passed=prunable_count == 0,  # Fail only if prunable (needs cleanup)
        message=f"{total} worktree{'s' if total != 1 else ''}: {', '.join(issues)}",
        fix_hint="; ".join(fix_hints) if fix_hints else None,
        fix_commands=fix_commands if fix_commands else None,
        severity="warning" if prunable_count > 0 else "info",
    )


def _parse_worktree_porcelain(repo_path: Path) -> list[dict[str, Any]]:
    """Parse git worktree list --porcelain output.

    Porcelain format example:
        worktree /path/to/main
        HEAD abc123
        branch refs/heads/main

        worktree /path/to/feature
        HEAD def456
        branch refs/heads/feature
        locked
        locked reason: deployment in progress

        worktree /path/to/old
        HEAD ghi789
        detached
        prunable

    Returns:
        List of dicts with keys: path, branch, detached, locked, lock_reason, prunable
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
        current: dict[str, Any] = {}

        for line in result.stdout.split("\n"):
            if line.startswith("worktree "):
                # Start of new worktree entry
                if current and current.get("path"):
                    worktrees.append(current)
                current = {
                    "path": line[9:],
                    "branch": "",
                    "detached": False,
                    "locked": False,
                    "lock_reason": "",
                    "prunable": False,
                }
            elif line.startswith("branch "):
                current["branch"] = line[7:].replace("refs/heads/", "")
            elif line == "detached":
                current["detached"] = True
            elif line == "locked":
                current["locked"] = True
            elif line.startswith("locked "):
                # "locked reason: ..." format
                current["locked"] = True
                current["lock_reason"] = line[7:]  # Includes "reason: " prefix
            elif line == "prunable":
                current["prunable"] = True
            elif line.startswith("prunable "):
                # "prunable reason: ..." format
                current["prunable"] = True

        # Don't forget the last worktree
        if current and current.get("path"):
            worktrees.append(current)

        return worktrees

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def check_git_version_for_worktrees() -> CheckResult | None:
    """Check if git version supports stable worktree operations.

    Git 2.20+ is recommended for stable worktree behavior.
    Earlier versions may have issues with locked worktrees and pruning.

    Returns:
        CheckResult with version check status, or None if git not installed.
    """
    from ... import git as git_module

    if not git_module.check_git_installed():
        return None  # Already covered by check_git()

    version = git_module.get_git_version()
    if not version:
        return None

    # Parse version (e.g., "git version 2.39.3" or "git version 2.39.3 (Apple Git-145)")
    # Extract the version number (third word or second word if starts with number)
    words = version.split()
    version_str = ""
    for word in words:
        if word and word[0].isdigit():
            version_str = word
            break

    if not version_str:
        return None

    try:
        parts = version_str.split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0

        if major < 2 or (major == 2 and minor < 20):
            return CheckResult(
                name="Git Version (Worktrees)",
                passed=True,  # Still pass, just warn
                message=f"Git {version_str} works, but 2.20+ recommended for worktrees",
                severity="info",
            )

        return CheckResult(
            name="Git Version (Worktrees)",
            passed=True,
            message=f"Git {version_str} fully supports worktrees",
        )
    except (ValueError, IndexError):
        # Can't parse version, skip
        return None


def check_worktree_branch_conflicts(cwd: Path | None = None) -> CheckResult | None:
    """Check for branches that are checked out in multiple worktrees.

    This is a common source of confusion when switching worktrees.
    Git prevents checking out a branch that's already checked out elsewhere.

    Args:
        cwd: Directory to check (defaults to current working directory).

    Returns:
        CheckResult with branch conflict status, or None if not in a git repo.
    """
    if cwd is None:
        cwd = Path.cwd()

    worktree_data = _parse_worktree_porcelain(cwd)
    if len(worktree_data) < 2:
        # Need at least 2 worktrees for conflicts
        return None

    # Build a map of branch -> worktrees
    branch_worktrees: dict[str, list[str]] = {}
    for wt in worktree_data:
        branch = wt.get("branch")
        if branch:
            path = Path(wt.get("path", "")).name
            if branch not in branch_worktrees:
                branch_worktrees[branch] = []
            branch_worktrees[branch].append(path)

    # Find branches checked out in multiple worktrees
    conflicts = {branch: paths for branch, paths in branch_worktrees.items() if len(paths) > 1}

    if not conflicts:
        return None  # No conflicts to report

    # Build message
    conflict_msgs = []
    for branch, paths in conflicts.items():
        conflict_msgs.append(f"'{branch}' in: {', '.join(paths)}")

    return CheckResult(
        name="Branch Conflicts",
        passed=False,
        message=f"Branch checked out in multiple worktrees: {'; '.join(conflict_msgs)}",
        fix_hint="Each branch can only be checked out in one worktree at a time",
        severity="error",
    )
