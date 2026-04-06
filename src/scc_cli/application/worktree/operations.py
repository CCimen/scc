"""Worktree creation and shell-entry operations."""

from __future__ import annotations

from pathlib import Path

from scc_cli.application.worktree.models import (
    ShellCommand,
    WorktreeCreateRequest,
    WorktreeCreateResult,
    WorktreeDependencies,
    WorktreeEnterOutcome,
    WorktreeEnterRequest,
    WorktreeListRequest,
    WorktreeSelectionItem,
    WorktreeShellResult,
    WorktreeSummary,
    WorktreeWarning,
    WorktreeWarningOutcome,
)
from scc_cli.core.constants import WORKTREE_BRANCH_PREFIX
from scc_cli.core.errors import NotAGitRepoError, WorktreeCreationError
from scc_cli.ports.git_client import GitClient
from scc_cli.services.git.branch import sanitize_branch_name
from scc_cli.utils.locks import file_lock, lock_path


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
    from scc_cli.application.worktree.use_cases import (
        _require_workspace,
        list_worktrees,
    )

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
        return _build_select_request_prompt(worktrees, dependencies, request)

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


def _build_select_request_prompt(
    worktrees: tuple[WorktreeSummary, ...],
    dependencies: WorktreeDependencies,
    request: WorktreeEnterRequest,
) -> WorktreeEnterOutcome:
    """Build a selection prompt for enter_worktree_shell."""
    from scc_cli.application.worktree.models import WorktreeSelectionPrompt
    from scc_cli.application.worktree.use_cases import _build_select_request, _build_selection_items

    return WorktreeSelectionPrompt(
        request=_build_select_request(
            request_id="worktree-enter",
            title="Enter Worktree",
            subtitle="Select a worktree to enter",
            items=_build_selection_items(worktrees, []),
        )
    )


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
