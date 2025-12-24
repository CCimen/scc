"""
Credential persistence subsystem for Docker sandbox.

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

See run_sandbox() in launch.py for implementation.
===============================================================================
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from ..constants import OAUTH_CREDENTIAL_KEY, SANDBOX_DATA_VOLUME
from .core import _list_all_sandbox_containers, list_running_sandboxes


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
                f"{SANDBOX_DATA_VOLUME}:/data",
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
    Check whether the Docker volume already has valid OAuth credentials.

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
                f"{SANDBOX_DATA_VOLUME}:/data",
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
            return bool(creds and creds.get(OAUTH_CREDENTIAL_KEY))
        except json.JSONDecodeError:
            return False

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


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
                if not creds or not creds.get(OAUTH_CREDENTIAL_KEY):
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
                    f"{SANDBOX_DATA_VOLUME}:/data",
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
                        f"{SANDBOX_DATA_VOLUME}:/data",
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
                    if not creds or not creds.get(OAUTH_CREDENTIAL_KEY):
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
                        f"{SANDBOX_DATA_VOLUME}:/data",
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
                                f"{SANDBOX_DATA_VOLUME}:/data",
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
                if creds and creds.get(OAUTH_CREDENTIAL_KEY):
                    # Valid OAuth credentials - copy to volume
                    escaped = content.replace("'", "'\"'\"'")
                    subprocess.run(
                        [
                            "docker",
                            "run",
                            "--rm",
                            "-v",
                            f"{SANDBOX_DATA_VOLUME}:/data",
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
                    f"{SANDBOX_DATA_VOLUME}:/data",
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
        import time

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
                f"{SANDBOX_DATA_VOLUME}:/data",
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
