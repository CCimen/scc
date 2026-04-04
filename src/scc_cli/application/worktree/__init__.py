"""Worktree application use cases."""

from scc_cli.application.worktree.models import (
    ShellCommand,
    WorktreeConfirmation,
    WorktreeCreateRequest,
    WorktreeCreateResult,
    WorktreeDependencies,
    WorktreeEnterRequest,
    WorktreeListRequest,
    WorktreeListResult,
    WorktreeResolution,
    WorktreeSelectionItem,
    WorktreeSelectionPrompt,
    WorktreeSelectRequest,
    WorktreeShellResult,
    WorktreeSummary,
    WorktreeSwitchRequest,
    WorktreeWarningOutcome,
)
from scc_cli.application.worktree.operations import (
    create_worktree,
    enter_worktree_shell,
)
from scc_cli.application.worktree.use_cases import (
    list_worktrees,
    select_worktree,
    switch_worktree,
)

__all__ = [
    "ShellCommand",
    "WorktreeConfirmation",
    "WorktreeCreateRequest",
    "WorktreeCreateResult",
    "WorktreeDependencies",
    "WorktreeEnterRequest",
    "WorktreeListRequest",
    "WorktreeListResult",
    "WorktreeResolution",
    "WorktreeSelectRequest",
    "WorktreeSelectionItem",
    "WorktreeSelectionPrompt",
    "WorktreeShellResult",
    "WorktreeSummary",
    "WorktreeSwitchRequest",
    "WorktreeWarningOutcome",
    "create_worktree",
    "enter_worktree_shell",
    "list_worktrees",
    "select_worktree",
    "switch_worktree",
]
