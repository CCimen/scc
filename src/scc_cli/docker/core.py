"""
Provide Docker core operations: checks, commands, container lifecycle, and queries.

Contain stateless Docker primitives that don't manage persistent state.
For credential persistence, see credentials.py.
"""

import datetime
import hashlib
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..core.constants import SANDBOX_IMAGE
from ..core.errors import (
    ContainerNotFoundError,
    DockerNotFoundError,
    DockerVersionError,
    SandboxNotAvailableError,
)
from ..subprocess_utils import run_command, run_command_bool

# Minimum Docker Desktop version required for sandbox feature
MIN_DOCKER_VERSION = "4.50.0"

# Label prefix for SCC containers
LABEL_PREFIX = "scc"

# Docker sandbox labels (Docker Desktop)
SANDBOX_LABEL_KEY = "docker/sandbox"
SANDBOX_AGENT_LABEL = "com.docker.sandbox.agent"
SANDBOX_WORKDIR_LABEL = "com.docker.sandbox.workingDirectory"


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
    """Check whether Docker is installed and in PATH."""
    return shutil.which("docker") is not None


def _parse_version(version_string: str) -> tuple[int, int, int]:
    """Parse version string into comparable tuple."""
    # Extract version number from strings like "Docker version 27.5.1, build..."
    match = re.search(r"(\d+)\.(\d+)\.(\d+)", version_string)
    if match:
        major, minor, patch = (int(x) for x in match.groups())
        return (major, minor, patch)
    return (0, 0, 0)


def check_docker_available() -> None:
    """
    Check if Docker is available and meets requirements.

    Raises:
        DockerNotFoundError: Docker is not installed
        DockerVersionError: Docker Desktop version is too old
        SandboxNotAvailableError: Sandbox feature not available
    """
    # Check Docker is installed
    if not _check_docker_installed():
        raise DockerNotFoundError()

    # Check Docker Desktop version when available (sandbox requirement)
    desktop_version = get_docker_desktop_version()
    if desktop_version:
        current = _parse_version(desktop_version)
        required = _parse_version(MIN_DOCKER_VERSION)
        if current < required:
            raise DockerVersionError(current_version=desktop_version)

    # Check sandbox command exists
    if not check_docker_sandbox():
        raise SandboxNotAvailableError()


def check_docker_sandbox() -> bool:
    """Check whether Docker sandbox feature is available (Docker Desktop 4.50+)."""
    if not _check_docker_installed():
        return False

    output = run_command(["docker", "sandbox", "--help"], timeout=10)
    if not output:
        return False

    normalized = output.lower()
    # True sandbox CLI prints a specific help header (not generic docker help)
    return (
        "docker sandbox" in normalized
        or "sandbox run" in normalized
        or "run an ai agent inside a sandbox" in normalized
    )


def get_docker_version() -> str | None:
    """Get Docker version string."""
    return run_command(["docker", "--version"], timeout=5)


def get_docker_desktop_version() -> str | None:
    """Get Docker Desktop version string, if available."""

    def _extract_desktop_version(text: str) -> str | None:
        if not text:
            return None
        match = re.search(r"Docker Desktop\s+([0-9]+\.[0-9]+\.[0-9]+)", text, re.I)
        if match:
            return match.group(1)
        match = re.search(r"Desktop\s+version\s*:?\s*([0-9]+\.[0-9]+\.[0-9]+)", text, re.I)
        if match:
            return match.group(1)
        return None

    platform_name = run_command(
        ["docker", "version", "--format", "{{.Server.Platform.Name}}"], timeout=5
    )
    desktop_version = _extract_desktop_version(platform_name or "")
    if desktop_version:
        return desktop_version

    desktop_output = run_command(["docker", "desktop", "version"], timeout=5)
    return _extract_desktop_version(desktop_output or "")


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
    """Check whether a container with the given name exists (running or stopped)."""
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
    """Return the status of a container (running, exited, etc.)."""
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
    policy_host_path: Path | None = None,
) -> list[str]:
    """
    Build the docker sandbox run command.

    Structure: docker sandbox run [options] claude [claude-options]

    Args:
        workspace: Path to mount as workspace (-w flag)
        continue_session: Pass -c flag to Claude (ignored in detached mode)
        resume: Pass --resume flag to Claude (ignored in detached mode)
        detached: Create container without running agent (-d flag)
        policy_host_path: Host path to safety net policy file to bind-mount read-only.
            If provided, mounts at /mnt/claude-data/effective_policy.json:ro
            and sets SCC_POLICY_PATH env var for the plugin.

    Returns:
        Command as list of strings

    CRITICAL (DO NOT CHANGE):
        - Agent `claude` is ALWAYS included, even in detached mode
        - Session flags passed via docker exec in detached mode (see run_sandbox)
    """
    from ..core.constants import SAFETY_NET_POLICY_FILENAME, SANDBOX_DATA_MOUNT

    cmd = ["docker", "sandbox", "run"]

    # Detached mode: create container without running Claude interactively
    # This allows us to create symlinks BEFORE Claude starts
    if detached:
        cmd.append("-d")

    # Add read-only bind mount for safety net policy (kernel-enforced security)
    # This MUST be added before the agent name in the command
    #
    # Design note: We mount the FILE directly (not a directory) because:
    # - Containers are ephemeral (recreated each `scc start`)
    # - Policy is written before container creation, so new containers get current policy
    # - If we ever support container reuse or hot-reload, switch to directory mount
    #   (file mounts pin to inode; atomic rename would be invisible to running container)
    if policy_host_path is not None:
        container_policy_path = f"{SANDBOX_DATA_MOUNT}/{SAFETY_NET_POLICY_FILENAME}"
        # -v host_path:container_path:ro  ← Kernel-enforced read-only
        # Even sudo inside container cannot bypass `:ro` - requires CAP_SYS_ADMIN
        # Use os.fspath() to reliably convert Path to string
        cmd.extend(["-v", f"{os.fspath(policy_host_path)}:{container_policy_path}:ro"])
        # Set SCC_POLICY_PATH env var so plugin knows where to read policy
        cmd.extend(["-e", f"SCC_POLICY_PATH={container_policy_path}"])

    # Add workspace mount
    if workspace:
        cmd.extend(["-w", str(workspace)])

    # Agent name is ALWAYS required (docker sandbox run requires <agent>)
    cmd.append("claude")

    # Skip permission prompts by default - safe since we're in a sandbox container
    # The Docker sandbox already provides isolation, so the extra prompts are redundant
    cmd.append("--dangerously-skip-permissions")

    # In interactive mode (not detached), add Claude-specific arguments
    # In detached mode, skip these - we'll pass them via docker exec later
    if not detached:
        if continue_session:
            cmd.append("-c")
        elif resume:
            cmd.append("--resume")

    return cmd


def build_start_command(container_name: str) -> list[str]:
    """Build command to resume an existing container and return it."""
    return ["docker", "start", "-ai", container_name]


def run_detached(cmd: list[str]) -> subprocess.Popen[bytes]:
    """Run Docker command in background and return the process handle."""
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
    # Import here to avoid circular dependency
    from .launch import run

    if not container_exists(container_name):
        raise ContainerNotFoundError(container_name=container_name)

    cmd = build_start_command(container_name)
    return run(cmd)


def stop_container(container_id: str) -> bool:
    """Stop a running container and return success status."""
    return run_command_bool(["docker", "stop", container_id], timeout=30)


def resume_container(container_id: str) -> bool:
    """Start a stopped container in background and return success status.

    Unlike start_container() which attaches interactively, this just starts
    the container and returns immediately. Suitable for batch operations.
    """
    return run_command_bool(["docker", "start", container_id], timeout=30)


def remove_container(container_name: str, force: bool = False) -> bool:
    """Remove a container and return success status."""
    cmd = ["docker", "rm"]
    if force:
        cmd.append("-f")
    cmd.append("--")
    cmd.append(container_name)
    return run_command_bool(cmd, timeout=30)


def _list_sandbox_containers_by_label() -> list[ContainerInfo]:
    """List Claude sandboxes using Docker Desktop label metadata.

    Returns containers with workspace paths when available via labels.
    Falls back to empty list on any error.
    """
    try:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"label={SANDBOX_LABEL_KEY}=true",
                "--filter",
                f"label={SANDBOX_AGENT_LABEL}=claude",
                "--format",
                f'{{{{.ID}}}}\t{{{{.Names}}}}\t{{{{.Status}}}}\t{{{{.Label "{SANDBOX_WORKDIR_LABEL}"}}}}',
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return []

        containers: list[ContainerInfo] = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 3:
                workspace = parts[3] if len(parts) > 3 else None
                if workspace == "":
                    workspace = None
                containers.append(
                    ContainerInfo(
                        id=parts[0],
                        name=parts[1],
                        status=parts[2],
                        workspace=workspace,
                    )
                )

        return containers
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def _list_all_sandbox_containers() -> list[ContainerInfo]:
    """
    List ALL Claude Code sandbox containers (running AND stopped).

    This is critical for credential recovery - when user does /exit,
    the container STOPS but still contains the OAuth credentials.

    Returns list of ContainerInfo objects sorted by most recent first.
    """
    # Prefer label-based discovery for richer metadata (workspace path).
    containers = _list_sandbox_containers_by_label()
    if containers:
        return containers

    try:
        # Fallback: filter by sandbox image (older Docker versions)
        result = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                f"ancestor={SANDBOX_IMAGE}",
                "--format",
                "{{.ID}}\t{{.Names}}\t{{.Status}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return []

        containers_fallback: list[ContainerInfo] = []
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split("\t")
                if len(parts) >= 3:
                    containers_fallback.append(
                        ContainerInfo(
                            id=parts[0],
                            name=parts[1],
                            status=parts[2],
                        )
                    )

        return containers_fallback
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


def list_scc_containers() -> list[ContainerInfo]:
    """Return all SCC-managed containers (running and stopped).

    Includes Docker Desktop Claude sandboxes which do not support SCC labels.
    """
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

        containers: list[ContainerInfo] = []
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

        # Merge in Docker sandbox containers (dedupe by ID)
        sandbox_containers = _list_all_sandbox_containers()
        if sandbox_containers:
            existing_ids = {c.id for c in containers}
            for container in sandbox_containers:
                if container.id not in existing_ids:
                    containers.append(container)

        return containers
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return _list_all_sandbox_containers()


def list_running_sandboxes() -> list[ContainerInfo]:
    """
    Return running Claude Code sandboxes (created by Docker Desktop).

    Docker sandbox containers are identified by the sandbox image
    (docker/sandbox-templates:claude-code).
    """
    try:
        # Filter by the Docker sandbox image
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                f"ancestor={SANDBOX_IMAGE}",
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
