"""
Provide subprocess utilities for consistent error handling.

Define wrapper functions for subprocess execution with graceful timeout
and missing executable handling.
"""

import shutil
import subprocess


def run_command(
    cmd: list[str],
    timeout: int = 10,
    cwd: str | None = None,
) -> str | None:
    """Run command, return stdout if successful, None otherwise.

    Handle timeouts and missing executables gracefully.

    Args:
        cmd: Command and arguments as list of strings.
        timeout: Maximum seconds to wait for command.
        cwd: Working directory for command execution.

    Returns:
        Stripped stdout on success, None on any failure.
    """
    # Pre-check: handle empty command list
    if not cmd:
        return None

    # Pre-check: is the executable available?
    if not shutil.which(cmd[0]):
        return None

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


def run_command_bool(
    cmd: list[str],
    timeout: int = 10,
    cwd: str | None = None,
) -> bool:
    """Run command, return True if exit code is 0.

    Args:
        cmd: Command and arguments as list of strings.
        timeout: Maximum seconds to wait for command.
        cwd: Working directory for command execution.

    Returns:
        True if command succeeded (exit code 0), False otherwise.
    """
    return run_command(cmd, timeout, cwd) is not None


def run_command_lines(
    cmd: list[str],
    timeout: int = 10,
    cwd: str | None = None,
) -> list[str]:
    """Run command, return stdout split into lines.

    Args:
        cmd: Command and arguments as list of strings.
        timeout: Maximum seconds to wait for command.
        cwd: Working directory for command execution.

    Returns:
        List of output lines on success, empty list on failure.
    """
    output = run_command(cmd, timeout, cwd)
    if output is None:
        return []
    return [line for line in output.split("\n") if line.strip()]
