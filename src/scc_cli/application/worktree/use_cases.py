"""Worktree use cases and domain models."""

from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TypeAlias

from scc_cli.application.interaction_requests import ConfirmRequest, SelectOption, SelectRequest
from scc_cli.core.constants import WORKTREE_BRANCH_PREFIX
from scc_cli.core.errors import NotAGitRepoError, WorkspaceNotFoundError, WorktreeCreationError
from scc_cli.core.exit_codes import EXIT_CANCELLED
from scc_cli.ports.dependency_installer import DependencyInstaller
from scc_cli.ports.git_client import GitClient
from scc_cli.services.git.branch import get_display_branch, sanitize_branch_name
from scc_cli.services.git.worktree import WorktreeInfo
from scc_cli.utils.locks import file_lock, lock_path


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


def list_worktrees(
    request: WorktreeListRequest,
    *,
    git_client: GitClient,
) -> WorktreeListResult:
    """List worktrees for a repository.

    Invariants:
        - Mirrors git worktree ordering and status calculations.
        - Does not emit UI output.
    """
    worktrees = git_client.list_worktrees(request.workspace_path)
    current_real = os.path.realpath(request.current_dir)
    summaries: list[WorktreeSummary] = []

    for worktree in worktrees:
        path = Path(worktree.path)
        is_current = os.path.realpath(worktree.path) == current_real
        staged = modified = untracked = 0
        status_timed_out = False
        has_changes = worktree.has_changes

        if request.verbose:
            staged, modified, untracked, status_timed_out = git_client.get_worktree_status(path)
            has_changes = (staged + modified + untracked) > 0

        summaries.append(
            WorktreeSummary.from_info(
                worktree,
                path=path,
                is_current=is_current,
                staged_count=staged,
                modified_count=modified,
                untracked_count=untracked,
                status_timed_out=status_timed_out,
                has_changes=has_changes,
            )
        )

    return WorktreeListResult(workspace_path=request.workspace_path, worktrees=tuple(summaries))


def select_worktree(
    request: WorktreeSelectRequest,
    *,
    dependencies: WorktreeDependencies,
) -> WorktreeSelectOutcome:
    """Select a worktree or branch without performing UI prompts.

    Invariants:
        - Confirmation prompts mirror existing CLI copy.
        - Branch selections trigger worktree creation only after confirmation.

    Raises:
        WorkspaceNotFoundError: If the workspace path does not exist.
        NotAGitRepoError: If the workspace is not a git repository.
        WorktreeCreationError: If creation fails after confirmation.
    """
    _require_workspace(request.workspace_path)
    if not dependencies.git_client.is_git_repo(request.workspace_path):
        raise NotAGitRepoError(path=str(request.workspace_path))

    if request.selection is not None:
        return _resolve_selection(request, dependencies)

    worktrees = list_worktrees(
        WorktreeListRequest(
            workspace_path=request.workspace_path,
            verbose=False,
            current_dir=request.current_dir,
        ),
        git_client=dependencies.git_client,
    ).worktrees
    branch_items: list[str] = []
    if request.include_branches:
        branch_items = dependencies.git_client.list_branches_without_worktrees(
            request.workspace_path
        )

    items = _build_selection_items(worktrees, branch_items)
    if not items:
        return WorktreeWarningOutcome(
            WorktreeWarning(
                title="No Worktrees or Branches",
                message="No worktrees found and no remote branches available.",
                suggestion="Create a worktree with: scc worktree create <repo> <name>",
            )
        )

    subtitle = f"{len(worktrees)} worktrees"
    if branch_items:
        subtitle += f", {len(branch_items)} branches"
    return WorktreeSelectionPrompt(
        request=_build_select_request(
            request_id="worktree-select",
            title="Select Worktree",
            subtitle=subtitle,
            items=items,
        ),
    )


def switch_worktree(
    request: WorktreeSwitchRequest,
    *,
    dependencies: WorktreeDependencies,
) -> WorktreeSwitchOutcome:
    """Resolve a worktree switch target.

    Invariants:
        - Shortcut semantics for '-' and '^' remain stable.
        - Matching behavior mirrors git worktree fuzzy matching rules.

    Raises:
        WorkspaceNotFoundError: If the workspace path does not exist.
        NotAGitRepoError: If the workspace is not a git repository.
        WorktreeCreationError: If creation fails after confirmation.
    """
    _require_workspace(request.workspace_path)
    if not dependencies.git_client.is_git_repo(request.workspace_path):
        raise NotAGitRepoError(path=str(request.workspace_path))

    if request.selection is not None:
        return _resolve_selection(
            WorktreeSelectRequest(
                workspace_path=request.workspace_path,
                include_branches=False,
                current_dir=request.current_dir,
                selection=request.selection,
            ),
            dependencies,
        )

    if request.target is None:
        worktrees = list_worktrees(
            WorktreeListRequest(
                workspace_path=request.workspace_path,
                verbose=False,
                current_dir=request.current_dir,
            ),
            git_client=dependencies.git_client,
        ).worktrees
        if not worktrees:
            return WorktreeWarningOutcome(
                WorktreeWarning(
                    title="No Worktrees",
                    message="No worktrees found for this repository.",
                    suggestion="Create one with: scc worktree create <repo> <name>",
                )
            )
        return WorktreeSelectionPrompt(
            request=_build_select_request(
                request_id="worktree-switch",
                title="Select Worktree",
                subtitle=f"{len(worktrees)} worktrees",
                items=_build_selection_items(worktrees, []),
            )
        )

    if request.target == "-":
        if not request.oldpwd:
            return WorktreeWarningOutcome(
                WorktreeWarning(
                    title="No Previous Directory",
                    message="Shell $OLDPWD is not set.",
                    suggestion="This typically means you haven't changed directories yet.",
                )
            )
        return WorktreeResolution(worktree_path=Path(request.oldpwd))

    if request.target == "^":
        main_worktree = dependencies.git_client.find_main_worktree(request.workspace_path)
        if not main_worktree:
            default_branch = dependencies.git_client.get_default_branch(request.workspace_path)
            return WorktreeWarningOutcome(
                WorktreeWarning(
                    title="No Main Worktree",
                    message=f"No worktree found for default branch '{default_branch}'.",
                    suggestion="The main branch may not have a separate worktree.",
                )
            )
        return WorktreeResolution(worktree_path=Path(main_worktree.path))

    exact_match, matches = dependencies.git_client.find_worktree_by_query(
        request.workspace_path, request.target
    )
    if exact_match:
        return WorktreeResolution(worktree_path=Path(exact_match.path))

    if not matches:
        if request.target not in ("^", "-", "@") and not request.target.startswith("@{"):
            branches = dependencies.git_client.list_branches_without_worktrees(
                request.workspace_path
            )
            if request.target in branches:
                if request.confirm_create is False:
                    return WorktreeWarningOutcome(
                        WorktreeWarning(
                            title="Cancelled",
                            message="Cancelled.",
                            suggestion=None,
                        ),
                        exit_code=EXIT_CANCELLED,
                    )
                if request.confirm_create is True:
                    return create_worktree(
                        WorktreeCreateRequest(
                            workspace_path=request.workspace_path,
                            name=request.target,
                            base_branch=request.target,
                            install_dependencies=True,
                        ),
                        dependencies=dependencies,
                    )
                if not request.interactive_allowed:
                    return WorktreeWarningOutcome(
                        WorktreeWarning(
                            title="Branch Exists, No Worktree",
                            message=f"Branch '{request.target}' exists but has no worktree.",
                            suggestion=(
                                "Use: scc worktree create <repo> "
                                f"{request.target} --base {request.target}"
                            ),
                        )
                    )
                return WorktreeConfirmation(
                    action=WorktreeConfirmAction.CREATE_WORKTREE,
                    request=ConfirmRequest(
                        request_id="worktree-create-branch",
                        prompt=f"No worktree for '{request.target}'. Create one?",
                    ),
                    default_response=False,
                    branch_name=request.target,
                )

        return WorktreeWarningOutcome(
            WorktreeWarning(
                title="Worktree Not Found",
                message=f"No worktree matches '{request.target}'.",
                suggestion="Tip: Use 'scc worktree select --branches' to pick from remote branches.",
            )
        )

    if request.interactive_allowed:
        return WorktreeSelectionPrompt(
            request=_build_select_request(
                request_id="worktree-switch",
                title="Multiple Matches",
                subtitle=f"'{request.target}' matches {len(matches)} worktrees",
                items=_build_selection_items(_summaries_from_matches(matches), []),
            ),
            initial_filter=request.target,
        )

    match_lines = []
    for i, match in enumerate(matches):
        display_branch = get_display_branch(match.branch)
        dir_name = Path(match.path).name
        if i == 0:
            match_lines.append(
                f"  1. [bold]{display_branch}[/] -> {dir_name}  [dim]<- best match[/]"
            )
        else:
            match_lines.append(f"  {i + 1}. {display_branch} -> {dir_name}")
    top_match_dir = Path(matches[0].path).name

    return WorktreeWarningOutcome(
        WorktreeWarning(
            title="Ambiguous Match",
            message=f"'{request.target}' matches {len(matches)} worktrees (ranked by relevance):",
            suggestion=(
                "\n".join(match_lines)
                + f"\n\n[dim]Use explicit directory name: scc worktree switch {top_match_dir}[/]"
            ),
        )
    )


def enter_worktree_shell(
    request: WorktreeEnterRequest,
    *,
    dependencies: WorktreeDependencies,
) -> WorktreeEnterOutcome:
    """Resolve a worktree target into a shell command.

    Invariants:
        - Shell resolution mirrors platform defaults.
        - Worktree existence is verified before returning a command.

    Raises:
        WorkspaceNotFoundError: If the workspace path does not exist.
        NotAGitRepoError: If the workspace is not a git repository.
    """
    _require_workspace(request.workspace_path)
    if not dependencies.git_client.is_git_repo(request.workspace_path):
        raise NotAGitRepoError(path=str(request.workspace_path))

    if request.selection is not None:
        return _build_shell_result(request, request.selection)

    if request.target is None:
        worktrees = list_worktrees(
            WorktreeListRequest(
                workspace_path=request.workspace_path,
                verbose=False,
                current_dir=request.current_dir,
            ),
            git_client=dependencies.git_client,
        ).worktrees
        if not worktrees:
            return WorktreeWarningOutcome(
                WorktreeWarning(
                    title="No Worktrees",
                    message="No worktrees found for this repository.",
                    suggestion="Create one with: scc worktree create <repo> <name>",
                )
            )
        return WorktreeSelectionPrompt(
            request=_build_select_request(
                request_id="worktree-enter",
                title="Enter Worktree",
                subtitle="Select a worktree to enter",
                items=_build_selection_items(worktrees, []),
            )
        )

    if request.target == "-":
        if not request.oldpwd:
            return WorktreeWarningOutcome(
                WorktreeWarning(
                    title="No Previous Directory",
                    message="Shell $OLDPWD is not set.",
                    suggestion="This typically means you haven't changed directories yet.",
                )
            )
        selection = WorktreeSelectionItem(
            item_id="oldpwd",
            branch=Path(request.oldpwd).name,
            worktree=WorktreeSummary(
                path=Path(request.oldpwd),
                branch=Path(request.oldpwd).name,
                status="",
                is_current=False,
                has_changes=False,
                staged_count=0,
                modified_count=0,
                untracked_count=0,
                status_timed_out=False,
            ),
            is_branch_only=False,
        )
        return _build_shell_result(request, selection)

    if request.target == "^":
        default_branch = dependencies.git_client.get_default_branch(request.workspace_path)
        worktrees = list_worktrees(
            WorktreeListRequest(
                workspace_path=request.workspace_path,
                verbose=False,
                current_dir=request.current_dir,
            ),
            git_client=dependencies.git_client,
        ).worktrees
        selected = None
        for worktree in worktrees:
            if worktree.branch == default_branch or worktree.branch in {"main", "master"}:
                selected = worktree
                break
        if not selected:
            return WorktreeWarningOutcome(
                WorktreeWarning(
                    title="Main Branch Not Found",
                    message=f"No worktree found for main branch ({default_branch}).",
                    suggestion="The main worktree may be in a different location.",
                )
            )
        selection = WorktreeSelectionItem(
            item_id=f"worktree:{selected.path}",
            branch=selected.branch or selected.path.name,
            worktree=selected,
            is_branch_only=False,
        )
        return _build_shell_result(request, selection)

    matched, _matches = dependencies.git_client.find_worktree_by_query(
        request.workspace_path, request.target
    )
    if not matched:
        return WorktreeWarningOutcome(
            WorktreeWarning(
                title="Worktree Not Found",
                message=f"No worktree matching '{request.target}'.",
                suggestion="Run 'scc worktree list' to see available worktrees.",
            )
        )
    selection = WorktreeSelectionItem(
        item_id=f"worktree:{matched.path}",
        branch=matched.branch or Path(matched.path).name,
        worktree=WorktreeSummary(
            path=Path(matched.path),
            branch=matched.branch,
            status=matched.status,
            is_current=False,
            has_changes=matched.has_changes,
            staged_count=matched.staged_count,
            modified_count=matched.modified_count,
            untracked_count=matched.untracked_count,
            status_timed_out=matched.status_timed_out,
        ),
        is_branch_only=False,
    )
    return _build_shell_result(request, selection)


def create_worktree(
    request: WorktreeCreateRequest,
    *,
    dependencies: WorktreeDependencies,
) -> WorktreeCreateResult:
    """Create a worktree using git and dependency installer ports.

    Invariants:
        - Uses the same branch naming and lock behavior as the CLI.
        - Cleans up partially created worktrees on failure.

    Raises:
        NotAGitRepoError: If the workspace is not a git repository.
        WorktreeCreationError: If worktree creation fails.
    """
    if not dependencies.git_client.is_git_repo(request.workspace_path):
        raise NotAGitRepoError(path=str(request.workspace_path))

    safe_name = sanitize_branch_name(request.name)
    if not safe_name:
        raise ValueError(f"Invalid worktree name: {request.name!r}")

    branch_name = f"{WORKTREE_BRANCH_PREFIX}{safe_name}"
    worktree_base = request.workspace_path.parent / f"{request.workspace_path.name}-worktrees"
    worktree_path = worktree_base / safe_name

    lock_file = lock_path("worktree", request.workspace_path)
    with file_lock(lock_file):
        if worktree_path.exists():
            raise WorktreeCreationError(
                name=safe_name,
                user_message=f"Worktree already exists: {worktree_path}",
                suggested_action="Use existing worktree, remove it first, or choose a different name",
            )

        base_branch = request.base_branch or dependencies.git_client.get_default_branch(
            request.workspace_path
        )

        if dependencies.git_client.has_remote(request.workspace_path):
            dependencies.git_client.fetch_branch(request.workspace_path, base_branch)

        worktree_created = False
        try:
            dependencies.git_client.add_worktree(
                request.workspace_path,
                worktree_path,
                branch_name,
                base_branch,
            )
            worktree_created = True

            dependencies_installed = None
            if request.install_dependencies:
                install_result = dependencies.dependency_installer.install(worktree_path)
                if install_result.attempted and not install_result.success:
                    raise WorktreeCreationError(
                        name=safe_name,
                        user_message="Dependency install failed for the new worktree",
                        suggested_action="Install dependencies manually and retry if needed",
                    )
                if install_result.attempted:
                    dependencies_installed = install_result.success

            return WorktreeCreateResult(
                worktree_path=worktree_path,
                worktree_name=safe_name,
                branch_name=branch_name,
                base_branch=base_branch,
                dependencies_installed=dependencies_installed,
            )
        except KeyboardInterrupt:
            if worktree_created or worktree_path.exists():
                _cleanup_partial_worktree(
                    request.workspace_path, worktree_path, dependencies.git_client
                )
            raise
        except WorktreeCreationError:
            if worktree_created or worktree_path.exists():
                _cleanup_partial_worktree(
                    request.workspace_path, worktree_path, dependencies.git_client
                )
            raise
        except Exception as exc:
            if worktree_created or worktree_path.exists():
                _cleanup_partial_worktree(
                    request.workspace_path, worktree_path, dependencies.git_client
                )
            raise WorktreeCreationError(
                name=safe_name,
                user_message=f"Failed to create worktree: {safe_name}",
                suggested_action="Check if the branch already exists or if there are uncommitted changes",
                command=str(getattr(exc, "cmd", "")) or None,
            ) from exc


def _cleanup_partial_worktree(repo_path: Path, worktree_path: Path, git_client: GitClient) -> None:
    try:
        git_client.remove_worktree(repo_path, worktree_path, force=True)
    except Exception:
        pass
    try:
        git_client.prune_worktrees(repo_path)
    except Exception:
        pass


def _require_workspace(workspace_path: Path) -> None:
    if not workspace_path.exists():
        raise WorkspaceNotFoundError(path=str(workspace_path))


def _build_selection_items(
    worktrees: Iterable[WorktreeSummary],
    branches: Sequence[str],
) -> list[WorktreeSelectionItem]:
    items: list[WorktreeSelectionItem] = []
    for worktree in worktrees:
        items.append(
            WorktreeSelectionItem(
                item_id=f"worktree:{worktree.path}",
                branch=worktree.branch,
                worktree=worktree,
                is_branch_only=False,
            )
        )
    for branch in branches:
        items.append(
            WorktreeSelectionItem(
                item_id=f"branch:{branch}",
                branch=branch,
                worktree=None,
                is_branch_only=True,
            )
        )
    return items


def _build_select_request(
    *,
    request_id: str,
    title: str,
    subtitle: str | None,
    items: Sequence[WorktreeSelectionItem],
) -> SelectRequest[WorktreeSelectionItem]:
    options = [
        SelectOption(
            option_id=item.item_id,
            label=item.branch or (item.path.name if item.path else item.item_id),
            description=None,
            value=item,
        )
        for item in items
    ]
    return SelectRequest(
        request_id=request_id,
        title=title,
        subtitle=subtitle,
        options=options,
        allow_back=False,
    )


def _resolve_selection(
    request: WorktreeSelectRequest,
    dependencies: WorktreeDependencies,
) -> WorktreeSelectOutcome:
    selection = request.selection
    if selection is None:
        raise ValueError("Selection must be provided to resolve a worktree selection")

    if not selection.is_branch_only:
        if not selection.path:
            raise ValueError("Selection missing worktree path")
        worktree_name = selection.branch or selection.path.name
        return WorktreeResolution(worktree_path=selection.path, worktree_name=worktree_name)

    if request.confirm_create is None:
        return WorktreeConfirmation(
            action=WorktreeConfirmAction.CREATE_WORKTREE,
            request=ConfirmRequest(
                request_id="worktree-create-branch",
                prompt=f"Create worktree for branch '{selection.branch}'?",
            ),
            default_response=True,
            branch_name=selection.branch,
        )

    if not request.confirm_create:
        return WorktreeWarningOutcome(
            WorktreeWarning(
                title="Cancelled",
                message="Cancelled.",
                suggestion=None,
            ),
            exit_code=EXIT_CANCELLED,
        )

    return create_worktree(
        WorktreeCreateRequest(
            workspace_path=request.workspace_path,
            name=selection.branch,
            base_branch=selection.branch,
            install_dependencies=True,
        ),
        dependencies=dependencies,
    )


def _summaries_from_matches(matches: Sequence[WorktreeInfo]) -> list[WorktreeSummary]:
    summaries = []
    for match in matches:
        summaries.append(
            WorktreeSummary(
                path=Path(match.path),
                branch=match.branch,
                status=match.status,
                is_current=match.is_current,
                has_changes=match.has_changes,
                staged_count=match.staged_count,
                modified_count=match.modified_count,
                untracked_count=match.untracked_count,
                status_timed_out=match.status_timed_out,
            )
        )
    return summaries


def _build_shell_result(
    request: WorktreeEnterRequest,
    selection: WorktreeSelectionItem,
) -> WorktreeShellResult | WorktreeWarningOutcome:
    if not selection.path:
        raise ValueError("Selection must include a worktree path")

    if not selection.path.exists():
        return WorktreeWarningOutcome(
            WorktreeWarning(
                title="Worktree Missing",
                message=f"Worktree path does not exist: {selection.path}",
                suggestion="The worktree may have been removed. Run 'scc worktree prune'.",
            )
        )

    env = dict(request.env)
    worktree_name = selection.branch or selection.path.name
    env["SCC_WORKTREE"] = worktree_name

    if request.platform_system == "Windows":
        shell = env.get("COMSPEC", "cmd.exe")
    else:
        shell = env.get("SHELL", "/bin/bash")

    return WorktreeShellResult(
        shell_command=ShellCommand(argv=[shell], workdir=selection.path, env=env),
        worktree_path=selection.path,
        worktree_name=worktree_name,
    )
