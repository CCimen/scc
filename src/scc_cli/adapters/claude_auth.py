"""Host-browser auth bootstrap for containerized Claude sessions."""

from __future__ import annotations

import subprocess
from pathlib import Path

from scc_cli.core.errors import ProviderNotReadyError
from scc_cli.core.provider_registry import get_runtime_spec


def build_claude_browser_auth_command() -> list[str]:
    """Build the host-side Claude login command."""
    return ["claude", "auth", "login", "--claudeai"]


def run_claude_browser_auth() -> int:
    """Run browser-based Claude login, then sync the resulting cache to Docker."""
    try:
        result = subprocess.run(build_claude_browser_auth_command(), check=False)
    except FileNotFoundError as exc:
        raise ProviderNotReadyError(
            provider_id="claude",
            user_message=(
                "Claude browser sign-in cannot start because the host 'claude' CLI "
                "is not installed."
            ),
            suggested_action=(
                "Install Claude Code on the host, or connect Claude later from an "
                "environment where the host CLI is available."
            ),
        ) from exc

    if result.returncode == 0:
        _sync_host_claude_auth_to_volume()
    return result.returncode


def _sync_host_claude_auth_to_volume() -> None:
    """Copy host Claude auth files into the persistent Docker volume."""
    spec = get_runtime_spec("claude")
    for source_path, volume_filename in _host_claude_auth_files().items():
        if not source_path.exists():
            continue

        subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "-i",
                "-v",
                f"{spec.data_volume}:/data",
                "alpine",
                "sh",
                "-lc",
                (
                    f"cat > /data/{volume_filename} && "
                    f"chown 1000:1000 /data/{volume_filename} && "
                    f"chmod 0600 /data/{volume_filename}"
                ),
            ],
            input=source_path.read_text(),
            text=True,
            capture_output=True,
            check=False,
        )


def _host_claude_auth_files() -> dict[Path, str]:
    """Return host Claude auth files that should be imported into the volume."""
    return {
        Path.home() / ".claude.json": ".claude.json",
    }
