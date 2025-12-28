"""
Provide high-level Docker sandbox launch functions and settings injection.

Orchestrate the Docker sandbox lifecycle, combining primitives from
core.py and credential management from credentials.py.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, cast

from ..config import get_cache_dir
from ..constants import SAFETY_NET_POLICY_FILENAME, SANDBOX_DATA_MOUNT, SANDBOX_DATA_VOLUME
from ..errors import SandboxLaunchError
from .core import (
    build_command,
    validate_container_filename,
)
from .credentials import (
    _create_symlinks_in_container,
    _preinit_credential_volume,
    _start_migration_loop,
    _sync_credentials_from_existing_containers,
)

# ─────────────────────────────────────────────────────────────────────────────
# Safety Net Policy Injection
# ─────────────────────────────────────────────────────────────────────────────

# Default policy for when no org config exists (fail-safe to block mode)
DEFAULT_SAFETY_NET_POLICY: dict[str, Any] = {"action": "block"}

# Valid action values (prevents typo → weird behavior)
VALID_SAFETY_NET_ACTIONS: frozenset[str] = frozenset({"block", "warn", "allow"})

# Container path for policy (constant derived from mount point)
CONTAINER_POLICY_PATH = f"{SANDBOX_DATA_MOUNT}/{SAFETY_NET_POLICY_FILENAME}"


def extract_safety_net_policy(org_config: dict[str, Any] | None) -> dict[str, Any] | None:
    """Extract safety_net policy from org config for container injection.

    Args:
        org_config: The resolved organization configuration, or None.

    Returns:
        The safety_net policy dict if present, None otherwise.
    """
    if org_config is None:
        return None
    security = org_config.get("security")
    if not isinstance(security, dict):
        return None
    safety_net = security.get("safety_net")
    if not isinstance(safety_net, dict):
        return None
    return safety_net


def validate_safety_net_policy(policy: dict[str, Any]) -> dict[str, Any]:
    """Validate and sanitize safety net policy, fail-closed on invalid values.

    Args:
        policy: Raw policy dict from org config.

    Returns:
        Validated policy dict. Missing or invalid 'action' values default to 'block'.
        The result always contains an 'action' key.
    """
    result = dict(policy)  # shallow copy
    action = result.get("action")
    # Always set action: either keep valid value or default to "block" (fail-closed)
    if action is None or action not in VALID_SAFETY_NET_ACTIONS:
        result["action"] = "block"  # fail-closed on missing or invalid
    return result


def get_effective_safety_net_policy(org_config: dict[str, Any] | None) -> dict[str, Any]:
    """Get the safety net policy, falling back to default if not configured.

    Always returns a policy dict - never None. This ensures the mount is always
    present, avoiding sandbox reuse issues when policy is added later.

    Args:
        org_config: The resolved organization configuration, or None.

    Returns:
        The validated safety_net policy dict from org config, or DEFAULT_SAFETY_NET_POLICY.
    """
    custom_policy = extract_safety_net_policy(org_config)
    if custom_policy is not None:
        return validate_safety_net_policy(custom_policy)
    return DEFAULT_SAFETY_NET_POLICY


def _write_policy_to_dir(policy: dict[str, Any], target_dir: Path) -> Path | None:
    """Write policy to a specific directory with atomic pattern.

    Uses temp file + rename pattern for atomicity. Even if the process crashes
    mid-write, readers will see either the old file or the complete new file.

    Args:
        policy: Policy dict to write.
        target_dir: Directory to write to.

    Returns:
        The absolute path to the policy file on success, None on failure.
    """
    try:
        target_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError:
        return None

    policy_path = target_dir / SAFETY_NET_POLICY_FILENAME
    content = json.dumps(policy, indent=2)

    try:
        # Atomic write: temp file → fsync → rename → fsync dir
        fd, temp_path_str = tempfile.mkstemp(
            dir=target_dir,
            prefix=".policy_",
            suffix=".tmp",
        )
        temp_path = Path(temp_path_str)
        try:
            os.write(fd, content.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)

        os.chmod(temp_path, 0o600)  # User read/write only
        temp_path.replace(policy_path)  # Atomic replace (cross-platform)

        # fsync directory to ensure replace is durable
        # O_DIRECTORY may not exist on all platforms (e.g., Windows)
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        try:
            dir_fd = os.open(target_dir, flags)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass  # Directory fsync is best-effort

        return policy_path.resolve()  # Return absolute path
    except OSError:
        # Clean up temp file if it exists
        try:
            if "temp_path" in locals():
                temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        return None


def _get_fallback_policy_dir() -> Path:
    """Get fallback directory for policy files.

    Uses home-based path instead of tempfile.gettempdir() because:
    - On macOS, /var/folders/... is often NOT Docker-shareable by default
    - Home directory (/Users/... on macOS, /home/... on Linux) is always shared

    Returns:
        Path under user's home that's reliably Docker-mountable.
    """
    return Path.home() / ".cache" / "scc-policy-fallback"


def write_safety_net_policy_to_host(policy: dict[str, Any]) -> Path | None:
    """Write safety net policy to host cache with atomic write pattern.

    Args:
        policy: The safety_net policy dict to write.

    Returns:
        The absolute host path to the policy file (resolved for Docker Desktop),
        or None on failure.

    Note:
        Uses atomic write (temp file + replace) to prevent partial reads
        if container starts while file is being written.
        Returns resolved absolute path for Docker Desktop compatibility.

        If cache dir write fails, falls back to ~/.cache/scc-policy-fallback/
        which is reliably Docker-shareable (under /Users on macOS, /home on Linux).
    """
    # Primary: try cache directory (user's standard cache location)
    cache_dir = get_cache_dir().resolve()
    result = _write_policy_to_dir(policy, cache_dir)

    if result is not None:
        # Optional hygiene: delete old fallback files on success
        _cleanup_fallback_policy_files()
        return result

    # Fallback: use home-based path (always Docker-shareable)
    # Avoid tempfile.gettempdir() - on macOS it's /var/folders which may not be shared
    fallback_dir = _get_fallback_policy_dir()
    return _write_policy_to_dir(policy, fallback_dir)


def _cleanup_fallback_policy_files() -> None:
    """Remove old fallback policy files (optional hygiene).

    Called after successful cache dir write to clean up any stale fallback files.
    Failures are silently ignored - this is purely optional hygiene.
    """
    fallback_dir = _get_fallback_policy_dir()
    fallback_file = fallback_dir / SAFETY_NET_POLICY_FILENAME
    try:
        fallback_file.unlink(missing_ok=True)
        # Also try to remove the directory if empty
        if fallback_dir.exists() and not any(fallback_dir.iterdir()):
            fallback_dir.rmdir()
    except OSError:
        pass  # Silently ignore - this is optional hygiene


def run(
    cmd: list[str],
    ensure_credentials: bool = True,
    org_config: dict[str, Any] | None = None,
) -> int:
    """
    Execute the Docker command with optional org configuration.

    This is a thin wrapper that calls run_sandbox() with extracted parameters.
    When org_config is provided, the security.safety_net policy is extracted
    and mounted read-only into the container for the scc-safety-net plugin.

    Args:
        cmd: Command to execute (must be docker sandbox run format)
        ensure_credentials: If True, use detached→symlink→exec pattern
        org_config: Organization config dict. If provided, safety-net policy
            is extracted and mounted. If None, default fail-safe policy is used.

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
        org_config=org_config,
    )


def run_sandbox(
    workspace: Path | None = None,
    continue_session: bool = False,
    resume: bool = False,
    ensure_credentials: bool = True,
    org_config: dict[str, Any] | None = None,
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
        org_config: Organization config dict. If provided, security.safety_net
            policy is extracted and mounted read-only into container for the
            scc-safety-net plugin. If None, a default fail-safe policy is used.

    Returns:
        Exit code from Docker process

    Raises:
        SandboxLaunchError: If Docker command fails to start
    """
    try:
        # ALWAYS write policy file and get host path (even without org config)
        # This ensures the mount is present from first launch, avoiding
        # sandbox reuse issues when safety-net is enabled later.
        # If no org config, uses default {"action": "block"} (fail-safe).
        effective_policy = get_effective_safety_net_policy(org_config)
        policy_host_path = write_safety_net_policy_to_host(effective_policy)
        # Note: policy_host_path may be None if write failed - build_command
        # will handle this gracefully (no mount, plugin uses internal defaults)

        if os.name != "nt" and ensure_credentials:
            # STEP 1: Sync credentials from existing containers to volume
            # This copies credentials from project A's container when starting project B
            _sync_credentials_from_existing_containers()

            # STEP 2: Pre-initialize volume files (prevents EOF race condition)
            _preinit_credential_volume()

            # STEP 3: Start container in DETACHED mode (no Claude running yet)
            detached_cmd = build_command(
                workspace=workspace,
                detached=True,
                policy_host_path=policy_host_path,
            )
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
            # Policy injection still applies - mount is always present
            cmd = build_command(
                workspace=workspace,
                continue_session=continue_session,
                resume=resume,
                detached=False,
                policy_host_path=policy_host_path,
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
