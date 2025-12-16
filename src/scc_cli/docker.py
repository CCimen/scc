"""
Docker sandbox operations.

Container re-use pattern:
- Containers are named deterministically: scc-<workspace_hash>-<branch_hash>
- On start: check if container exists, resume if so, create if not
- Docker labels store metadata (profile, workspace, branch, created timestamp)
"""

import datetime
import hashlib
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

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
) -> list[str]:
    """
    Build the docker sandbox run command.

    Docker sandbox run structure: docker sandbox run [sandbox-flags] claude [claude-args]

    Note: Docker sandbox is ephemeral - it doesn't support --name, --label,
    or -e flags. Volume mounts and credentials are handled automatically.

    Args:
        workspace: Path to mount as workspace (-w flag)
        continue_session: Pass -c flag to Claude
        resume: Pass --resume flag to Claude

    Returns:
        Command as list of strings
    """
    cmd = ["docker", "sandbox", "run"]

    # Add workspace mount (sandbox flag, goes before 'claude')
    if workspace:
        cmd.extend(["-w", str(workspace)])

    # Add the claude agent
    cmd.append("claude")

    # Add Claude-specific flags (go after 'claude')
    if continue_session:
        cmd.append("-c")
    elif resume:
        cmd.append("--resume")

    return cmd


def build_start_command(container_name: str) -> list[str]:
    """Build command to resume an existing container."""
    return ["docker", "start", "-ai", container_name]


def _ensure_credentials_symlink() -> bool:
    """
    Ensure the credentials.json symlink exists in a running sandbox.

    Docker Desktop's sandbox has a bug where credentials.json is not symlinked
    from ~/.claude/ to /mnt/claude-data/, causing credentials to not persist.
    This function creates the symlink if missing.

    Returns:
        True if symlink exists or was created successfully
    """
    import time

    # Find the running sandbox container
    sandboxes = list_running_sandboxes()
    if not sandboxes:
        return False

    container_id = sandboxes[0].id

    # Wait a moment for container to fully initialize
    time.sleep(2)

    try:
        # Create symlink if it doesn't exist (idempotent)
        result = subprocess.run(
            [
                "docker",
                "exec",
                container_id,
                "sh",
                "-c",
                # Check if symlink exists, create if not
                "[ -L /home/agent/.claude/credentials.json ] || "
                "ln -sf /mnt/claude-data/credentials.json /home/agent/.claude/credentials.json",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def run(cmd: list[str], ensure_credentials: bool = True) -> int:
    """
    Execute the Docker command.

    On Unix: Uses os.execvp to replace current process (most efficient)
    On Windows: Uses subprocess.run

    Args:
        cmd: Command to execute
        ensure_credentials: If True, spawn background process to ensure
            credentials.json symlink exists (workaround for Docker Desktop bug)

    Raises:
        SandboxLaunchError: If Docker command fails to start
    """
    try:
        # On Unix, fork a background process to fix credentials symlink
        # This must happen BEFORE execvp since execvp replaces the process
        if os.name != "nt" and ensure_credentials:
            pid = os.fork()
            if pid == 0:
                # Child process: wait and ensure symlink
                try:
                    import sys
                    import time

                    # Detach from terminal
                    os.setsid()

                    # Wait for sandbox to start
                    time.sleep(3)

                    # Ensure symlink exists
                    _ensure_credentials_symlink()

                    # Exit child process silently
                    sys.exit(0)
                except Exception:
                    sys.exit(1)
            # Parent continues to execvp

        # Use execvp to replace current process (Unix)
        if os.name != "nt":
            os.execvp(cmd[0], cmd)
            # If execvp returns, something went wrong
            raise SandboxLaunchError(
                user_message="Failed to start Docker sandbox",
                command=" ".join(cmd),
            )
        else:
            # On Windows, use subprocess
            result = subprocess.run(cmd)
            return result.returncode
    except FileNotFoundError:
        raise SandboxLaunchError(
            user_message=f"Command not found: {cmd[0]}",
            suggested_action="Ensure Docker is installed and in your PATH",
            command=" ".join(cmd),
        )
    except OSError as e:
        raise SandboxLaunchError(
            user_message=f"Failed to start Docker sandbox: {e}",
            command=" ".join(cmd),
        )


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


def inject_file_to_sandbox_volume(filename: str, content: str) -> bool:
    """
    Inject a file into the Docker sandbox persistent volume.

    Uses a temporary alpine container to write to the docker-claude-sandbox-data volume.
    Files are written to /data/ which maps to /mnt/claude-data/ in the sandbox.

    Args:
        filename: Name of file to create (e.g., "settings.json", "scc-statusline.sh")
        content: Content to write

    Returns:
        True if successful
    """
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
            import json

            return json.loads(result.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def prepare_sandbox_volume_for_credentials() -> bool:
    """
    Prepare the Docker sandbox volume for credential persistence.

    The Docker sandbox volume has a permissions issue where files are created as
    root:root, but the sandbox runs as agent (uid=1000). This function:
    1. Creates credentials.json if it doesn't exist (owned by uid 1000)
    2. Fixes directory permissions so agent user can write
    3. Ensures existing files are writable by agent

    This works around a Docker Desktop sandbox bug where the credentials.json
    symlink is not created and permissions are not set correctly.

    Returns:
        True if preparation successful
    """
    try:
        # Fix permissions on the volume directory and create credentials.json
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
                # Fix directory permissions, create credentials.json, set ownership
                "chmod 777 /data && "
                "touch /data/credentials.json && "
                "chown 1000:1000 /data/credentials.json && "
                "chmod 666 /data/credentials.json && "
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


def get_or_create_container(
    workspace: Path,
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
