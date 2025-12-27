"""
Docker sandbox operations.

This package provides Docker sandbox lifecycle management with
credential persistence across project switches.

===============================================================================
CREDENTIAL PERSISTENCE ARCHITECTURE (DO NOT MODIFY)
===============================================================================

PROBLEM: OAuth credentials lost when switching projects. Claude reads config
    before symlinks are created (race condition).

SOLUTION (Synchronous Detached Pattern):
    1. docker sandbox run -d -w /path claude  → Creates container, returns ID
    2. docker exec <id> <symlink_script>      → Creates symlinks while idle
    3. docker exec -it <id> claude            → Runs Claude after symlinks exist

CRITICAL - DO NOT CHANGE:
    - Agent name `claude` is REQUIRED even in detached mode (-d)!
      Wrong: docker sandbox run -d -w /path
      Right: docker sandbox run -d -w /path claude
    - Session flags (-c, --resume) passed via docker exec, NOT container creation

See run_sandbox() and build_command() for implementation.
===============================================================================

Module Structure:
    - core.py: Docker primitives (checks, commands, container lifecycle)
    - credentials.py: Credential persistence subsystem
    - launch.py: High-level launch orchestration and settings

All public symbols are re-exported here for backward compatibility.
Import from scc_cli.docker, not from submodules.
"""

# Re-export subprocess utilities for test patching compatibility
from ..subprocess_utils import run_command, run_command_bool

# Re-export from core.py
from .core import (
    LABEL_PREFIX,
    MIN_DOCKER_VERSION,
    ContainerInfo,
    _check_docker_installed,
    _list_all_sandbox_containers,
    _parse_version,
    build_command,
    build_labels,
    build_start_command,
    check_docker_available,
    check_docker_sandbox,
    container_exists,
    generate_container_name,
    get_container_status,
    get_docker_version,
    list_running_sandboxes,
    list_scc_containers,
    remove_container,
    resume_container,
    run_detached,
    start_container,
    stop_container,
    validate_container_filename,
)

# Re-export from credentials.py
from .credentials import (
    prepare_sandbox_volume_for_credentials,
)

# Re-export from launch.py
from .launch import (
    get_or_create_container,
    get_sandbox_settings,
    inject_file_to_sandbox_volume,
    inject_settings,
    inject_team_settings,
    run,
    run_sandbox,
)

__all__ = [
    # Constants
    "MIN_DOCKER_VERSION",
    "LABEL_PREFIX",
    # Data classes
    "ContainerInfo",
    # Docker checks
    "check_docker_available",
    "check_docker_sandbox",
    "get_docker_version",
    # Container lifecycle
    "container_exists",
    "get_container_status",
    "start_container",
    "stop_container",
    "remove_container",
    "resume_container",
    "run_detached",
    # Command building
    "build_command",
    "build_start_command",
    "build_labels",
    "generate_container_name",
    "validate_container_filename",
    # Container queries
    "list_scc_containers",
    "list_running_sandboxes",
    # Credential management
    "prepare_sandbox_volume_for_credentials",
    # Settings injection
    "inject_file_to_sandbox_volume",
    "get_sandbox_settings",
    "inject_settings",
    "inject_team_settings",
    # High-level launch functions
    "run",
    "run_sandbox",
    "get_or_create_container",
    # Re-exported for test patching compatibility
    "run_command",
    "run_command_bool",
    "_check_docker_installed",
    "_list_all_sandbox_containers",
    "_parse_version",
]
