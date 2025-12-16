"""
Docker sandbox operations.

Container re-use pattern:
- Containers are named deterministically: scc-<workspace_hash>-<branch_hash>
- On start: check if container exists, resume if so, create if not
- Docker labels store metadata (profile, workspace, branch, created timestamp)
"""

import subprocess
import shutil
import hashlib
import re
import os
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass

from .errors import (
    DockerNotFoundError,
    DockerVersionError,
    SandboxNotAvailableError,
    SandboxLaunchError,
    ContainerNotFoundError,
    ToolError,
)


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
    profile: Optional[str] = None
    workspace: Optional[str] = None
    branch: Optional[str] = None
    created: Optional[str] = None


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

    try:
        result = subprocess.run(
            ["docker", "sandbox", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_docker_version() -> Optional[str]:
    """Get Docker version string."""
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def generate_container_name(workspace: Path, branch: Optional[str] = None) -> str:
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
    try:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"name=^{container_name}$",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return container_name in result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_container_status(container_name: str) -> Optional[str]:
    """Get the status of a container (running, exited, etc.)."""
    try:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"name=^{container_name}$",
                "--format",
                "{{.Status}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def build_labels(
    profile: Optional[str] = None,
    workspace: Optional[Path] = None,
    branch: Optional[str] = None,
) -> Dict[str, str]:
    """Build Docker labels for container metadata."""
    import datetime

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
    workspace: Optional[Path] = None,
    container_name: Optional[str] = None,
    session_name: Optional[str] = None,
    continue_session: bool = False,
    resume: bool = False,
    env_vars: Optional[Dict[str, str]] = None,
    labels: Optional[Dict[str, str]] = None,
) -> List[str]:
    """
    Build the docker sandbox run command.

    Args:
        workspace: Path to mount as workspace
        container_name: Name for the container (for re-use)
        session_name: Claude session name
        continue_session: Pass -c flag to Claude
        resume: Pass --resume flag to Claude
        env_vars: Environment variables to set
        labels: Docker labels to apply

    Returns:
        Command as list of strings
    """
    cmd = ["docker", "sandbox", "run"]

    # Add container name if provided
    if container_name:
        cmd.extend(["--name", container_name])

    # Add workspace mount
    if workspace:
        cmd.extend(["-w", str(workspace)])

    # Add labels
    if labels:
        for key, value in labels.items():
            cmd.extend(["--label", f"{key}={value}"])

    # Add environment variables
    if env_vars:
        for key, value in env_vars.items():
            cmd.extend(["-e", f"{key}={value}"])

    # Add the claude agent
    cmd.append("claude")

    # Add session flags (passed to Claude Code)
    if continue_session:
        cmd.append("-c")
    elif resume:
        cmd.append("--resume")

    return cmd


def build_start_command(container_name: str) -> List[str]:
    """Build command to resume an existing container."""
    return ["docker", "start", "-ai", container_name]


def run(cmd: List[str]) -> int:
    """
    Execute the Docker command.

    On Unix: Uses os.execvp to replace current process (most efficient)
    On Windows: Uses subprocess.run

    Raises:
        SandboxLaunchError: If Docker command fails to start
    """
    try:
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


def run_detached(cmd: List[str]) -> subprocess.Popen:
    """Run Docker command in background (for multiple worktrees)."""
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
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
    try:
        result = subprocess.run(
            ["docker", "stop", container_id],
            capture_output=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def remove_container(container_name: str, force: bool = False) -> bool:
    """Remove a container."""
    try:
        cmd = ["docker", "rm"]
        if force:
            cmd.append("-f")
        cmd.append(container_name)

        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def list_scc_containers() -> List[ContainerInfo]:
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
                "{{.ID}}\t{{.Names}}\t{{.Status}}\t{{.Label \"scc.profile\"}}\t{{.Label \"scc.workspace\"}}\t{{.Label \"scc.branch\"}}",
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


def list_running_sandboxes() -> List[Dict[str, str]]:
    """
    List running Claude Code sandboxes.

    Returns list of dicts with id, name, status keys.
    (Kept for backward compatibility)
    """
    try:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                "ancestor=claude",
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
                        {
                            "id": parts[0],
                            "name": parts[1],
                            "status": parts[2],
                        }
                    )

        return sandboxes
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def get_or_create_container(
    workspace: Path,
    branch: Optional[str] = None,
    profile: Optional[str] = None,
    force_new: bool = False,
    continue_session: bool = False,
    env_vars: Optional[Dict[str, str]] = None,
) -> tuple[List[str], bool]:
    """
    Get existing container or create new one.

    This is the main entry point for container re-use pattern.

    Args:
        workspace: Path to workspace
        branch: Git branch name (optional, for container naming)
        profile: Team profile being used
        force_new: Force creation of new container (--fresh flag)
        continue_session: Pass -c flag to Claude
        env_vars: Environment variables

    Returns:
        Tuple of (command_to_run, is_resume)
        - is_resume=True means we're resuming existing container
        - is_resume=False means we're creating new container
    """
    container_name = generate_container_name(workspace, branch)

    # Check if we should resume existing container
    if not force_new and container_exists(container_name):
        # Resume existing container
        cmd = build_start_command(container_name)
        return cmd, True

    # Remove old container if it exists and we're forcing new
    if force_new and container_exists(container_name):
        remove_container(container_name, force=True)

    # Create new container
    labels = build_labels(profile=profile, workspace=workspace, branch=branch)
    cmd = build_command(
        workspace=workspace,
        container_name=container_name,
        continue_session=continue_session,
        env_vars=env_vars,
        labels=labels,
    )
    return cmd, False
