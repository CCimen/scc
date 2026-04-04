"""
Docker sandbox runtime: container launch, plugin injection, and marketplace seeding.

Extracted from launch.py to keep modules under 800 lines.
Contains run_sandbox() and the helpers it calls during container startup.
"""

import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
    # Import sibling functions via module to keep test-patch compatibility.
    # Tests patch scc_cli.docker.sandbox.<name>; direct imports would bind
    # at import-time and be immune to patches.
    from .launch import (
        get_effective_safety_net_policy,
        reset_global_settings,
        write_safety_net_policy_to_host,
    )

    try:
        # STEP 0: Reset global settings to prevent plugin mixing across teams
        # This ensures only workspace settings.local.json drives plugins.
        # Called once per scc start flow, before container exec.
        if not reset_global_settings():
            logger.warning(
                "Failed to reset global settings. "
                "Plugin mixing may occur if switching teams."
            )

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
            # Use retry-with-backoff for Docker Desktop VirtioFS race conditions
            # (newly created files may not be immediately visible to Docker)
            detached_cmd = build_command(
                workspace=workspace,
                detached=True,
                policy_host_path=policy_host_path,
                env_vars=env_vars,
            )

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
                    break  # Success!

                # Check if this is a retryable mount race error
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
                    # Non-retryable error or last attempt failed
                    break

            # After retry loop, check final result
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

            # STEP 4: Create symlinks BEFORE Claude starts
            # This is the KEY fix - symlinks exist BEFORE Claude reads config
            _create_symlinks_in_container(container_id)

            # STEP 5: Start background migration loop for first-time login
            # This runs in background to capture OAuth tokens during login
            _start_migration_loop(container_id)

            # STEP 5.5: Inject plugin settings to container HOME (if provided)
            # This writes extraKnownMarketplaces and enabledPlugins to
            # /home/agent/.claude/settings.json - preventing host leakage
            # while ensuring container Claude can access SCC-managed plugins
            if plugin_settings:
                if not inject_plugin_settings_to_container(container_id, plugin_settings):
                    logger.warning(
                        "Failed to inject plugin settings. "
                        "SCC-managed plugins may not be available."
                    )
                elif not seed_container_plugin_marketplaces(container_id, plugin_settings):
                    logger.warning(
                        "Failed to pre-seed plugin marketplaces after settings injection. "
                        "Claude may show transient plugin lookup errors."
                    )

            # STEP 6: Exec Claude interactively (replaces current process)
            # Claude binary is at /home/agent/.local/bin/claude
            # Use -w to set working directory so Claude finds .claude/settings.local.json
            # For worktrees: workspace is mount path (parent), container_workdir is actual workspace
            exec_workdir = container_workdir if container_workdir else workspace
            exec_cmd = ["docker", "exec", "-it", "-w", str(exec_workdir), container_id, "claude"]

            # Skip permission prompts by default - safe since we're in a sandbox container
            # The Docker sandbox already provides isolation, so the extra prompts are redundant
            exec_cmd.append("--dangerously-skip-permissions")

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
            # NOTE: Legacy path uses workspace for BOTH mount and CWD via -w flag.
            # Worktrees require the exec path (credential mode) for separate mount/CWD.
            cmd = build_command(
                workspace=workspace,
                continue_session=continue_session,
                resume=resume,
                detached=False,
                policy_host_path=policy_host_path,
                env_vars=env_vars,
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
