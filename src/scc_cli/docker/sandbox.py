"""
Docker sandbox runtime: container launch, plugin injection, and marketplace seeding.

Extracted from launch.py to keep modules under 800 lines.
Contains run_sandbox() and the helpers it calls during container startup.

**Legacy Docker Desktop sandbox path.** This module implements the ``docker
sandbox run`` container launch flow (Docker Desktop >= 4.50). It is NOT used by
the OCI-based launch path (see ``adapters/oci_sandbox_runtime.py``). Retained
for users whose Docker Desktop includes the sandbox feature.
"""

import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, NoReturn

from ..core.errors import SandboxLaunchError
from .core import build_command
from .credentials import (
    _create_symlinks_in_container,
    _preinit_credential_volume,
    _start_migration_loop,
    _sync_credentials_from_existing_containers,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Mount Race Detection
# ─────────────────────────────────────────────────────────────────────────────


def _is_mount_race_error(stderr: str) -> bool:
    """Check if Docker error is a mount race condition (retryable).

    Docker Desktop's VirtioFS can have delays before newly created files
    are visible. This function detects these specific errors.

    Args:
        stderr: The stderr output from the Docker command.

    Returns:
        True if the error indicates a mount race condition.
    """
    error_lower = stderr.lower()
    return (
        "bind source path does not exist" in error_lower
        or "no such file or directory" in error_lower
    )


# ─────────────────────────────────────────────────────────────────────────────
# Plugin Marketplace Cache
# ─────────────────────────────────────────────────────────────────────────────


def _build_known_marketplaces_cache(settings: dict[str, Any]) -> dict[str, Any]:
    """Build known_marketplaces.json payload from injected settings."""
    marketplaces = settings.get("extraKnownMarketplaces")
    if not isinstance(marketplaces, dict):
        return {}

    now_iso = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    cache: dict[str, Any] = {}

    for name, entry in marketplaces.items():
        if not isinstance(entry, dict):
            continue
        source = entry.get("source")
        if not isinstance(source, dict):
            continue

        cache_entry: dict[str, Any] = {
            "source": source,
            "lastUpdated": now_iso,
        }

        if source.get("source") == "directory":
            path = source.get("path")
            if isinstance(path, str) and path:
                cache_entry["installLocation"] = path

        cache[str(name)] = cache_entry

    return cache


def seed_container_plugin_marketplaces(container_id: str, settings: dict[str, Any]) -> bool:
    """
    Pre-seed Claude Code's known marketplaces inside a running container.

    Claude's startup sequence may scan enabled plugins before processing
    extraKnownMarketplaces from settings. Writing known_marketplaces.json
    ahead of time prevents transient "Plugin not found in marketplace" errors.

    Returns:
        True if seed successful or not needed, False otherwise
    """
    payload = _build_known_marketplaces_cache(settings)
    if not payload:
        return True

    try:
        payload_json = json.dumps(payload, indent=2)
        escaped_payload = payload_json.replace("'", "'\"'\"'")

        result = subprocess.run(
            [
                "docker",
                "exec",
                container_id,
                "sh",
                "-c",
                (
                    "mkdir -p /home/agent/.claude/plugins && "
                    f"printf '%s' '{escaped_payload}' "
                    "> /home/agent/.claude/plugins/known_marketplaces.json"
                ),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Plugin Settings Injection
# ─────────────────────────────────────────────────────────────────────────────


def inject_plugin_settings_to_container(
    container_id: str,
    settings: dict[str, Any],
) -> bool:
    """
    Inject plugin settings into container HOME directory.

    This writes settings to /home/agent/.claude/settings.json inside the container.
    Used for container-only plugin configuration to prevent host Claude from
    seeing SCC-managed plugins.

    The settings contain extraKnownMarketplaces and enabledPlugins with absolute
    paths pointing to the bind-mounted workspace.

    Args:
        container_id: Docker container ID to inject settings into
        settings: Settings dict containing extraKnownMarketplaces and enabledPlugins

    Returns:
        True if injection successful, False otherwise
    """
    try:
        # Serialize settings to JSON
        settings_json = json.dumps(settings, indent=2)

        # Use docker exec to write settings to container HOME
        # First ensure the .claude directory exists
        mkdir_result = subprocess.run(
            [
                "docker",
                "exec",
                container_id,
                "mkdir",
                "-p",
                "/home/agent/.claude",
            ],
            capture_output=True,
            timeout=10,
        )

        if mkdir_result.returncode != 0:
            return False

        # Write settings via sh -c and echo/printf
        # Using printf to handle special characters properly
        # Escape single quotes in JSON for shell
        escaped_json = settings_json.replace("'", "'\"'\"'")

        write_result = subprocess.run(
            [
                "docker",
                "exec",
                container_id,
                "sh",
                "-c",
                f"printf '%s' '{escaped_json}' > /home/agent/.claude/settings.json",
            ],
            capture_output=True,
            timeout=10,
        )

        return write_result.returncode == 0

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Sandbox Launch
# ─────────────────────────────────────────────────────────────────────────────


def _reset_global_settings_for_sandbox() -> None:
    # Deferred import avoids the launch<->sandbox cycle and keeps test patch points stable.
    from .launch import reset_global_settings

    if not reset_global_settings():
        logger.warning(
            "Failed to reset global settings. Plugin mixing may occur if switching teams."
        )


def _write_safety_net_policy(org_config: dict[str, Any] | None) -> Path | None:
    from .launch import (
        get_effective_safety_net_policy,
        write_safety_net_policy_to_host,
    )

    effective_policy = get_effective_safety_net_policy(org_config)
    return write_safety_net_policy_to_host(effective_policy)


def _start_detached_container(detached_cmd: list[str]) -> str:
    max_retries = 5
    base_delay = 0.5  # Start with 500ms, exponential backoff
    last_result: subprocess.CompletedProcess[str] | None = None

    for attempt in range(max_retries):
        result = subprocess.run(
            detached_cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        last_result = result

        if result.returncode == 0:
            break

        if _is_mount_race_error(result.stderr) and attempt < max_retries - 1:
            delay = base_delay * (2**attempt)  # 0.5s, 1s, 2s, 4s
            logger.warning(
                "Docker mount race detected, retrying in %.1fs (%d/%d)...",
                delay,
                attempt + 1,
                max_retries,
            )
            time.sleep(delay)
        else:
            break

    if last_result is None or last_result.returncode != 0:
        stderr = last_result.stderr if last_result else ""
        raise SandboxLaunchError(
            user_message="Failed to create Docker sandbox",
            command=" ".join(detached_cmd),
            stderr=stderr,
        )

    container_id = last_result.stdout.strip()
    if not container_id:
        raise SandboxLaunchError(
            user_message="Docker sandbox returned empty container ID",
            command=" ".join(detached_cmd),
        )

    return container_id


def _inject_container_plugin_settings(
    container_id: str,
    plugin_settings: dict[str, Any] | None,
) -> None:
    if not plugin_settings:
        return

    if not inject_plugin_settings_to_container(container_id, plugin_settings):
        logger.warning(
            "Failed to inject plugin settings. SCC-managed plugins may not be available."
        )
    elif not seed_container_plugin_marketplaces(container_id, plugin_settings):
        logger.warning(
            "Failed to pre-seed plugin marketplaces after settings injection. "
            "Claude may show transient plugin lookup errors."
        )


def _exec_claude_in_container(
    *,
    container_id: str,
    workspace: Path | None,
    container_workdir: Path | None,
    continue_session: bool,
    resume: bool,
) -> NoReturn:
    exec_workdir = container_workdir if container_workdir else workspace
    exec_cmd = ["docker", "exec", "-it", "-w", str(exec_workdir), container_id, "claude"]

    # Safe in this path because Docker Desktop sandbox already provides isolation.
    exec_cmd.append("--dangerously-skip-permissions")

    if continue_session:
        exec_cmd.append("-c")
    elif resume:
        exec_cmd.append("--resume")

    os.execvp("docker", exec_cmd)
    raise SandboxLaunchError(
        user_message="Failed to exec into Docker sandbox",
        command=" ".join(exec_cmd),
    )


def _run_credential_sandbox(
    *,
    workspace: Path | None,
    container_workdir: Path | None,
    continue_session: bool,
    resume: bool,
    plugin_settings: dict[str, Any] | None,
    policy_host_path: Path | None,
    env_vars: dict[str, str] | None,
) -> NoReturn:
    # Sync credentials from existing containers to volume.
    _sync_credentials_from_existing_containers()

    # Pre-initialize volume files to prevent EOF race conditions.
    _preinit_credential_volume()

    detached_cmd = build_command(
        workspace=workspace,
        detached=True,
        policy_host_path=policy_host_path,
        env_vars=env_vars,
    )
    container_id = _start_detached_container(detached_cmd)

    _create_symlinks_in_container(container_id)
    _start_migration_loop(container_id)
    _inject_container_plugin_settings(container_id, plugin_settings)
    _exec_claude_in_container(
        container_id=container_id,
        workspace=workspace,
        container_workdir=container_workdir,
        continue_session=continue_session,
        resume=resume,
    )


def _run_noncredential_sandbox(cmd: list[str]) -> int:
    if os.name != "nt":
        os.execvp(cmd[0], cmd)
        raise SandboxLaunchError(
            user_message="Failed to start Docker sandbox",
            command=" ".join(cmd),
        )

    result = subprocess.run(cmd, text=True)
    return result.returncode


def run_sandbox(
    workspace: Path | None = None,
    continue_session: bool = False,
    resume: bool = False,
    ensure_credentials: bool = True,
    org_config: dict[str, Any] | None = None,
    container_workdir: Path | None = None,
    plugin_settings: dict[str, Any] | None = None,
    env_vars: dict[str, str] | None = None,
) -> int:
    """
    Run Claude in a Docker sandbox with credential persistence.

    Uses SYNCHRONOUS detached→symlink→exec pattern to eliminate race condition:
    1. Start container in DETACHED mode (no Claude running yet)
    2. Create symlinks BEFORE Claude starts (race eliminated!)
    3. Inject plugin settings to container HOME (if provided)
    4. Exec Claude interactively using docker exec

    This replaces the previous fork-and-inject pattern which had a fundamental
    race condition: parent became Docker at T+0, child created symlinks at T+2s,
    but Claude read config at T+0 before symlinks existed.

    Args:
        workspace: Path to mount as workspace (-w flag for docker sandbox run).
            For worktrees, this is the common parent directory.
        continue_session: Pass -c flag to Claude
        resume: Pass --resume flag to Claude
        ensure_credentials: If True, create credential symlinks
        org_config: Organization config dict. If provided, security.safety_net
            policy is extracted and mounted read-only into container for the
            scc-safety-net plugin. If None, a default fail-safe policy is used.
        container_workdir: Working directory for Claude inside container
            (-w flag for docker exec). If None, defaults to workspace.
            For worktrees, this should be the actual workspace path so Claude
            finds .claude/settings.local.json.
        plugin_settings: Plugin settings dict to inject into container HOME.
            Contains extraKnownMarketplaces and enabledPlugins. Injected to
            /home/agent/.claude/settings.json to prevent host leakage.
        env_vars: Environment variables to set for the sandbox runtime.

    Returns:
        Exit code from Docker process

    Raises:
        SandboxLaunchError: If Docker command fails to start
    """
    try:
        _reset_global_settings_for_sandbox()
        policy_host_path = _write_safety_net_policy(org_config)

        if os.name != "nt" and ensure_credentials:
            _run_credential_sandbox(
                workspace=workspace,
                container_workdir=container_workdir,
                continue_session=continue_session,
                resume=resume,
                plugin_settings=plugin_settings,
                policy_host_path=policy_host_path,
                env_vars=env_vars,
            )

        # Non-credential mode or Windows: this path uses workspace for both
        # mount and cwd. Worktrees require the credential exec path above.
        cmd = build_command(
            workspace=workspace,
            continue_session=continue_session,
            resume=resume,
            detached=False,
            policy_host_path=policy_host_path,
            env_vars=env_vars,
        )
        return _run_noncredential_sandbox(cmd)

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
