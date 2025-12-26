"""
Provide high-level Docker sandbox launch functions and settings injection.

Orchestrate the Docker sandbox lifecycle, combining primitives from
core.py and credential management from credentials.py.
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Any, cast

from .. import stats
from ..constants import SANDBOX_DATA_VOLUME
from ..errors import SandboxLaunchError
from .core import (
    build_command,
    check_docker_available,
    validate_container_filename,
)
from .credentials import (
    _create_symlinks_in_container,
    _preinit_credential_volume,
    _start_migration_loop,
    _sync_credentials_from_existing_containers,
)


def run(cmd: list[str], ensure_credentials: bool = True) -> int:
    """
    Execute the Docker command (legacy interface).

    This is a thin wrapper that calls run_sandbox() with extracted parameters.
    Kept for backwards compatibility with existing callers.

    Args:
        cmd: Command to execute (must be docker sandbox run format)
        ensure_credentials: If True, use detached→symlink→exec pattern

    Raises:
        SandboxLaunchError: If Docker command fails to start
    """
    # Extract workspace from command if present
    workspace = None
    continue_session = False
    resume = False

    # Parse the command to extract workspace and flags
    for i, arg in enumerate(cmd):
        if arg == "-w" and i + 1 < len(cmd):
            workspace = Path(cmd[i + 1])
        elif arg == "-c":
            continue_session = True
        elif arg == "--resume":
            resume = True

    # Use the new synchronous run_sandbox function
    return run_sandbox(
        workspace=workspace,
        continue_session=continue_session,
        resume=resume,
        ensure_credentials=ensure_credentials,
    )


def run_sandbox(
    workspace: Path | None = None,
    continue_session: bool = False,
    resume: bool = False,
    ensure_credentials: bool = True,
) -> int:
    """
    Run Claude in a Docker sandbox with credential persistence.

    Uses SYNCHRONOUS detached→symlink→exec pattern to eliminate race condition:
    1. Start container in DETACHED mode (no Claude running yet)
    2. Create symlinks BEFORE Claude starts (race eliminated!)
    3. Exec Claude interactively using docker exec

    This replaces the previous fork-and-inject pattern which had a fundamental
    race condition: parent became Docker at T+0, child created symlinks at T+2s,
    but Claude read config at T+0 before symlinks existed.

    Args:
        workspace: Path to mount as workspace (-w flag)
        continue_session: Pass -c flag to Claude
        resume: Pass --resume flag to Claude
        ensure_credentials: If True, create credential symlinks

    Returns:
        Exit code from Docker process

    Raises:
        SandboxLaunchError: If Docker command fails to start
    """
    try:
        if os.name != "nt" and ensure_credentials:
            # STEP 1: Sync credentials from existing containers to volume
            # This copies credentials from project A's container when starting project B
            _sync_credentials_from_existing_containers()

            # STEP 2: Pre-initialize volume files (prevents EOF race condition)
            _preinit_credential_volume()

            # STEP 3: Start container in DETACHED mode (no Claude running yet)
            detached_cmd = build_command(workspace=workspace, detached=True)
            result = subprocess.run(
                detached_cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                raise SandboxLaunchError(
                    user_message="Failed to create Docker sandbox",
                    command=" ".join(detached_cmd),
                    stderr=result.stderr,
                )

            container_id = result.stdout.strip()
            if not container_id:
                raise SandboxLaunchError(
                    user_message="Docker sandbox returned empty container ID",
                    command=" ".join(detached_cmd),
                )

            # STEP 4: Create symlinks BEFORE Claude starts
            # This is the KEY fix - symlinks exist BEFORE Claude reads config
            _create_symlinks_in_container(container_id)

            # STEP 5: Start background migration loop for first-time login
            # This runs in background to capture OAuth tokens during login
            _start_migration_loop(container_id)

            # STEP 6: Exec Claude interactively (replaces current process)
            # Claude binary is at /home/agent/.local/bin/claude
            exec_cmd = ["docker", "exec", "-it", container_id, "claude"]

            # Add Claude-specific flags
            if continue_session:
                exec_cmd.append("-c")
            elif resume:
                exec_cmd.append("--resume")

            # Replace current process with docker exec
            os.execvp("docker", exec_cmd)

            # If execvp returns, something went wrong
            raise SandboxLaunchError(
                user_message="Failed to exec into Docker sandbox",
                command=" ".join(exec_cmd),
            )

        else:
            # Non-credential mode or Windows: use legacy flow
            cmd = build_command(
                workspace=workspace,
                continue_session=continue_session,
                resume=resume,
                detached=False,
            )

            if os.name != "nt":
                os.execvp(cmd[0], cmd)
                raise SandboxLaunchError(
                    user_message="Failed to start Docker sandbox",
                    command=" ".join(cmd),
                )
            else:
                result = subprocess.run(cmd, text=True)
                return result.returncode

    except subprocess.TimeoutExpired:
        raise SandboxLaunchError(
            user_message="Docker sandbox creation timed out",
            suggested_action="Check if Docker Desktop is running",
        )
    except FileNotFoundError:
        raise SandboxLaunchError(
            user_message="Command not found: docker",
            suggested_action="Ensure Docker is installed and in your PATH",
        )
    except OSError as e:
        raise SandboxLaunchError(
            user_message=f"Failed to start Docker sandbox: {e}",
        )


def inject_file_to_sandbox_volume(filename: str, content: str) -> bool:
    """
    Inject a file into the Docker sandbox persistent volume.

    Uses a temporary alpine container to write to the sandbox data volume.
    Files are written to /data/ which maps to /mnt/claude-data/ in the sandbox.

    Args:
        filename: Name of file to create (e.g., "settings.json", "scc-statusline.sh")
                  Must be a simple filename, no path separators allowed.
        content: Content to write

    Returns:
        True if successful

    Raises:
        ValueError: If filename contains unsafe characters
    """
    # Validate filename to prevent path traversal
    filename = validate_container_filename(filename)

    try:
        # Escape content for shell (replace single quotes)
        escaped_content = content.replace("'", "'\"'\"'")

        # Use alpine to write to the persistent volume
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{SANDBOX_DATA_VOLUME}:/data",
                "alpine",
                "sh",
                "-c",
                f"printf '%s' '{escaped_content}' > /data/{filename} && chmod +x /data/{filename}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def get_sandbox_settings() -> dict[str, Any] | None:
    """
    Return current settings from the Docker sandbox volume.

    Returns:
        Settings dict or None if not found
    """
    try:
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{SANDBOX_DATA_VOLUME}:/data",
                "alpine",
                "cat",
                "/data/settings.json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return cast(dict[Any, Any], json.loads(result.stdout))
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError, json.JSONDecodeError):
        pass
    return None


def inject_settings(settings: dict[str, Any]) -> bool:
    """
    Inject pre-built settings into the Docker sandbox volume.

    This is the "dumb" settings injection function. docker.py does NOT know
    about Claude Code settings format - it just merges and injects JSON.

    Settings are merged with any existing settings in the sandbox volume
    (e.g., status line config). New settings take precedence for conflicts.

    Args:
        settings: Pre-built settings dict (from claude_adapter.build_claude_settings)

    Returns:
        True if settings were injected successfully, False otherwise
    """
    # Get existing settings from Docker volume (preserve status line, etc.)
    existing_settings = get_sandbox_settings() or {}

    # Merge settings with existing settings
    # New settings take precedence for overlapping keys
    merged_settings = {**existing_settings, **settings}

    # Inject merged settings into Docker volume
    return inject_file_to_sandbox_volume(
        "settings.json",
        json.dumps(merged_settings, indent=2),
    )


def inject_team_settings(team_name: str, org_config: dict[str, Any] | None = None) -> bool:
    """
    Inject team-specific settings into the Docker sandbox volume.

    Supports two modes:
    1. With org_config: Uses new remote org config architecture
       - Resolves profile/marketplace from org_config
       - Builds settings via claude_adapter
    2. Without org_config (deprecated): Uses legacy teams module

    Args:
        team_name: Name of the team profile
        org_config: Optional remote organization config. If provided, uses
            the new architecture with profiles.py and claude_adapter.py

    Returns:
        True if settings were injected successfully, False otherwise
    """
    if org_config is not None:
        # New architecture: use profiles.py and claude_adapter.py
        from .. import claude_adapter, profiles

        # Resolve profile from org config
        profile = profiles.resolve_profile(org_config, team_name)

        # Check if profile has a plugin
        if not profile.get("plugin"):
            return True  # No plugin to inject

        # Resolve marketplace
        marketplace = profiles.resolve_marketplace(org_config, profile)

        # Get org_id for namespacing
        org_id = org_config.get("organization", {}).get("id")

        # Build settings using claude_adapter
        settings = claude_adapter.build_claude_settings(profile, marketplace, org_id)

        # Inject settings
        return inject_settings(settings)
    else:
        # Legacy mode: use old teams module
        from .. import teams

        team_settings = teams.get_team_sandbox_settings(team_name)

        if not team_settings:
            return True

        return inject_settings(team_settings)


def launch_with_org_config(
    workspace: Path,
    org_config: dict[str, Any],
    team: str,
    continue_session: bool = False,
    resume: bool = False,
) -> None:
    """
    Launch Docker sandbox with team profile from remote org config.

    This is the main orchestration function for the new architecture:
    1. Resolves profile and marketplace from org_config (via profiles.py)
    2. Builds Claude Code settings (via claude_adapter.py)
    3. Injects settings into sandbox volume
    4. Launches Docker sandbox

    docker.py is "dumb" - it delegates all Claude Code format knowledge
    to claude_adapter.py and profile resolution to profiles.py.

    Args:
        workspace: Path to workspace directory
        org_config: Remote organization config dict
        team: Team profile name
        continue_session: Pass -c flag to Claude
        resume: Pass --resume flag to Claude

    Raises:
        ValueError: If team/profile not found in org_config
        DockerNotFoundError: If Docker not available
        SandboxLaunchError: If sandbox fails to start
    """
    from .. import claude_adapter, profiles

    # Check Docker is available
    check_docker_available()

    # Resolve profile from org config (raises ValueError if not found)
    profile = profiles.resolve_profile(org_config, team)

    # Resolve marketplace for the profile
    marketplace = profiles.resolve_marketplace(org_config, profile)

    # Get org_id for namespacing
    org_id = org_config.get("organization", {}).get("id")

    # Build Claude Code settings using the adapter
    settings = claude_adapter.build_claude_settings(profile, marketplace, org_id)

    # Inject settings into sandbox volume
    inject_settings(settings)

    # Build and run the Docker sandbox command
    cmd = build_command(
        workspace=workspace,
        continue_session=continue_session,
        resume=resume,
    )

    # Run the sandbox
    run(cmd)


def launch_with_org_config_v2(
    workspace: Path,
    org_config: dict[str, Any],
    team: str,
    continue_session: bool = False,
    resume: bool = False,
    is_offline: bool = False,
    cache_age_hours: int | None = None,
) -> None:
    """
    Launch Docker sandbox with v2 config inheritance.

    This is the v2 orchestration function that supports:
    - 3-layer config inheritance (org → team → project)
    - Security boundary enforcement (blocked items)
    - Delegation rules (denied additions)
    - Offline mode with stale cache warnings

    Args:
        workspace: Path to workspace directory
        org_config: Remote organization config dict (v2 schema)
        team: Team profile name
        continue_session: Pass -c flag to Claude
        resume: Pass --resume flag to Claude
        is_offline: Whether operating in offline mode
        cache_age_hours: Age of cached config in hours (for staleness warning)

    Raises:
        PolicyViolationError: If blocked plugins are detected
        ValueError: If team/profile not found in org_config
        DockerNotFoundError: If Docker not available
    """
    from .. import claude_adapter, profiles
    from ..errors import PolicyViolationError

    # Check Docker is available
    check_docker_available()

    # Compute effective config with 3-layer inheritance
    # This handles org defaults → team profile → project .scc.yaml
    effective = profiles.compute_effective_config(
        org_config=org_config,
        team_name=team,
        workspace_path=workspace,
    )

    # Check for security violations (blocked items = hard failure)
    if effective.blocked_items:
        # Raise error for first blocked item
        blocked = effective.blocked_items[0]
        raise PolicyViolationError(
            item=blocked.item,
            blocked_by=blocked.blocked_by,
        )

    # Warn about denied additions (soft failure - continue but warn)
    if effective.denied_additions:
        from scc_cli.utils.fixit import generate_unblock_command

        for denied in effective.denied_additions:
            print(f"⚠️  '{denied.item}' was denied: {denied.reason}")
            # Add fix-it command - make it stand out
            fix_cmd = generate_unblock_command(denied.item, "plugin")
            print(f"   → To unblock: {fix_cmd}")

    # Warn about stale cache when offline
    if is_offline and cache_age_hours is not None and cache_age_hours > 24:
        print(f"⚠️  Running offline with stale config cache ({cache_age_hours}h old)")

    # Get org_id for namespacing
    org_id = org_config.get("organization", {}).get("id")

    # Get marketplace info if available
    marketplace = None
    try:
        profile = profiles.resolve_profile(org_config, team)
        marketplace = profiles.resolve_marketplace(org_config, profile)
    except (ValueError, KeyError):
        pass

    # Build Claude Code settings using the v2 adapter
    settings = claude_adapter.build_settings_from_effective_config(
        effective_config=effective,
        org_id=org_id,
        marketplace=marketplace,
    )

    # Inject settings into sandbox volume
    inject_settings(settings)

    # Build and run the Docker sandbox command
    cmd = build_command(
        workspace=workspace,
        continue_session=continue_session,
        resume=resume,
    )

    # Record session start for usage stats
    # NOTE: session_end cannot be recorded on Unix because os.execvp replaces
    # the process. Incomplete sessions are tracked by the stats module.
    # Stats errors are non-fatal - launch must always proceed.
    try:
        # Get stats config from org config (may be None for defaults)
        stats_config = org_config.get("stats")

        # Get expected duration from session config (default 8 hours)
        expected_duration = effective.session_config.timeout_hours or 8

        # Generate session ID
        session_id = stats.generate_session_id()

        # Record session start
        stats.record_session_start(
            session_id=session_id,
            project_name=workspace.name,
            team_name=team,
            expected_duration_hours=expected_duration,
            stats_config=stats_config,
        )
    except Exception:
        # Stats recording failure must never block launch
        # Silently continue - user can still use scc without stats
        pass

    # Run the sandbox
    run(cmd)


def get_or_create_container(
    workspace: Path | None,
    branch: str | None = None,
    profile: str | None = None,
    force_new: bool = False,
    continue_session: bool = False,
    env_vars: dict[str, str] | None = None,
) -> tuple[list[str], bool]:
    """
    Build a Docker sandbox run command.

    Note: Docker sandboxes are ephemeral by design - they don't support container
    re-use patterns like traditional `docker run`. Each invocation creates a new
    sandbox instance. The branch, profile, force_new, and env_vars parameters are
    kept for API compatibility but are not used.

    Args:
        workspace: Path to workspace (-w flag for sandbox)
        branch: Git branch name (unused - sandboxes don't support naming)
        profile: Team profile (unused - sandboxes don't support labels)
        force_new: Force new container (unused - sandboxes are always new)
        continue_session: Pass -c flag to Claude
        env_vars: Environment variables (unused - sandboxes handle auth)

    Returns:
        Tuple of (command_to_run, is_resume)
        - is_resume is always False for sandboxes (no resume support)
    """
    # Docker sandbox doesn't support container re-use - always create new
    cmd = build_command(
        workspace=workspace,
        continue_session=continue_session,
    )
    return cmd, False
