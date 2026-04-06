"""Worktree domain models and request/result dataclasses."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TypeAlias

from scc_cli.application.interaction_requests import ConfirmRequest, SelectRequest
from scc_cli.ports.dependency_installer import DependencyInstaller
from scc_cli.ports.git_client import GitClient
from scc_cli.services.git.worktree import WorktreeInfo


@dataclass(frozen=True)
class WorktreeSummary:
    """Summary of a git worktree for selection and listing.

    Invariants:
        - Paths are absolute and refer to host filesystem locations.
        - Counts are zero when status data is unavailable.

    Args:
        path: Filesystem path to the worktree.
        branch: Branch name (may be empty for detached/bare worktrees).
        status: Raw status string from git worktree list.
        is_current: Whether this worktree matches the current working directory.
        has_changes: Whether the worktree has staged/modified/untracked files.
        staged_count: Number of staged files.
        modified_count: Number of modified files.
        untracked_count: Number of untracked files.
        status_timed_out: Whether status collection timed out.
    """

    path: Path
    branch: str
    status: str
    is_current: bool
    has_changes: bool
    staged_count: int
    modified_count: int
    untracked_count: int
    status_timed_out: bool

    @classmethod
    def from_info(
        cls,
        info: WorktreeInfo,
        *,
        path: Path,
        is_current: bool,
        staged_count: int,
        modified_count: int,
        untracked_count: int,
        status_timed_out: bool,
        has_changes: bool,
    ) -> WorktreeSummary:
        """Build a WorktreeSummary from a WorktreeInfo record."""
        return cls(
            path=path,
            branch=info.branch,
            status=info.status,
            is_current=is_current,
            has_changes=has_changes,
            staged_count=staged_count,
            modified_count=modified_count,
            untracked_count=untracked_count,
            status_timed_out=status_timed_out,
        )


@dataclass(frozen=True)
class WorktreeListRequest:
    """Inputs for listing worktrees.

    Invariants:
        - Current directory is provided for stable current-worktree detection.

    Args:
        workspace_path: Repository root path.
        verbose: Whether to include git status counts.
        current_dir: Current working directory for current-worktree detection.
    """

    workspace_path: Path
    verbose: bool
    current_dir: Path


@dataclass(frozen=True)
class WorktreeListResult:
    """Worktree list output for rendering at the edge.

    Invariants:
        - Worktrees preserve the ordering returned by git.

    Args:
        workspace_path: Repository root path.
        worktrees: Tuple of worktree summaries.
    """

    workspace_path: Path
    worktrees: tuple[WorktreeSummary, ...]


@dataclass(frozen=True)
class WorktreeSelectionItem:
    """Selectable worktree or branch entry.

    Invariants:
        - Branch-only entries have no worktree path.

    Args:
        item_id: Stable identifier for selection tracking.
        branch: Branch name associated with the item.
        worktree: Worktree summary if this item represents a worktree.
        is_branch_only: True when this item represents a branch without worktree.
    """

    item_id: str
    branch: str
    worktree: WorktreeSummary | None
    is_branch_only: bool

    @property
    def path(self) -> Path | None:
        """Return the worktree path if present."""
        if not self.worktree:
            return None
        return self.worktree.path


@dataclass(frozen=True)
class WorktreeSelectionPrompt:
    """Selection prompt metadata for interactive worktree choices.

    Invariants:
        - Selection options must map to WorktreeSelectionItem values.

    Args:
        request: SelectRequest describing the options.
        initial_filter: Optional query used to seed interactive filters.
    """

    request: SelectRequest[WorktreeSelectionItem]
    initial_filter: str = ""


@dataclass(frozen=True)
class WorktreeWarning:
    """User-facing warning metadata.

    Invariants:
        - Titles and messages remain stable for characterization tests.

    Args:
        title: Warning title for panel rendering.
        message: Warning body text.
        suggestion: Optional follow-up guidance.
    """

    title: str
    message: str
    suggestion: str | None = None


@dataclass(frozen=True)
class WorktreeWarningOutcome:
    """Warning outcome with an exit code hint.

    Args:
        warning: Warning metadata to render.
        exit_code: Suggested exit code for the command.
    """

    warning: WorktreeWarning
    exit_code: int = 1


class WorktreeConfirmAction(str, Enum):
    """Confirm action identifiers for worktree flows."""

    CREATE_WORKTREE = "create-worktree"


@dataclass(frozen=True)
class WorktreeConfirmation:
    """Confirmation request for follow-up actions.

    Invariants:
        - Prompts mirror existing CLI confirmations.

    Args:
        action: Action that requires confirmation.
        request: ConfirmRequest describing the prompt.
        default_response: Default response value for UI adapters.
        branch_name: Optional branch name for creation actions.
    """

    action: WorktreeConfirmAction
    request: ConfirmRequest
    default_response: bool
    branch_name: str | None = None


@dataclass(frozen=True)
class WorktreeResolution:
    """Resolved worktree path for shell integration.

    Args:
        worktree_path: Resolved worktree path to output.
        worktree_name: Optional worktree name for environment configuration.
    """

    worktree_path: Path
    worktree_name: str | None = None


@dataclass(frozen=True)
class WorktreeCreateRequest:
    """Inputs for creating a new worktree.

    Invariants:
        - Name is sanitized for branch creation.
        - Base branch defaults follow git default branch logic.

    Args:
        workspace_path: Repository root path.
        name: Worktree name (feature name).
        base_branch: Optional base branch override.
        install_dependencies: Whether to install dependencies after creation.
    """

    workspace_path: Path
    name: str
    base_branch: str | None
    install_dependencies: bool = True


@dataclass(frozen=True)
class WorktreeCreateResult:
    """Result of creating a new worktree.

    Args:
        worktree_path: Filesystem path to the created worktree.
        worktree_name: Sanitized worktree name.
        branch_name: Full branch name created for the worktree.
        base_branch: Base branch used for the worktree.
        dependencies_installed: Whether dependency installation succeeded.
    """

    worktree_path: Path
    worktree_name: str
    branch_name: str
    base_branch: str
    dependencies_installed: bool | None


@dataclass(frozen=True)
class ShellCommand:
    """Shell command specification for entering a worktree."""

    argv: list[str]
    workdir: Path
    env: dict[str, str]


@dataclass(frozen=True)
class WorktreeShellResult:
    """Shell entry details for a worktree."""

    shell_command: ShellCommand
    worktree_path: Path
    worktree_name: str


WorktreeSelectOutcome: TypeAlias = (
    WorktreeResolution
    | WorktreeSelectionPrompt
    | WorktreeWarningOutcome
    | WorktreeConfirmation
    | WorktreeCreateResult
)
WorktreeSwitchOutcome: TypeAlias = WorktreeSelectOutcome
WorktreeEnterOutcome: TypeAlias = (
    WorktreeShellResult | WorktreeSelectionPrompt | WorktreeWarningOutcome
)


@dataclass(frozen=True)
class WorktreeDependencies:
    """Dependencies for worktree use cases."""

    git_client: GitClient
    dependency_installer: DependencyInstaller


@dataclass(frozen=True)
class WorktreeSelectRequest:
    """Inputs for selecting a worktree or branch.

    Args:
        workspace_path: Repository root path.
        include_branches: Whether to include branches without worktrees.
        current_dir: Current working directory for current-worktree detection.
        selection: Selected item from a prior prompt (if any).
        confirm_create: Confirmation response for branch creation.
    """

    workspace_path: Path
    include_branches: bool
    current_dir: Path
    selection: WorktreeSelectionItem | None = None
    confirm_create: bool | None = None


@dataclass(frozen=True)
class WorktreeSwitchRequest:
    """Inputs for switching to a worktree.

    Args:
        workspace_path: Repository root path.
        target: Target name or shortcut.
        oldpwd: Shell OLDPWD value for '-' shortcut.
        interactive_allowed: Whether prompts may be shown.
        current_dir: Current working directory for current-worktree detection.
        selection: Selected item from a prior prompt (if any).
        confirm_create: Confirmation response for branch creation.
    """

    workspace_path: Path
    target: str | None
    oldpwd: str | None
    interactive_allowed: bool
    current_dir: Path
    selection: WorktreeSelectionItem | None = None
    confirm_create: bool | None = None


@dataclass(frozen=True)
class WorktreeEnterRequest:
    """Inputs for entering a worktree in a subshell.

    Args:
        workspace_path: Repository root path.
        target: Target name or shortcut.
        oldpwd: Shell OLDPWD value for '-' shortcut.
        interactive_allowed: Whether prompts may be shown.
        current_dir: Current working directory for current-worktree detection.
        env: Environment mapping for shell resolution.
        platform_system: Platform system name (e.g., "Windows", "Linux").
        selection: Selected item from a prior prompt (if any).
    """

    workspace_path: Path
    target: str | None
    oldpwd: str | None
    interactive_allowed: bool
    current_dir: Path
    env: dict[str, str]
    platform_system: str
    selection: WorktreeSelectionItem | None = None
