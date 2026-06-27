"""Container action handlers for the dashboard orchestrator.

This module owns stop, resume, and remove side effects for dashboard container
rows. Handlers prepare terminal state, execute Docker actions, and return
structured container action results.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from scc_cli.application.dashboard_models import ContainerActionResult

from ...console import get_err_console

if TYPE_CHECKING:
    from rich.console import Console


def _prepare_for_nested_ui(console: Console) -> None:
    """Prepare terminal state for nested UI."""
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


def _handle_container_stop(container_id: str, container_name: str) -> ContainerActionResult:
    """Stop a container from the dashboard."""
    from rich.status import Status

    from ... import docker
    from ...theme import Spinners

    console = get_err_console()
    _prepare_for_nested_ui(console)

    status = docker.get_container_status(container_name)
    if status and status.startswith("Up") is False:
        return ContainerActionResult(success=True, message=f"Already stopped: {container_name}")

    with Status(
        f"[cyan]Stopping {container_name}...[/cyan]",
        console=console,
        spinner=Spinners.DOCKER,
    ):
        success = docker.stop_container(container_id)

    return ContainerActionResult(
        success=success,
        message=f"Stopped {container_name}" if success else f"Failed to stop {container_name}",
    )


def _handle_container_resume(container_id: str, container_name: str) -> ContainerActionResult:
    """Resume a container from the dashboard."""
    from rich.status import Status

    from ... import docker
    from ...theme import Spinners

    console = get_err_console()
    _prepare_for_nested_ui(console)

    status = docker.get_container_status(container_name)
    if status and status.startswith("Up"):
        return ContainerActionResult(success=True, message=f"Already running: {container_name}")

    with Status(
        f"[cyan]Starting {container_name}...[/cyan]",
        console=console,
        spinner=Spinners.DOCKER,
    ):
        success = docker.resume_container(container_id)

    return ContainerActionResult(
        success=success,
        message=f"Resumed {container_name}" if success else f"Failed to resume {container_name}",
    )


def _handle_container_remove(container_id: str, container_name: str) -> ContainerActionResult:
    """Remove a stopped container from the dashboard."""
    from rich.status import Status

    from ... import docker
    from ...theme import Spinners

    console = get_err_console()
    _prepare_for_nested_ui(console)

    status = docker.get_container_status(container_name)
    if status and status.startswith("Up"):
        return ContainerActionResult(
            success=False, message=f"Stop {container_name} before deleting"
        )

    with Status(
        f"[cyan]Removing {container_name}...[/cyan]",
        console=console,
        spinner=Spinners.DOCKER,
    ):
        success = docker.remove_container(container_name or container_id)

    return ContainerActionResult(
        success=success,
        message=f"Removed {container_name}" if success else f"Failed to remove {container_name}",
    )
