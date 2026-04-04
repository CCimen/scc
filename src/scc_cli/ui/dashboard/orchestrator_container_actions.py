"""Container action handlers for the dashboard orchestrator.

Extracted from orchestrator_handlers.py to keep that module below the
800-line threshold.  Every function follows the same pattern used by the
other handler helpers: get the Rich console, prepare for nested UI,
execute, and return ``(success, message)`` tuples.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...console import get_err_console

if TYPE_CHECKING:
    from rich.console import Console


def _prepare_for_nested_ui(console: Console) -> None:
    """Prepare terminal state for nested UI (thin copy — delegates to same logic)."""
    import io
    import sys

    console.show_cursor(True)
    console.print()

    try:
        import termios

        termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
    except (
        ModuleNotFoundError,
        OSError,
        ValueError,
        TypeError,
        io.UnsupportedOperation,
    ):
        pass


def _handle_container_stop(container_id: str, container_name: str) -> tuple[bool, str | None]:
    """Stop a container from the dashboard."""
    from rich.status import Status

    from ... import docker
    from ...theme import Spinners

    console = get_err_console()
    _prepare_for_nested_ui(console)

    status = docker.get_container_status(container_name)
    if status and status.startswith("Up") is False:
        return True, f"Already stopped: {container_name}"

    with Status(
        f"[cyan]Stopping {container_name}...[/cyan]",
        console=console,
        spinner=Spinners.DOCKER,
    ):
        success = docker.stop_container(container_id)

    return success, (f"Stopped {container_name}" if success else f"Failed to stop {container_name}")


def _handle_container_resume(container_id: str, container_name: str) -> tuple[bool, str | None]:
    """Resume a container from the dashboard."""
    from rich.status import Status

    from ... import docker
    from ...theme import Spinners

    console = get_err_console()
    _prepare_for_nested_ui(console)

    status = docker.get_container_status(container_name)
    if status and status.startswith("Up"):
        return True, f"Already running: {container_name}"

    with Status(
        f"[cyan]Starting {container_name}...[/cyan]",
        console=console,
        spinner=Spinners.DOCKER,
    ):
        success = docker.resume_container(container_id)

    return success, (
        f"Resumed {container_name}" if success else f"Failed to resume {container_name}"
    )


def _handle_container_remove(container_id: str, container_name: str) -> tuple[bool, str | None]:
    """Remove a stopped container from the dashboard."""
    from rich.status import Status

    from ... import docker
    from ...theme import Spinners

    console = get_err_console()
    _prepare_for_nested_ui(console)

    status = docker.get_container_status(container_name)
    if status and status.startswith("Up"):
        return False, f"Stop {container_name} before deleting"

    with Status(
        f"[cyan]Removing {container_name}...[/cyan]",
        console=console,
        spinner=Spinners.DOCKER,
    ):
        success = docker.remove_container(container_name or container_id)

    return success, (
        f"Removed {container_name}" if success else f"Failed to remove {container_name}"
    )
