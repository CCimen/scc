"""Provider image readiness helpers for interactive launch flows."""

from __future__ import annotations

import shlex
import subprocess
from collections.abc import Callable
from pathlib import Path

from rich.console import Console
from rich.status import Status

from scc_cli.core.errors import ProviderImageBuildError, ProviderImageMissingError
from scc_cli.core.provider_registry import get_runtime_spec
from scc_cli.theme import Spinners

_IMAGE_CHECK_TIMEOUT = 10
_IMAGE_BUILD_TIMEOUT = 30 * 60


def ensure_provider_image(
    provider_id: str,
    *,
    console: Console,
    non_interactive: bool,
    show_notice: Callable[[str, str, str], None],
) -> None:
    """Ensure the selected provider image exists locally.

    Interactive flows auto-build the missing image from SCC's bundled Dockerfile.
    Non-interactive flows fail fast with the exact build command.
    """
    spec = get_runtime_spec(provider_id)
    if _provider_image_exists(spec.image_ref):
        return

    build_command = get_provider_build_command(provider_id)
    build_command_str = shlex.join(build_command)

    if non_interactive:
        raise ProviderImageMissingError(
            provider_id=provider_id,
            image_ref=spec.image_ref,
            suggested_action=f"Build the image first:\n  {build_command_str}",
        )

    show_notice(
        f"Preparing {spec.display_name}",
        (
            f"The local {spec.display_name} image is not available yet.\n\n"
            "SCC will build it now from the bundled Dockerfile before launch continues."
        ),
        "This usually happens only the first time or after an SCC reset.",
    )
    _build_provider_image(provider_id, console=console)


def get_provider_build_command(provider_id: str) -> list[str]:
    """Return the canonical docker build command for a provider image."""
    spec = get_runtime_spec(provider_id)
    build_context = _provider_build_context(provider_id)
    return ["docker", "build", "-t", spec.image_ref, str(build_context)]


def _provider_build_context(provider_id: str) -> Path:
    """Return the absolute Docker build context for a provider image."""
    repo_root = Path(__file__).resolve().parents[4]
    return repo_root / "images" / f"scc-agent-{provider_id}"


def _provider_image_exists(image_ref: str) -> bool:
    """Return whether the provider image is already present locally."""
    result = subprocess.run(
        ["docker", "image", "inspect", image_ref],
        capture_output=True,
        text=True,
        timeout=_IMAGE_CHECK_TIMEOUT,
        check=False,
    )
    if result.returncode == 0:
        return True

    stderr = (result.stderr or "").lower()
    stdout = (result.stdout or "").lower()
    missing_markers = ("no such image", "no such object", "not found")
    if any(marker in stderr for marker in missing_markers) or any(
        marker in stdout for marker in missing_markers
    ):
        return False
    return False


def _build_provider_image(provider_id: str, *, console: Console) -> None:
    """Build the provider image from SCC's local Dockerfile."""
    spec = get_runtime_spec(provider_id)
    build_command = get_provider_build_command(provider_id)
    build_command_str = shlex.join(build_command)
    build_context = _provider_build_context(provider_id)

    with Status(
        f"[cyan]Building {spec.display_name} image...[/cyan]",
        console=console,
        spinner=Spinners.DOCKER,
    ):
        result = subprocess.run(
            build_command,
            capture_output=True,
            text=True,
            timeout=_IMAGE_BUILD_TIMEOUT,
            check=False,
            cwd=build_context.parent.parent,
        )

    if result.returncode == 0:
        return

    raise ProviderImageBuildError(
        provider_id=provider_id,
        image_ref=spec.image_ref,
        build_command=build_command_str,
        command=build_command_str,
        stderr=result.stderr,
    )
