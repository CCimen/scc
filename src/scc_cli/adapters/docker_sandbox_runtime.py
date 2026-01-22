"""Docker sandbox runtime adapter for SandboxRuntime port."""

from __future__ import annotations

from scc_cli import docker
from scc_cli.core.enums import NetworkPolicy
from scc_cli.core.network_policy import collect_proxy_env
from scc_cli.ports.models import SandboxHandle, SandboxSpec, SandboxState, SandboxStatus
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

    def ensure_available(self) -> None:
        docker.check_docker_available()

    def run(self, spec: SandboxSpec) -> SandboxHandle:
        docker.prepare_sandbox_volume_for_credentials()
        env_vars = dict(spec.env) if spec.env else {}
        if spec.network_policy == NetworkPolicy.CORP_PROXY_ONLY.value:
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
        plugin_settings = spec.agent_settings.content if spec.agent_settings else None
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
