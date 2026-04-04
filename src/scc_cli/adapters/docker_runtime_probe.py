"""Docker runtime probe adapter.

Detects Docker runtime capabilities by calling existing helpers in
scc_cli.docker. Never raises from probe() — returns truthful state.
"""

from __future__ import annotations

from scc_cli.core.contracts import RuntimeInfo
from scc_cli.docker import (
    _check_docker_installed,
    check_docker_sandbox,
    get_docker_desktop_version,
    get_docker_version,
    run_command_bool,
)


class DockerRuntimeProbe:
    """Probe the local Docker runtime and return capability information."""

    def probe(self) -> RuntimeInfo:
        """Detect Docker runtime capabilities.

        Each detection step is defensive: failure at any point produces
        a RuntimeInfo reflecting only what was successfully detected.

        Returns:
            RuntimeInfo describing the Docker runtime state.
        """
        if not _check_docker_installed():
            return RuntimeInfo(
                runtime_id="docker",
                display_name="Docker (not installed)",
                cli_name="docker",
                supports_oci=False,
                supports_internal_networks=False,
                supports_host_network=False,
                daemon_reachable=False,
                sandbox_available=False,
            )

        version = get_docker_version()
        daemon_reachable = run_command_bool(["docker", "info"], timeout=5)

        if not daemon_reachable:
            return RuntimeInfo(
                runtime_id="docker",
                display_name="Docker (daemon not running)",
                cli_name="docker",
                supports_oci=True,
                supports_internal_networks=False,
                supports_host_network=False,
                version=version,
                daemon_reachable=False,
                sandbox_available=False,
            )

        desktop_version = get_docker_desktop_version()
        sandbox_available = check_docker_sandbox()

        display_name = "Docker Desktop" if desktop_version else "Docker Engine"

        return RuntimeInfo(
            runtime_id="docker",
            display_name=display_name,
            cli_name="docker",
            supports_oci=True,
            supports_internal_networks=True,
            supports_host_network=True,
            version=version,
            desktop_version=desktop_version,
            daemon_reachable=True,
            sandbox_available=sandbox_available,
        )
