"""Git command analysis for detecting destructive operations.

This module analyzes git commands and returns typed SafetyVerdict objects
for destructive operations that could damage remote history or local work.

Lifted from the scc-safety-net plugin into core. All analyze_* functions
return SafetyVerdict | None instead of raw strings.

Blocked operations (v0.2.0):
- git push --force / -f / +refspec
- git push --mirror
- git reset --hard
- git branch -D
- git stash drop / clear
- git clean -f / -fd / -xfd
- git checkout -- <path>
- git restore <path> (worktree, not --staged)
- git reflog expire --expire-unreachable=now
- git gc --prune=now
- git filter-branch (always blocked)
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .contracts import SafetyVerdict
from .enums import CommandFamily

# ─────────────────────────────────────────────────────────────────────────────
# Git Global Option Handling
# ─────────────────────────────────────────────────────────────────────────────

# Git global options that take a value (skip both flag and value)
GIT_GLOBAL_OPTIONS_WITH_VALUE = frozenset({"-C", "-c", "--git-dir", "--work-tree"})

# Git global options that combine flag=value
GIT_GLOBAL_OPTIONS_COMBINED = ("--git-dir=", "--work-tree=")


def normalize_git_tokens(tokens: list[str]) -> tuple[str, list[str]]:
    """Extract subcommand and args, skipping global git options.

    Handles:
    - /usr/bin/git → git
    - git -C /path push → push
    - git --git-dir=.git push → push

    Args:
        tokens: Full command tokens starting with git

    Returns:
        Tuple of (subcommand, remaining_args)
    """
    if not tokens:
        return "", []

    # Check if first token is git (handle /usr/bin/git)
    if Path(tokens[0]).name != "git":
        return "", []

    i = 1
    while i < len(tokens):
        token = tokens[i]

        # Handle -C, -c, --git-dir, --work-tree (with separate value)
        if token in GIT_GLOBAL_OPTIONS_WITH_VALUE:
            i += 2  # Skip option and its value
        # Handle --git-dir=.git, --work-tree=/path
        elif any(token.startswith(prefix) for prefix in GIT_GLOBAL_OPTIONS_COMBINED):
            i += 1  # Skip combined option=value
        else:
            break

    if i >= len(tokens):
        return "", []

    return tokens[i], tokens[i + 1 :]


# ─────────────────────────────────────────────────────────────────────────────
# Force Push Detection
# ─────────────────────────────────────────────────────────────────────────────


def has_force_flag(args: list[str]) -> bool:
    """Detect force flags including combined short options.

    Matches: -f, --force, -xfd (contains -f)

    IMPORTANT: Only apply this function for git subcommands where -f
    means "force" (push, clean, branch -D). Do NOT apply globally -
    some subcommands use -f for different meanings.

    Args:
        args: Command arguments (after subcommand)

    Returns:
        True if force flag detected
    """
    for token in args:
        if token == "-f" or token == "--force":
            return True
        # Combined short flags: -xfd contains -f
        # Must start with - but not -- (long options)
        if token.startswith("-") and not token.startswith("--") and "f" in token:
            return True
    return False


def has_force_refspec(args: list[str]) -> bool:
    """Detect force push via +refspec patterns.

    Matches: +main, +main:main, HEAD:+main, origin/+main

    Args:
        args: Command arguments (after subcommand)

    Returns:
        True if +refspec force push pattern detected
    """
    for token in args:
        # Skip flags
        if token.startswith("-"):
            continue
        # +ref at start of token
        if token.startswith("+") and not token.startswith("++"):
            return True
        # ref:+ref pattern (e.g., HEAD:+main)
        if ":+" in token:
            return True
    return False


def has_force_with_lease(args: list[str]) -> bool:
    """Check if --force-with-lease is present (safe force push).

    Args:
        args: Command arguments

    Returns:
        True if --force-with-lease is present
    """
    return any(arg.startswith("--force-with-lease") for arg in args)


# ─────────────────────────────────────────────────────────────────────────────
# Destructive Command Detection
# ─────────────────────────────────────────────────────────────────────────────

# Block reasons with safe alternatives
BLOCK_MESSAGES: dict[str, str] = {
    "force_push": (
        "BLOCKED: Force push destroys remote history.\n\n"
        "Safe alternative: git push --force-with-lease"
    ),
    "push_mirror": (
        "BLOCKED: git push --mirror overwrites entire remote.\n\n"
        "Safe alternative: git push (regular push)"
    ),
    "reflog_expire": (
        "BLOCKED: reflog expire --expire-unreachable=now destroys recovery history.\n\n"
        "Safe alternative: Don't manually expire reflog; let Git handle it"
    ),
    "gc_prune": (
        "BLOCKED: git gc --prune=now immediately deletes objects.\n\n"
        "Safe alternative: git gc (default prune with grace period)"
    ),
    "filter_branch": (
        "BLOCKED: git filter-branch rewrites history destructively.\n\n"
        "Safe alternative: git filter-repo (external tool with safety checks)"
    ),
    "reset_hard": (
        "BLOCKED: git reset --hard destroys uncommitted changes.\n\n"
        "Safe alternative: git stash (preserves changes)"
    ),
    "branch_force_delete": (
        "BLOCKED: git branch -D force-deletes without merge check.\n\n"
        "Safe alternative: git branch -d (requires merge check)"
    ),
    "stash_drop": (
        "BLOCKED: git stash drop permanently deletes stash entry.\n\n"
        "Safe alternative: Review with git stash list first"
    ),
    "stash_clear": (
        "BLOCKED: git stash clear permanently deletes ALL stashes.\n\n"
        "Safe alternative: Review with git stash list first"
    ),
    "clean_force": (
        "BLOCKED: git clean -f destroys untracked files.\n\n"
        "Safe alternative: git clean -n (dry-run preview)"
    ),
    "checkout_path": (
        "BLOCKED: git checkout -- <path> destroys uncommitted changes.\n\n"
        "Safe alternative: git stash (preserves changes)"
    ),
    "restore_worktree": (
        "BLOCKED: git restore <path> destroys uncommitted changes.\n\n"
        "Safe alternatives:\n"
        "  - git stash (preserves changes)\n"
        "  - git restore --staged <path> (only unstages, doesn't discard)"
    ),
}

# Maps BLOCK_MESSAGES key → matched_rule identifier
_RULE_NAMES: dict[str, str] = {
    "force_push": "git.force_push",
    "push_mirror": "git.push_mirror",
    "reflog_expire": "git.reflog_expire",
    "gc_prune": "git.gc_prune",
    "filter_branch": "git.filter_branch",
    "reset_hard": "git.reset_hard",
    "branch_force_delete": "git.branch_force_delete",
    "stash_drop": "git.stash_drop",
    "stash_clear": "git.stash_clear",
    "clean_force": "git.clean_force",
    "checkout_path": "git.checkout_path",
    "restore_worktree": "git.restore_worktree",
}


def _block(key: str) -> SafetyVerdict:
    """Build a block SafetyVerdict from a BLOCK_MESSAGES key."""
    return SafetyVerdict(
        allowed=False,
        reason=BLOCK_MESSAGES[key],
        matched_rule=_RULE_NAMES[key],
        command_family=CommandFamily.DESTRUCTIVE_GIT,
    )


def analyze_push(args: list[str]) -> SafetyVerdict | None:
    """Analyze git push for destructive patterns.

    Blocks:
    - git push --force
    - git push -f
    - git push +refspec
    - git push --mirror

    Allows:
    - git push --force-with-lease
    """
    # Block --mirror (overwrites entire remote)
    if "--mirror" in args:
        return _block("push_mirror")

    # Allow --force-with-lease (safe)
    if has_force_with_lease(args):
        return None

    # Block --force, -f, or combined flags containing 'f'
    if has_force_flag(args):
        return _block("force_push")

    # Block +refspec patterns
    if has_force_refspec(args):
        return _block("force_push")

    return None


def analyze_reset(args: list[str]) -> SafetyVerdict | None:
    """Analyze git reset for destructive patterns.

    Blocks:
    - git reset --hard

    Allows:
    - git reset (default mixed)
    - git reset --soft
    - git reset --mixed
    """
    if "--hard" in args:
        return _block("reset_hard")
    return None


def analyze_branch(args: list[str]) -> SafetyVerdict | None:
    """Analyze git branch for destructive patterns.

    Blocks:
    - git branch -D (force delete)
    - git branch --delete --force

    Allows:
    - git branch -d (safe delete with merge check)
    """
    # Check for -D specifically (uppercase)
    if "-D" in args:
        return _block("branch_force_delete")

    # Check for combined --delete --force
    has_delete = "--delete" in args or any(
        a.startswith("-") and not a.startswith("--") and "d" in a.lower() for a in args
    )
    if has_delete and "--force" in args:
        return _block("branch_force_delete")

    return None


def analyze_stash(args: list[str]) -> SafetyVerdict | None:
    """Analyze git stash for destructive patterns.

    Blocks:
    - git stash drop
    - git stash clear

    Allows:
    - git stash (push)
    - git stash pop
    - git stash apply
    - git stash list
    """
    if not args:
        return None

    subcommand = args[0]
    if subcommand == "drop":
        return _block("stash_drop")
    if subcommand == "clear":
        return _block("stash_clear")

    return None


def analyze_clean(args: list[str]) -> SafetyVerdict | None:
    """Analyze git clean for destructive patterns.

    Blocks:
    - git clean -f
    - git clean -fd
    - git clean -xfd
    - Any combination containing -f without -n/--dry-run

    Allows:
    - git clean -n (dry-run)
    - git clean --dry-run
    """
    # Allow dry-run mode
    has_dry_run = "-n" in args or "--dry-run" in args
    if has_dry_run:
        return None

    # Block any force flag (including combined like -xfd)
    if has_force_flag(args):
        return _block("clean_force")

    return None


def analyze_checkout(args: list[str]) -> SafetyVerdict | None:
    """Analyze git checkout for destructive patterns.

    Blocks:
    - git checkout -- <path>
    - git checkout HEAD -- <path>
    - git checkout <branch> -- <path> (when reverting changes)

    Allows:
    - git checkout <branch> (switching branches)
    - git checkout -b <branch> (creating branch)
    """
    if not args:
        return None

    # Look for -- separator (indicates path checkout)
    try:
        separator_idx = args.index("--")
        # If there are paths after --, this is a destructive path checkout
        if separator_idx < len(args) - 1:
            return _block("checkout_path")
    except ValueError:
        pass

    return None


def analyze_restore(args: list[str]) -> SafetyVerdict | None:
    """Analyze git restore for destructive patterns.

    Blocks:
    - git restore <path> (worktree restore)
    - git restore --worktree <path>

    Allows:
    - git restore --staged <path> (only unstages)
    """
    if not args:
        return None

    # Allow --staged only (safe: just unstages)
    has_staged = "--staged" in args or "-S" in args
    has_worktree = "--worktree" in args or "-W" in args

    # If only --staged and not --worktree, it's safe
    if has_staged and not has_worktree:
        return None

    # Check if there are path arguments (non-flag arguments)
    paths = [a for a in args if not a.startswith("-")]
    if paths:
        # Has paths and either:
        # - explicit --worktree, or
        # - no --staged (worktree is default for paths)
        if has_worktree or not has_staged:
            return _block("restore_worktree")

    return None


# ─────────────────────────────────────────────────────────────────────────────
# Catastrophic Command Detection (v0.2.0)
# ─────────────────────────────────────────────────────────────────────────────


def analyze_reflog(args: list[str]) -> SafetyVerdict | None:
    """Analyze git reflog for destructive patterns.

    Blocks:
    - git reflog expire --expire-unreachable=now
    - git reflog expire --expire-unreachable now

    Allows:
    - git reflog (show)
    - git reflog show
    - git reflog expire (without =now)
    """
    if "expire" not in args:
        return None

    # Handle both --expire-unreachable=now and --expire-unreachable now
    for i, token in enumerate(args):
        if "--expire-unreachable=now" in token:
            return _block("reflog_expire")
        if token == "--expire-unreachable":
            if i + 1 < len(args) and args[i + 1] == "now":
                return _block("reflog_expire")

    return None


def analyze_gc(args: list[str]) -> SafetyVerdict | None:
    """Analyze git gc for destructive patterns.

    Blocks:
    - git gc --prune=now
    - git gc --prune now

    Allows:
    - git gc (default prune with grace period)
    - git gc --prune=2.weeks.ago
    """
    # Handle both --prune=now and --prune now
    for i, token in enumerate(args):
        if "--prune=now" in token:
            return _block("gc_prune")
        if token == "--prune":
            if i + 1 < len(args) and args[i + 1] == "now":
                return _block("gc_prune")

    return None


def analyze_filter_branch(args: list[str]) -> SafetyVerdict | None:
    """Analyze git filter-branch (always blocked).

    git filter-branch is always destructive and has been
    deprecated in favor of git filter-repo.

    Blocks:
    - git filter-branch (any invocation)
    """
    # filter-branch is always destructive
    return _block("filter_branch")


# ─────────────────────────────────────────────────────────────────────────────
# Main Analysis Entry Point
# ─────────────────────────────────────────────────────────────────────────────


def analyze_git(tokens: list[str]) -> SafetyVerdict | None:
    """Analyze git command tokens for destructive operations.

    Args:
        tokens: Command tokens starting with 'git'

    Returns:
        SafetyVerdict if destructive, None if allowed
    """
    subcommand, args = normalize_git_tokens(tokens)

    if not subcommand:
        return None

    # Global DX bypass - check BEFORE any analyzer
    # git help <anything> is always safe
    if subcommand == "help":
        return None

    # --help, -h, --version flags make any command safe (just shows help)
    if "--help" in args or "-h" in args or "--version" in args:
        return None

    # Route to specific analyzers
    analyzers: dict[str, Callable[[list[str]], SafetyVerdict | None]] = {
        "push": analyze_push,
        "reset": analyze_reset,
        "branch": analyze_branch,
        "stash": analyze_stash,
        "clean": analyze_clean,
        "checkout": analyze_checkout,
        "restore": analyze_restore,
        # Catastrophic commands (v0.2.0)
        "reflog": analyze_reflog,
        "gc": analyze_gc,
        "filter-branch": analyze_filter_branch,
    }

    analyzer = analyzers.get(subcommand)
    if analyzer:
        return analyzer(args)

    return None
