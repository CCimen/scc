"""Git services - data operations without UI dependencies.

This package contains pure data functions for git operations.
UI rendering is handled separately in ui/git_render.py.
"""

from .branch import (
    PROTECTED_BRANCHES,
    get_current_branch,
    get_default_branch,
    get_display_branch,
    get_uncommitted_files,
    is_protected_branch,
    list_branches_without_worktrees,
    sanitize_branch_name,
)
from .core import (
    check_git_available,
    check_git_installed,
    create_empty_initial_commit,
    detect_workspace_root,
    get_git_version,
    has_commits,
    has_remote,
    init_repo,
    is_file_ignored,
    is_git_repo,
)
from .hooks import (
    SCC_HOOK_MARKER,
    install_pre_push_hook,
    is_scc_hook,
)
from .worktree import (
    WorktreeInfo,
    find_main_worktree,
    find_worktree_by_query,
    get_workspace_mount_path,
    get_worktree_main_repo,
    get_worktree_status,
    get_worktrees_data,
    is_worktree,
)

__all__ = [
    # Core
    "check_git_available",
    "check_git_installed",
    "get_git_version",
    "is_git_repo",
    "is_file_ignored",
    "has_commits",
    "init_repo",
    "create_empty_initial_commit",
    "has_remote",
    "detect_workspace_root",
    # Branch
    "PROTECTED_BRANCHES",
    "is_protected_branch",
    "get_current_branch",
    "get_default_branch",
    "sanitize_branch_name",
    "get_display_branch",
    "get_uncommitted_files",
    "list_branches_without_worktrees",
    # Worktree
    "WorktreeInfo",
    "get_worktrees_data",
    "get_worktree_status",
    "is_worktree",
    "get_worktree_main_repo",
    "get_workspace_mount_path",
    "find_worktree_by_query",
    "find_main_worktree",
    # Hooks
    "SCC_HOOK_MARKER",
    "is_scc_hook",
    "install_pre_push_hook",
]
