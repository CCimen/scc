"""
Docker sandbox operations.

Container re-use pattern:
- Containers are named deterministically: scc-<workspace_hash>-<branch_hash>
- On start: check if container exists, resume if so, create if not
- Docker labels store metadata (profile, workspace, branch, created timestamp)

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
"""

import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from . import stats
from .errors import (
    ContainerNotFoundError,
    DockerNotFoundError,
    DockerVersionError,
    SandboxLaunchError,
    SandboxNotAvailableError,
)
from .subprocess_utils import run_command, run_command_bool

# Minimum Docker Desktop version required for sandbox feature
MIN_DOCKER_VERSION = "4.50.0"

# Label prefix for SCC containers
LABEL_PREFIX = "scc"


@dataclass
class ContainerInfo:
    """Information about an SCC container."""

    id: str
    name: str
    status: str
    profile: str | None = None
    workspace: str | None = None
    branch: str | None = None
    created: str | None = None


def _check_docker_installed() -> bool:
    """Check if Docker is installed and in PATH."""
    return shutil.which("docker") is not None


def _parse_version(version_string: str) -> tuple:
    """Parse version string into comparable tuple."""
    # Extract version number from strings like "Docker version 27.5.1, build..."
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", version_string)
    if match:
        return tuple(int(x) for x in match.groups())
    return (0, 0, 0)


def check_docker_available() -> None:
    """
    Check if Docker is available and meets requirements.

    Raises:
        DockerNotFoundError: Docker is not installed
        DockerVersionError: Docker version is too old
        SandboxNotAvailableError: Sandbox feature not available
    """
    # Check Docker is installed
    if not _check_docker_installed():
        raise DockerNotFoundError()

    # Check Docker version
    version = get_docker_version()
    if version:
        current = _parse_version(version)
        required = _parse_version(MIN_DOCKER_VERSION)
        if current < required:
            raise DockerVersionError(current_version=version)

    # Check sandbox command exists
    if not check_docker_sandbox():
        raise SandboxNotAvailableError()


def check_docker_sandbox() -> bool:
    """Check if Docker sandbox feature is available (Docker Desktop 4.50+)."""
    if not _check_docker_installed():
        return False
    return run_command_bool(["docker", "sandbox", "--help"], timeout=10)


def get_docker_version() -> str | None:
    """Get Docker version string."""
    return run_command(["docker", "--version"], timeout=5)


def generate_container_name(workspace: Path, branch: str | None = None) -> str:
    """
    Generate deterministic container name from workspace and branch.

    Format: scc-<workspace_name>-<hash>
    Example: scc-eneo-platform-a1b2c3
    """
    # Sanitize workspace name (take last component, lowercase, alphanumeric only)
    workspace_name = workspace.name.lower()
    workspace_name = re.sub(r"[^a-z0-9]", "-", workspace_name)
    workspace_name = re.sub(r"-+", "-", workspace_name).strip("-")

    # Create hash from full workspace path + branch
    hash_input = str(workspace.resolve())
    if branch:
        hash_input += f":{branch}"
    hash_suffix = hashlib.sha256(hash_input.encode()).hexdigest()[:8]

    return f"scc-{workspace_name}-{hash_suffix}"


def container_exists(container_name: str) -> bool:
    """Check if a container with the given name exists (running or stopped)."""
    output = run_command(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            f"name=^{container_name}$",
            "--format",
            "{{.Names}}",
        ],
        timeout=10,
    )
    return output is not None and container_name in output


def get_container_status(container_name: str) -> str | None:
    """Get the status of a container (running, exited, etc.)."""
    output = run_command(
        [
            "docker",
            "ps",
            "-a",
            "--filter",
            f"name=^{container_name}$",
            "--format",
            "{{.Status}}",
        ],
        timeout=10,
    )
    return output if output else None


def build_labels(
    profile: str | None = None,
    workspace: Path | None = None,
    branch: str | None = None,
) -> dict[str, str]:
    """Build Docker labels for container metadata."""
    labels = {
        f"{LABEL_PREFIX}.managed": "true",
        f"{LABEL_PREFIX}.created": datetime.datetime.now().isoformat(),
    }

    if profile:
        labels[f"{LABEL_PREFIX}.profile"] = profile
    if workspace:
        labels[f"{LABEL_PREFIX}.workspace"] = str(workspace)
    if branch:
        labels[f"{LABEL_PREFIX}.branch"] = branch

    return labels


def build_command(
    workspace: Path | None = None,
    continue_session: bool = False,
    resume: bool = False,
    detached: bool = False,
) -> list[str]:
    """
    Build the docker sandbox run command.

    Structure: docker sandbox run [options] claude [claude-options]

    Args:
        workspace: Path to mount as workspace (-w flag)
        continue_session: Pass -c flag to Claude (ignored in detached mode)
        resume: Pass --resume flag to Claude (ignored in detached mode)
        detached: Create container without running agent (-d flag)

    Returns:
        Command as list of strings

    CRITICAL (DO NOT CHANGE):
        - Agent `claude` is ALWAYS included, even in detached mode
        - Session flags passed via docker exec in detached mode (see run_sandbox)
    """
    cmd = ["docker", "sandbox", "run"]

    # Detached mode: create container without running Claude interactively
    # This allows us to create symlinks BEFORE Claude starts
    if detached:
        cmd.append("-d")

    # Add workspace mount
    if workspace:
        cmd.extend(["-w", str(workspace)])

    # Agent name is ALWAYS required (docker sandbox run requires <agent>)
    cmd.append("claude")

    # In interactive mode (not detached), add Claude-specific arguments
    # In detached mode, skip these - we'll pass them via docker exec later
    if not detached:
        if continue_session:
            cmd.append("-c")
        elif resume:
            cmd.append("--resume")

    return cmd


def build_start_command(container_name: str) -> list[str]:
    """Build command to resume an existing container."""
    return ["docker", "start", "-ai", container_name]


def _preinit_credential_volume() -> None:
    """
    Pre-initialize credential volume files BEFORE container starts.

    This prevents "JSON Parse error: Unexpected EOF" race condition:
    1. Docker sandbox creates symlinks to volume immediately on start
    2. Claude Code reads symlinked files immediately
    3. If volume files don't exist, Claude sees EOF error

    Solution: Ensure volume has valid JSON files BEFORE starting container.
    Uses a temporary alpine container to initialize the volume.

    CRITICAL: Files must be owned by uid 1000 (agent user) and writable,
    otherwise Claude Code cannot write OAuth tokens to .credentials.json!
    """
    init_cmd = (
        # Create files with empty JSON object if missing or empty
        "[ -s /data/.claude.json ] || echo '{}' > /data/.claude.json; "
        "[ -s /data/credentials.json ] || echo '{}' > /data/credentials.json; "
        "[ -s /data/.credentials.json ] || echo '{}' > /data/.credentials.json; "
        # ALWAYS fix ownership to agent user (uid 1000) - handles existing volumes
        # with wrong permissions from earlier versions
        "chown 1000:1000 /data/.claude.json /data/credentials.json /data/.credentials.json 2>/dev/null; "
        # ALWAYS set writable permissions (needed for OAuth token writes)
        "chmod 666 /data/.claude.json /data/credentials.json /data/.credentials.json 2>/dev/null"
    )

    try:
        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                "docker-claude-sandbox-data:/data",
                "alpine",
                "sh",
                "-c",
                init_cmd,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        # If pre-init fails, continue anyway - sandbox might still work
        pass


def _check_volume_has_credentials() -> bool:
    """
    Check if the Docker volume already has valid OAuth credentials.

    The volume is the source of truth. If it has credentials from a
    previous session, we don't need to copy from containers.

    Returns:
        True if volume has valid OAuth credentials
    """
    try:
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                "docker-claude-sandbox-data:/data",
                "alpine",
                "cat",
                "/data/.credentials.json",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0 or not result.stdout.strip():
            return False

        # Validate JSON and check for OAuth tokens
        try:
            creds = json.loads(result.stdout)
            return bool(creds and creds.get("claudeAiOauth"))
        except json.JSONDecodeError:
            return False

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def _list_all_sandbox_containers() -> list[ContainerInfo]:
    """
    List ALL Claude Code sandbox containers (running AND stopped).

    This is critical for credential recovery - when user does /exit,
    the container STOPS but still contains the OAuth credentials.

    Returns list of ContainerInfo objects sorted by most recent first.
    """
    try:
        # Get ALL containers (not just running) filtered by sandbox image
        result = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                "ancestor=docker/sandbox-templates:claude-code",
                "--format",
                "{{.ID}}\t{{.Names}}\t{{.Status}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return []

        containers = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("\t")
                if len(parts) >= 3:
                    containers.append(
                        ContainerInfo(
                            id=parts[0],
                            name=parts[1],
                            status=parts[2],
                        )
                    )

        return containers
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _copy_credentials_from_container(container_id: str, is_running: bool) -> bool:
    """
    Copy OAuth credentials from a container to the persistent volume.

    For RUNNING containers: uses docker exec
    For STOPPED containers: uses docker cp (the key insight!)

    Args:
        container_id: The container ID to copy from
        is_running: Whether the container is currently running

    Returns:
        True if credentials were found and copied successfully
    """
    import tempfile

    if is_running:
        # Running container: use docker exec to cat the file
        try:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    container_id,
                    "cat",
                    "/home/agent/.claude/.credentials.json",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0 or not result.stdout.strip():
                return False

            # Validate JSON
            try:
                creds = json.loads(result.stdout)
                if not creds or not creds.get("claudeAiOauth"):
                    return False
            except json.JSONDecodeError:
                return False

            # Write to volume
            escaped = result.stdout.replace("'", "'\"'\"'")
            subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    "docker-claude-sandbox-data:/data",
                    "alpine",
                    "sh",
                    "-c",
                    f"printf '%s' '{escaped}' > /data/.credentials.json && "
                    "chown 1000:1000 /data/.credentials.json && chmod 666 /data/.credentials.json",
                ],
                capture_output=True,
                timeout=30,
            )

            # Also copy .claude.json
            result2 = subprocess.run(
                ["docker", "exec", container_id, "cat", "/home/agent/.claude.json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result2.returncode == 0 and result2.stdout.strip():
                escaped2 = result2.stdout.replace("'", "'\"'\"'")
                subprocess.run(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "-v",
                        "docker-claude-sandbox-data:/data",
                        "alpine",
                        "sh",
                        "-c",
                        f"printf '%s' '{escaped2}' > /data/.claude.json && "
                        "chown 1000:1000 /data/.claude.json && chmod 666 /data/.claude.json",
                    ],
                    capture_output=True,
                    timeout=30,
                )

            return True

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False

    else:
        # STOPPED container: use docker cp (THE KEY FIX!)
        # docker cp works on stopped containers, docker exec does not
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                creds_path = Path(tmpdir) / ".credentials.json"
                claude_path = Path(tmpdir) / ".claude.json"

                # Copy .credentials.json from stopped container
                result = subprocess.run(
                    [
                        "docker",
                        "cp",
                        f"{container_id}:/home/agent/.claude/.credentials.json",
                        str(creds_path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result.returncode != 0 or not creds_path.exists():
                    return False

                # Validate credentials
                try:
                    content = creds_path.read_text()
                    creds = json.loads(content)
                    if not creds or not creds.get("claudeAiOauth"):
                        return False
                except (json.JSONDecodeError, OSError):
                    return False

                # Write to volume using alpine container
                escaped = content.replace("'", "'\"'\"'")
                subprocess.run(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "-v",
                        "docker-claude-sandbox-data:/data",
                        "alpine",
                        "sh",
                        "-c",
                        f"printf '%s' '{escaped}' > /data/.credentials.json && "
                        "chown 1000:1000 /data/.credentials.json && chmod 666 /data/.credentials.json",
                    ],
                    capture_output=True,
                    timeout=30,
                )

                # Also try .claude.json
                result2 = subprocess.run(
                    [
                        "docker",
                        "cp",
                        f"{container_id}:/home/agent/.claude.json",
                        str(claude_path),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if result2.returncode == 0 and claude_path.exists():
                    try:
                        content2 = claude_path.read_text()
                        escaped2 = content2.replace("'", "'\"'\"'")
                        subprocess.run(
                            [
                                "docker",
                                "run",
                                "--rm",
                                "-v",
                                "docker-claude-sandbox-data:/data",
                                "alpine",
                                "sh",
                                "-c",
                                f"printf '%s' '{escaped2}' > /data/.claude.json && "
                                "chown 1000:1000 /data/.claude.json && chmod 666 /data/.claude.json",
                            ],
                            capture_output=True,
                            timeout=30,
                        )
                    except OSError:
                        pass  # .claude.json is optional

                return True

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return False


def _sync_credentials_from_existing_containers() -> bool:
    """
    Sync credentials from existing containers to volume BEFORE starting new container.

    This is the KEY to cross-project credential persistence:
    1. Check if volume already has credentials (source of truth)
    2. If not, check ALL containers (running AND stopped)
    3. Use docker cp for stopped containers (docker exec only works on running)

    The critical insight: when user does /exit, the container STOPS.
    docker exec doesn't work on stopped containers, but docker cp DOES!

    Returns:
        True if credentials exist in volume (either already or after sync)
    """
    # Step 1: Check if volume already has credentials
    if _check_volume_has_credentials():
        return True  # Volume is source of truth, nothing to do

    # Step 2: Get ALL containers (running AND stopped)
    containers = _list_all_sandbox_containers()
    if not containers:
        return False

    # Step 3: Try to copy credentials from each container
    for container in containers:
        is_running = "Up" in container.status
        if _copy_credentials_from_container(container.id, is_running):
            return True  # Successfully synced

    return False


def _create_symlinks_in_container(container_id: str) -> bool:
    """
    Create credential symlinks directly in a running container.

    NON-DESTRUCTIVE approach:
    - Docker sandbox creates some symlinks automatically (.claude.json, settings.json)
    - We only create symlinks that are MISSING or point to WRONG target
    - Never delete Docker's working symlinks (prevents race conditions)

    Args:
        container_id: The container ID to create symlinks in

    Returns:
        True if all required symlinks exist
    """
    try:
        # Step 1: Ensure directory exists
        subprocess.run(
            ["docker", "exec", container_id, "mkdir", "-p", "/home/agent/.claude"],
            capture_output=True,
            timeout=5,
        )

        # Step 2: Create symlinks only if missing or pointing to wrong target
        symlinks = [
            # (source on volume, target in container)
            # .credentials.json is the OAuth file - Docker does NOT create this
            ("/mnt/claude-data/.credentials.json", "/home/agent/.claude/.credentials.json"),
            # .claude.json - Docker creates this, but we verify it's correct
            ("/mnt/claude-data/.claude.json", "/home/agent/.claude.json"),
            # credentials.json (API key) - Docker does NOT create this
            ("/mnt/claude-data/credentials.json", "/home/agent/.claude/credentials.json"),
        ]

        for src, dst in symlinks:
            # Check if symlink already exists and points to correct target
            check = subprocess.run(
                ["docker", "exec", container_id, "readlink", dst],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if check.returncode == 0 and check.stdout.strip() == src:
                # Symlink already correct, skip (don't touch Docker's symlinks)
                continue

            # Symlink missing or wrong - create it (ln -sfn is atomic)
            # -s = symbolic, -f = force (overwrite), -n = no-dereference
            result = subprocess.run(
                ["docker", "exec", container_id, "ln", "-sfn", src, dst],
                capture_output=True,
                timeout=5,
            )
            if result.returncode != 0:
                return False

        return True

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def _migrate_credentials_to_volume(container_id: str) -> bool:
    """
    Migrate any regular credential files from container to volume.

    If credentials exist as regular files (not symlinks) in the container,
    copy them to the volume before creating symlinks.

    Args:
        container_id: The container ID to migrate from

    Returns:
        True if migration succeeded or was not needed
    """
    try:
        # Check if .credentials.json is a regular file (not symlink)
        result = subprocess.run(
            [
                "docker",
                "exec",
                container_id,
                "sh",
                "-c",
                "[ -f /home/agent/.claude/.credentials.json ] && "
                "[ ! -L /home/agent/.claude/.credentials.json ] && "
                "cat /home/agent/.claude/.credentials.json",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0 and result.stdout.strip():
            # Found regular file with content - copy to volume
            content = result.stdout
            try:
                creds = json.loads(content)
                if creds and creds.get("claudeAiOauth"):
                    # Valid OAuth credentials - copy to volume
                    escaped = content.replace("'", "'\"'\"'")
                    subprocess.run(
                        [
                            "docker",
                            "run",
                            "--rm",
                            "-v",
                            "docker-claude-sandbox-data:/data",
                            "alpine",
                            "sh",
                            "-c",
                            f"printf '%s' '{escaped}' > /data/.credentials.json && "
                            "chown 1000:1000 /data/.credentials.json",
                        ],
                        capture_output=True,
                        timeout=30,
                    )
            except json.JSONDecodeError:
                pass

        # Also check .claude.json
        result2 = subprocess.run(
            [
                "docker",
                "exec",
                container_id,
                "sh",
                "-c",
                "[ -f /home/agent/.claude.json ] && "
                "[ ! -L /home/agent/.claude.json ] && "
                "cat /home/agent/.claude.json",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result2.returncode == 0 and result2.stdout.strip():
            escaped = result2.stdout.replace("'", "'\"'\"'")
            subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    "docker-claude-sandbox-data:/data",
                    "alpine",
                    "sh",
                    "-c",
                    f"printf '%s' '{escaped}' > /data/.claude.json && "
                    "chown 1000:1000 /data/.claude.json",
                ],
                capture_output=True,
                timeout=30,
            )

        return True

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def _ensure_credentials_symlink(existing_sandbox_ids: set[str] | None = None) -> bool:
    """
    Create credential symlinks from container paths to persistent volume.

    Docker Desktop's sandbox creates symlinks to /mnt/claude-data/ for the
    FIRST sandbox only. When switching workspaces, subsequent sandboxes
    don't get these symlinks, causing credentials to not persist.

    This function:
    1. Waits for the NEW container to start
    2. Creates symlinks IMMEDIATELY once found
    3. Runs migration loop to capture OAuth tokens during first login

    Args:
        existing_sandbox_ids: Set of container IDs that existed before we started
            the new sandbox. Used to identify the NEW container (not in this set).

    Returns:
        True if symlinks were created successfully
    """
    import datetime
    import time

    debug_log = "/tmp/scc-sandbox-debug.log"

    def _debug(msg: str) -> None:
        """Write debug message to log file."""
        try:
            with open(debug_log, "a") as f:
                f.write(f"{datetime.datetime.now().isoformat()} [symlink] {msg}\n")
        except Exception:
            pass

    startup_timeout = 60  # Max 60 seconds to find the container
    migration_interval = 5  # Check every 5 seconds for new credentials
    container_id = None

    _debug(f"Starting, existing_ids={existing_sandbox_ids}")

    # Phase 1: Wait for NEW container to start
    start_time = time.time()
    while time.time() - start_time < startup_timeout:
        try:
            sandboxes = list_running_sandboxes()
            sandbox_ids = [s.id for s in sandboxes]
            _debug(f"Found sandboxes: {sandbox_ids}")

            if existing_sandbox_ids:
                new_sandboxes = [s for s in sandboxes if s.id not in existing_sandbox_ids]
                if new_sandboxes:
                    container_id = new_sandboxes[0].id
                    _debug(f"Found NEW container: {container_id}")
                    break
            elif sandboxes:
                container_id = sandboxes[0].id
                _debug(f"Found container (no existing): {container_id}")
                break
        except Exception as e:
            _debug(f"Exception in sandbox list: {type(e).__name__}: {e}")
        time.sleep(1)  # Check frequently during startup

    if not container_id:
        _debug(f"FAILED: No container found after {startup_timeout}s")
        return False

    # Phase 2: Create symlinks IMMEDIATELY
    # This is the critical fix - create symlinks as soon as container starts
    _debug(f"Creating symlinks in container {container_id}...")
    symlink_result = _create_symlinks_in_container(container_id)
    _debug(f"Symlink creation result: {symlink_result}")

    # Phase 3: Run migration loop UNTIL container stops
    # This captures OAuth tokens during first login and migrates them to volume
    loop_count = 0
    while True:
        try:
            sandboxes = list_running_sandboxes()
            if not any(s.id == container_id for s in sandboxes):
                _debug(
                    f"Container {container_id} stopped, exiting loop after {loop_count} iterations"
                )
                break  # Container stopped

            # Migrate any new credentials to volume
            _migrate_credentials_to_volume(container_id)

            # Re-create symlinks (in case Claude wrote regular files)
            _create_symlinks_in_container(container_id)

            loop_count += 1

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            _debug(f"Loop exception: {type(e).__name__}: {e}")
            break

        time.sleep(migration_interval)

    _debug(f"Completed successfully, loop ran {loop_count} times")
    return True


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


def _start_migration_loop(container_id: str) -> None:
    """
    Start background process to capture OAuth tokens during first login.

    This is still needed for FIRST LOGIN only - when user logs in for the
    first time, Claude writes tokens to container filesystem. This loop
    migrates them to the persistent volume.

    For subsequent projects, credentials are already in volume from step 1.

    Args:
        container_id: The container to monitor and migrate from
    """
    pid = os.fork()
    if pid == 0:
        # Child process: daemonize and run migration loop
        import datetime

        debug_log = "/tmp/scc-sandbox-debug.log"

        def _debug(msg: str) -> None:
            try:
                with open(debug_log, "a") as f:
                    f.write(f"{datetime.datetime.now().isoformat()} [migration] {msg}\n")
            except Exception:
                pass

        try:
            # Detach from terminal
            os.setsid()

            # Redirect FDs to /dev/null
            devnull = os.open(os.devnull, os.O_RDWR)
            os.dup2(devnull, 0)
            os.dup2(devnull, 1)
            os.dup2(devnull, 2)
            os.close(devnull)

            _debug(f"Migration loop started for {container_id}")

            # Run migration loop until container stops
            import time

            loop_count = 0
            while True:
                try:
                    sandboxes = list_running_sandboxes()
                    if not any(s.id == container_id for s in sandboxes):
                        _debug(f"Container {container_id} stopped after {loop_count} loops")
                        break

                    # Migrate any new credentials to volume
                    _migrate_credentials_to_volume(container_id)
                    loop_count += 1

                except Exception as e:
                    _debug(f"Loop error: {type(e).__name__}: {e}")
                    break

                time.sleep(5)

            _debug("Migration loop completed")
            os._exit(0)

        except Exception as e:
            _debug(f"Migration FAILED: {type(e).__name__}: {e}")
            os._exit(1)


def run_detached(cmd: list[str]) -> subprocess.Popen:
    """Run Docker command in background (for multiple worktrees)."""
    return subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def start_container(container_name: str) -> int:
    """
    Start (resume) an existing container interactively.

    Raises:
        ContainerNotFoundError: If container doesn't exist
        SandboxLaunchError: If start fails
    """
    if not container_exists(container_name):
        raise ContainerNotFoundError(container_name=container_name)

    cmd = build_start_command(container_name)
    return run(cmd)


def stop_container(container_id: str) -> bool:
    """Stop a running container."""
    return run_command_bool(["docker", "stop", container_id], timeout=30)


def remove_container(container_name: str, force: bool = False) -> bool:
    """Remove a container."""
    cmd = ["docker", "rm"]
    if force:
        cmd.append("-f")
    cmd.append(container_name)
    return run_command_bool(cmd, timeout=30)


def list_scc_containers() -> list[ContainerInfo]:
    """List all SCC-managed containers (running and stopped)."""
    try:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"label={LABEL_PREFIX}.managed=true",
                "--format",
                '{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Label "scc.profile"}}\t{{.Label "scc.workspace"}}\t{{.Label "scc.branch"}}',
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return []

        containers = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("\t")
                if len(parts) >= 3:
                    containers.append(
                        ContainerInfo(
                            id=parts[0],
                            name=parts[1],
                            status=parts[2],
                            profile=parts[3] if len(parts) > 3 else None,
                            workspace=parts[4] if len(parts) > 4 else None,
                            branch=parts[5] if len(parts) > 5 else None,
                        )
                    )

        return containers
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def list_running_sandboxes() -> list[ContainerInfo]:
    """
    List running Claude Code sandboxes (created by Docker Desktop).

    Docker sandbox containers are identified by:
    - Image: docker/sandbox-templates:claude-code
    - Name pattern: claude-sandbox-*

    Returns list of ContainerInfo objects.
    """
    try:
        # Filter by the Docker sandbox image
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                "ancestor=docker/sandbox-templates:claude-code",
                "--format",
                "{{.ID}}\t{{.Names}}\t{{.Status}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return []

        sandboxes = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("\t")
                if len(parts) >= 3:
                    sandboxes.append(
                        ContainerInfo(
                            id=parts[0],
                            name=parts[1],
                            status=parts[2],
                        )
                    )

        return sandboxes
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def validate_container_filename(filename: str) -> str:
    """Validate filename for injection into container volume.

    SECURITY: Defense-in-depth against path traversal attacks.
    Although files go to a Docker volume (low risk), we validate anyway.

    Args:
        filename: Filename to validate

    Returns:
        Validated filename

    Raises:
        ValueError: If filename contains path traversal or unsafe characters
    """
    if not filename:
        raise ValueError("Filename cannot be empty")

    # Reject path separators (prevent ../../../etc/passwd attacks)
    if "/" in filename or "\\" in filename:
        raise ValueError(f"Invalid filename: path separators not allowed: {filename}")

    # Reject hidden files starting with dot (e.g., .bashrc, .profile)
    if filename.startswith("."):
        raise ValueError(f"Invalid filename: hidden files not allowed: {filename}")

    # Reject null bytes (can truncate strings in some contexts)
    if "\x00" in filename:
        raise ValueError("Invalid filename: null bytes not allowed")

    return filename


def inject_file_to_sandbox_volume(filename: str, content: str) -> bool:
    """
    Inject a file into the Docker sandbox persistent volume.

    Uses a temporary alpine container to write to the docker-claude-sandbox-data volume.
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
                "docker-claude-sandbox-data:/data",
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


def get_sandbox_settings() -> dict | None:
    """
    Read current settings from the Docker sandbox volume.

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
                "docker-claude-sandbox-data:/data",
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


def prepare_sandbox_volume_for_credentials() -> bool:
    """
    Prepare the Docker sandbox volume for credential persistence.

    The Docker sandbox volume has a permissions issue where files are created as
    root:root, but the sandbox runs as agent (uid=1000). This function:
    1. Creates .claude.json (OAuth) if it doesn't exist (owned by uid 1000)
    2. Creates credentials.json (API keys) if it doesn't exist (owned by uid 1000)
    3. Fixes directory permissions so agent user can write
    4. Ensures existing files are writable by agent

    OAuth credentials (Claude Max subscription) are stored in .claude.json,
    while API keys are stored in credentials.json. Both need proper permissions.

    Returns:
        True if preparation successful
    """
    try:
        # Fix permissions on the volume directory and create credential files
        # The agent user in the sandbox has uid=1000
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-v",
                "docker-claude-sandbox-data:/data",
                "alpine",
                "sh",
                "-c",
                # Fix directory permissions
                "chmod 777 /data && "
                # Prepare .claude.json (OAuth credentials - Claude Max subscription)
                "touch /data/.claude.json && "
                "chown 1000:1000 /data/.claude.json && "
                "chmod 666 /data/.claude.json && "
                # Prepare credentials.json (API keys)
                "touch /data/credentials.json && "
                "chown 1000:1000 /data/credentials.json && "
                "chmod 666 /data/credentials.json && "
                # Fix settings.json permissions if it exists
                "chown 1000:1000 /data/settings.json 2>/dev/null; "
                "chmod 666 /data/settings.json 2>/dev/null; "
                "echo 'Volume prepared for credentials'",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def inject_settings(settings: dict) -> bool:
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


def inject_team_settings(team_name: str, org_config: dict | None = None) -> bool:
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
        from . import claude_adapter, profiles

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
        from . import teams

        team_settings = teams.get_team_sandbox_settings(team_name)

        if not team_settings:
            return True

        return inject_settings(team_settings)


def launch_with_org_config(
    workspace: Path,
    org_config: dict,
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
    from . import claude_adapter, profiles

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
    org_config: dict,
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
    from . import claude_adapter, profiles
    from .errors import PolicyViolationError

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
