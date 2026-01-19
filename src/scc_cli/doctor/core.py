from __future__ import annotations

from pathlib import Path

from scc_cli.core.enums import SeverityLevel

from .checks import (
    check_config_directory,
    check_docker,
    check_docker_running,
    check_docker_sandbox,
    check_git,
    check_user_config_valid,
    check_workspace_path,
    check_wsl2,
)
from .types import DoctorResult


def run_doctor(workspace: Path | None = None) -> DoctorResult:
    """Run all health checks and return comprehensive results."""

    result = DoctorResult()

    git_check = check_git()
    result.checks.append(git_check)
    result.git_ok = git_check.passed
    result.git_version = git_check.version

    docker_check = check_docker()
    result.checks.append(docker_check)
    result.docker_ok = docker_check.passed
    result.docker_version = docker_check.version

    if result.docker_ok:
        daemon_check = check_docker_running()
        result.checks.append(daemon_check)
        if not daemon_check.passed:
            result.docker_ok = False

    if result.docker_ok:
        sandbox_check = check_docker_sandbox()
        result.checks.append(sandbox_check)
        result.sandbox_ok = sandbox_check.passed
    else:
        result.sandbox_ok = False

    wsl2_check, is_wsl2 = check_wsl2()
    result.checks.append(wsl2_check)
    result.wsl2_detected = is_wsl2

    if workspace:
        path_check = check_workspace_path(workspace)
        result.checks.append(path_check)
        result.windows_path_warning = (
            not path_check.passed and path_check.severity == SeverityLevel.WARNING
        )

    config_check = check_config_directory()
    result.checks.append(config_check)

    from .checks import (
        check_git_version_for_worktrees,
        check_worktree_branch_conflicts,
        check_worktree_health,
    )

    git_version_wt_check = check_git_version_for_worktrees()
    if git_version_wt_check is not None:
        result.checks.append(git_version_wt_check)

    worktree_health_check = check_worktree_health()
    if worktree_health_check is not None:
        result.checks.append(worktree_health_check)

    branch_conflict_check = check_worktree_branch_conflicts()
    if branch_conflict_check is not None:
        result.checks.append(branch_conflict_check)

    user_config_check = check_user_config_valid()
    result.checks.append(user_config_check)

    return result
