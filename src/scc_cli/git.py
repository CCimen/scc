"""
Git operations - backward-compatible facade.

This module re-exports the pure git service API from services/git for backward
compatibility (e.g. `from scc_cli.git import WorktreeInfo`).

UI helpers now live in `scc_cli.ui.git_interactive` and `scc_cli.ui.git_render`
and should be imported directly.

No Rich imports are allowed in this module.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# Re-exports from services/git/ for backward compatibility
# These imports ARE used - they're intentional re-exports for the public API
# ═══════════════════════════════════════════════════════════════════════════════

# Branch operations
from .services.git.branch import (  # noqa: F401
    PROTECTED_BRANCHES,
    get_current_branch,
    get_default_branch,
    get_display_branch,
    get_uncommitted_files,
    is_protected_branch,
    list_branches_without_worktrees,
    sanitize_branch_name,
)

# Core operations
from .services.git.core import (  # noqa: F401
    check_git_available,
    check_git_installed,
    create_empty_initial_commit,
    detect_workspace_root,
    get_git_version,
    has_commits,
    has_remote,
    init_repo,
    is_git_repo,
)

# Hooks
from .services.git.hooks import (  # noqa: F401
    SCC_HOOK_MARKER,
    _write_scc_hook,
    install_pre_push_hook,
    is_scc_hook,
)

# Worktree operations
from .services.git.worktree import (  # noqa: F401
    WorktreeInfo,
    find_main_worktree,
    find_worktree_by_query,
    get_workspace_mount_path,
    get_worktree_main_repo,
    get_worktree_status,
    is_worktree,
)

# Keep _get_worktrees_data as alias for backward compatibility
from .services.git.worktree import get_worktrees_data as _get_worktrees_data  # noqa: F401
