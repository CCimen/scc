"""Worktree use cases and domain models."""

from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from pathlib import Path

from scc_cli.application.interaction_requests import ConfirmRequest, SelectOption, SelectRequest

# Re-export all models for backward compatibility
from scc_cli.application.worktree.models import (  # noqa: F401
    ShellCommand,
    WorktreeConfirmAction,
    WorktreeConfirmation,
    WorktreeCreateRequest,
    WorktreeCreateResult,
    WorktreeDependencies,
    WorktreeEnterOutcome,
    WorktreeEnterRequest,
    WorktreeListRequest,
    WorktreeListResult,
    WorktreeResolution,
    WorktreeSelectionItem,
    WorktreeSelectionPrompt,
    WorktreeSelectOutcome,
    WorktreeSelectRequest,
    WorktreeShellResult,
    WorktreeSummary,
    WorktreeSwitchOutcome,
    WorktreeSwitchRequest,
    WorktreeWarning,
    WorktreeWarningOutcome,
)

# Re-export operations for backward compatibility
from scc_cli.application.worktree.operations import (  # noqa: F401
    _build_shell_result,
    _cleanup_partial_worktree,
    create_worktree,
    enter_worktree_shell,
)
from scc_cli.core.errors import NotAGitRepoError, WorkspaceNotFoundError
from scc_cli.core.exit_codes import EXIT_CANCELLED
from scc_cli.ports.git_client import GitClient
from scc_cli.services.git.branch import get_display_branch
from scc_cli.services.git.worktree import WorktreeInfo


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
