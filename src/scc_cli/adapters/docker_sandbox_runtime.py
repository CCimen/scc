"""Docker sandbox runtime adapter for SandboxRuntime port."""

from __future__ import annotations

from typing import Any

from scc_cli import docker
from scc_cli.core.enums import NetworkPolicy
from scc_cli.core.errors import (
    DockerDaemonNotRunningError,
    DockerNotFoundError,
    DockerVersionError,
    SandboxNotAvailableError,
)
from scc_cli.core.network_policy import collect_proxy_env
from scc_cli.docker.core import MIN_DOCKER_VERSION, _parse_version
from scc_cli.ports.models import (
    SandboxConflict,
    SandboxHandle,
    SandboxSpec,
    SandboxState,
    SandboxStatus,
)
from scc_cli.ports.runtime_probe import RuntimeProbe
from scc_cli.ports.sandbox_runtime import SandboxRuntime


def _extract_container_name(cmd: list[str]) -> str | None:
    for idx, arg in enumerate(cmd):
        if arg == "--name" and idx + 1 < len(cmd):
            return cmd[idx + 1]
        if arg.startswith("--name="):
            return arg.split("=", 1)[1]
    if cmd and cmd[-1].startswith("scc-"):
        return cmd[-1]
    return None


class DockerSandboxRuntime(SandboxRuntime):
    """SandboxRuntime backed by Docker sandbox CLI."""

    def __init__(self, probe: RuntimeProbe) -> None:
        self._probe = probe

    def ensure_available(self) -> None:
        """Ensure the Docker runtime is available and ready for sandbox use.

        Uses RuntimeProbe to detect capabilities, then raises the same
        exception types as the old docker.check_docker_available() path.
        """
        info = self._probe.probe()

        # Docker not installed: no CLI found, no version info
        if not info.daemon_reachable and not info.cli_name:
            raise DockerNotFoundError()
        if not info.daemon_reachable and info.version is None:
            raise DockerNotFoundError()

        # Docker installed but daemon not running
        if not info.daemon_reachable:
            raise DockerDaemonNotRunningError()

        # Desktop version too old
        if info.desktop_version:
            current = _parse_version(info.desktop_version)
            required = _parse_version(MIN_DOCKER_VERSION)
            if current < required:
                raise DockerVersionError(current_version=info.desktop_version)

        # Sandbox feature not available
        if not info.sandbox_available:
            raise SandboxNotAvailableError()

    def run(self, spec: SandboxSpec) -> SandboxHandle:
        docker.prepare_sandbox_volume_for_credentials()
        env_vars = dict(spec.env) if spec.env else {}
        if spec.network_policy == NetworkPolicy.WEB_EGRESS_ENFORCED.value:
            for key, value in collect_proxy_env().items():
                env_vars.setdefault(key, value)
        runtime_env = env_vars or None
        docker_cmd, _is_resume = docker.get_or_create_container(
            workspace=spec.workspace_mount.source,
            branch=None,
            profile=None,
            force_new=spec.force_new,
            continue_session=spec.continue_session,
            env_vars=runtime_env,
        )
        container_name = _extract_container_name(docker_cmd)
        # Legacy Desktop sandbox path: expects a dict (Claude JSON only).
        # Deserialize rendered_bytes back to dict for backward compat.
        plugin_settings: dict[str, Any] | None = None
        if spec.agent_settings is not None:
            import json as _json

            plugin_settings = _json.loads(spec.agent_settings.rendered_bytes)
        docker.run(
            docker_cmd,
            org_config=spec.org_config,
            container_workdir=spec.workdir,
            plugin_settings=plugin_settings,
            env_vars=runtime_env,
        )
        return SandboxHandle(
            sandbox_id=container_name or "sandbox",
            name=container_name,
        )

    def detect_launch_conflict(self, spec: SandboxSpec) -> SandboxConflict | None:
        # Legacy Docker Desktop sandboxes already encapsulate their own
        # container reuse semantics.  M008 can add richer conflict inspection
        # here if the Desktop path remains active.
        return None

    def resume(self, handle: SandboxHandle) -> None:
        docker.resume_container(handle.sandbox_id)

    def stop(self, handle: SandboxHandle) -> None:
        docker.stop_container(handle.sandbox_id)

    def remove(self, handle: SandboxHandle) -> None:
        docker.remove_container(handle.sandbox_id, force=True)

    def list_running(self) -> list[SandboxHandle]:
        return [
            SandboxHandle(sandbox_id=container.id, name=container.name)
            for container in docker.list_running_sandboxes()
        ]

    def status(self, handle: SandboxHandle) -> SandboxStatus:
        status = docker.get_container_status(handle.sandbox_id)
        if not status:
            return SandboxStatus(state=SandboxState.UNKNOWN)
        normalized = status.lower()
        if "up" in normalized or "running" in normalized:
            state = SandboxState.RUNNING
        elif "exited" in normalized or "stopped" in normalized:
            state = SandboxState.STOPPED
        else:
            state = SandboxState.UNKNOWN
        return SandboxStatus(state=state)
