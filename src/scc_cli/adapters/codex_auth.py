"""Host-browser auth bootstrap for containerized Codex sessions."""

from __future__ import annotations

import socket
import subprocess

from scc_cli.core.errors import ProviderNotReadyError
from scc_cli.core.provider_registry import get_runtime_spec

AUTH_CALLBACK_PORT = 1455
AUTH_RELAY_PORT = 1456


def _build_auth_relay_command() -> str:
    """Return the shell command that exposes Codex's loopback callback server.

    Codex binds its browser-login callback listener to ``127.0.0.1:1455`` inside
    the container. Docker port publishing cannot expose that loopback-only
    listener directly, so we run a tiny relay on ``0.0.0.0:1456`` and publish
    the host callback port to that relay instead.
    """
    return (
        f"socat TCP-LISTEN:{AUTH_RELAY_PORT},bind=0.0.0.0,reuseaddr,fork "
        f"TCP:127.0.0.1:{AUTH_CALLBACK_PORT} & "
        "exec codex login -c cli_auth_credentials_store=file"
    )


def build_codex_browser_auth_command() -> list[str]:
    """Build the temporary Docker command for browser-based Codex login."""
    spec = get_runtime_spec("codex")
    return [
        "docker",
        "run",
        "--rm",
        "-it",
        "--entrypoint",
        "/bin/sh",
        "-p",
        f"127.0.0.1:{AUTH_CALLBACK_PORT}:{AUTH_RELAY_PORT}",
        "-v",
        f"{spec.data_volume}:/home/agent/{spec.config_dir}",
        "-w",
        "/home/agent",
        spec.image_ref,
        "-lc",
        _build_auth_relay_command(),
    ]


def run_codex_browser_auth() -> int:
    """Run browser-based Codex login against the persistent provider volume."""
    if not _is_local_callback_port_available(AUTH_CALLBACK_PORT):
        raise ProviderNotReadyError(
            provider_id="codex",
            user_message=(
                "Codex browser sign-in cannot start because localhost:1455 is already in use."
            ),
            suggested_action=(
                "Free port 1455 and try again. If browser login is unavailable in this "
                "environment, use the device-code fallback instead."
            ),
        )

    result = subprocess.run(build_codex_browser_auth_command(), check=False)
    return result.returncode


def _is_local_callback_port_available(port: int) -> bool:
    """Return True when the localhost callback port can be bound."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True
