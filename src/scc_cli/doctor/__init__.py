"""Provide system diagnostics and health checks for SCC-CLI.

Offer comprehensive health checks for all prerequisites needed to run
Claude Code in Docker sandboxes.

Philosophy: "Fast feedback, clear guidance"
- Check all prerequisites quickly
- Provide clear pass/fail indicators
- Offer actionable fix suggestions

Package Structure:
- types.py: Data structures (CheckResult, DoctorResult, JsonValidationResult)
- checks.py: Individual health check functions
- render.py: Orchestration and Rich terminal rendering
"""

# Re-export the config module for backward compatibility with tests
from scc_cli import config

# Import all check functions from checks.py
from scc_cli.doctor.checks import (
    _escape_rich,
    check_cache_readable,
    check_cache_ttl_status,
    check_config_directory,
    check_credential_injection,
    check_docker,
    check_docker_running,
    check_docker_sandbox,
    check_exception_stores,
    check_git,
    check_marketplace_auth_available,
    check_migration_status,
    check_org_config_reachable,
    check_proxy_environment,
    check_user_config_valid,
    check_workspace_path,
    check_wsl2,
    format_code_frame,
    get_json_error_hints,
    load_cached_org_config,
    run_all_checks,
    validate_json_file,
)

# Import orchestration and rendering functions from render.py
from scc_cli.doctor.render import (
    build_doctor_json_data,
    is_first_run,
    quick_check,
    render_doctor_compact,
    render_doctor_results,
    render_quick_status,
    run_doctor,
)

# Import types from types.py
from scc_cli.doctor.types import CheckResult, DoctorResult, JsonValidationResult

__all__ = [
    # Config module (for backward compatibility with tests)
    "config",
    # Dataclasses
    "CheckResult",
    "DoctorResult",
    "JsonValidationResult",
    # JSON validation helpers
    "validate_json_file",
    "format_code_frame",
    "_escape_rich",
    "get_json_error_hints",
    # Check functions
    "check_git",
    "check_docker",
    "check_docker_sandbox",
    "check_docker_running",
    "check_wsl2",
    "check_workspace_path",
    "check_user_config_valid",
    "check_config_directory",
    "load_cached_org_config",
    "check_org_config_reachable",
    "check_marketplace_auth_available",
    "check_credential_injection",
    "check_cache_readable",
    "check_cache_ttl_status",
    "check_migration_status",
    "check_exception_stores",
    "check_proxy_environment",
    "run_all_checks",
    # Orchestration and rendering
    "run_doctor",
    "build_doctor_json_data",
    "render_doctor_results",
    "render_doctor_compact",
    "render_quick_status",
    "quick_check",
    "is_first_run",
]
