from __future__ import annotations

from pathlib import Path

from scc_cli.core.enums import SeverityLevel

from .checks import (
    check_config_directory,
    check_docker,
    check_docker_running,
    check_docker_sandbox,
    check_git,
    check_provider_auth,
    check_provider_image,
    check_runtime_backend,
    check_safety_policy,
    check_user_config_valid,
    check_workspace_path,
    check_wsl2,
)
from .types import CheckResult, DoctorResult

_DEFAULT_PROVIDER_IDS: tuple[str, ...] = ("claude", "codex")

# Category assignment rules: check name → category
_CATEGORY_MAP: dict[str, str] = {
    "Git": "backend",
    "Docker": "backend",
    "Docker Daemon": "backend",
    "Docker Desktop": "backend",
    "Sandbox Backend": "backend",
    "Runtime Backend": "backend",
    "Provider Image": "provider",
    "Provider Auth": "provider",
    "Config Directory": "config",
    "User Config": "config",
    "Safety Policy": "config",
    "Git Worktrees": "worktree",
    "Worktree Health": "worktree",
    "Branch Conflicts": "worktree",
}


def _assign_category(check: CheckResult) -> None:
    """Assign a category to a check result based on its name.

    If the check already has a non-default category set (e.g. by the check
    function itself), leave it alone.
    """
    if check.category != "general":
        return  # already set by the check function
    check.category = _CATEGORY_MAP.get(check.name, "general")


def run_doctor(
    workspace: Path | None = None,
    provider_id: str | None = None,
) -> DoctorResult:
    """Run all health checks and return comprehensive results.

    Args:
        workspace: Optional workspace path to validate.
        provider_id: When set, scopes provider checks to this provider.
    """

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

    runtime_check = check_runtime_backend()
    result.checks.append(runtime_check)

    provider_ids = (provider_id,) if provider_id is not None else _DEFAULT_PROVIDER_IDS

    if result.docker_ok:
        for current_provider_id in provider_ids:
            try:
                image_check = check_provider_image(provider_id=current_provider_id)
                result.checks.append(
                    _label_provider_check(
                        image_check, current_provider_id, requested_provider_id=provider_id
                    )
                )
            except Exception:
                pass  # partial-results — don't block other checks

        for current_provider_id in provider_ids:
            try:
                auth_check = check_provider_auth(provider_id=current_provider_id)
                result.checks.append(
                    _label_provider_check(
                        auth_check, current_provider_id, requested_provider_id=provider_id
                    )
                )
            except Exception:
                pass  # partial-results — don't block other checks

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

    safety_check = check_safety_policy()
    result.checks.append(safety_check)

    # Assign categories to all checks
    for check in result.checks:
        _assign_category(check)

    return result


def _label_provider_check(
    check: CheckResult,
    current_provider_id: str,
    *,
    requested_provider_id: str | None,
) -> CheckResult:
    """Disambiguate provider checks when doctor is showing multiple providers."""
    if requested_provider_id is not None:
        return check

    from scc_cli.core.provider_resolution import get_provider_display_name

    check.name = f"{check.name} ({get_provider_display_name(current_provider_id)})"
    return check
