"""Health check functions for the doctor module.

This package contains all check functions organized by category:
- JSON validation helpers (json_helpers.py)
- Environment checks (environment.py) - Git, Docker, WSL2, Workspace
- Git Worktree checks (worktree.py)
- Configuration checks (config.py)
- Organization & Marketplace checks (organization.py)
- Cache & State checks (cache.py)

All check functions return CheckResult or CheckResult | None.
"""

from __future__ import annotations

from ..types import CheckResult

# Cache & State checks
from .cache import (
    check_cache_readable,
    check_cache_ttl_status,
    check_exception_stores,
    check_migration_status,
    check_proxy_environment,
)

# Configuration checks
from .config import (
    check_config_directory,
    check_user_config_valid,
)

# Environment checks
from .environment import (
    check_docker,
    check_docker_desktop,
    check_docker_running,
    check_docker_sandbox,
    check_git,
    check_workspace_path,
    check_wsl2,
)

# JSON validation helpers
from .json_helpers import (
    _escape_rich,
    format_code_frame,
    get_json_error_hints,
    validate_json_file,
)

# Organization & Marketplace checks
from .organization import (
    check_credential_injection,
    check_marketplace_auth_available,
    check_org_config_reachable,
    load_cached_org_config,
)

# Worktree checks
from .worktree import (
    check_git_version_for_worktrees,
    check_worktree_branch_conflicts,
    check_worktree_health,
)


def run_all_checks() -> list[CheckResult]:
    """Run all health checks and return list of results.

    Includes both environment checks and organization/marketplace checks.

    Returns:
        List of all CheckResult objects (excluding None results).
    """
    results: list[CheckResult] = []

    # Environment checks
    results.append(check_git())
    results.append(check_docker())
    results.append(check_docker_desktop())
    results.append(check_docker_sandbox())
    results.append(check_docker_running())

    wsl2_result, _ = check_wsl2()
    results.append(wsl2_result)

    results.append(check_config_directory())

    # Git worktree checks (may return None if not in a git repo)
    git_version_check = check_git_version_for_worktrees()
    if git_version_check is not None:
        results.append(git_version_check)

    worktree_check = check_worktree_health()
    if worktree_check is not None:
        results.append(worktree_check)

    branch_conflict_check = check_worktree_branch_conflicts()
    if branch_conflict_check is not None:
        results.append(branch_conflict_check)

    # User config validation (JSON syntax check)
    results.append(check_user_config_valid())

    # Organization checks (may return None)
    org_check = check_org_config_reachable()
    if org_check is not None:
        results.append(org_check)

    auth_check = check_marketplace_auth_available()
    if auth_check is not None:
        results.append(auth_check)

    injection_check = check_credential_injection()
    if injection_check is not None:
        results.append(injection_check)

    # Cache checks
    results.append(check_cache_readable())

    ttl_check = check_cache_ttl_status()
    if ttl_check is not None:
        results.append(ttl_check)

    # Migration check
    results.append(check_migration_status())

    # Exception stores check
    results.append(check_exception_stores())

    return results


__all__ = [
    # JSON validation helpers
    "validate_json_file",
    "format_code_frame",
    "_escape_rich",
    "get_json_error_hints",
    # Environment checks
    "check_git",
    "check_docker",
    "check_docker_desktop",
    "check_docker_sandbox",
    "check_docker_running",
    "check_wsl2",
    "check_workspace_path",
    # Worktree checks
    "check_worktree_health",
    "check_git_version_for_worktrees",
    "check_worktree_branch_conflicts",
    # Config checks
    "check_user_config_valid",
    "check_config_directory",
    # Organization checks
    "load_cached_org_config",
    "check_org_config_reachable",
    "check_marketplace_auth_available",
    "check_credential_injection",
    # Cache & state checks
    "check_cache_readable",
    "check_cache_ttl_status",
    "check_migration_status",
    "check_exception_stores",
    "check_proxy_environment",
    # Orchestration
    "run_all_checks",
]
