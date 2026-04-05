"""Plain OCI sandbox runtime adapter for SandboxRuntime port.

Uses standard ``docker create`` / ``docker start`` / ``docker exec``
commands instead of Docker Desktop's ``docker sandbox run``, making SCC
work on Docker Engine, OrbStack, Colima, and any OCI-compatible runtime.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from scc_cli.adapters.egress_topology import NetworkTopologyManager
from scc_cli.core.destination_registry import destination_sets_to_allow_rules
from scc_cli.core.egress_policy import build_egress_plan, compile_squid_acl
from scc_cli.core.enums import NetworkPolicy
from scc_cli.core.errors import (
    DockerDaemonNotRunningError,
    DockerNotFoundError,
    SandboxLaunchError,
)
from scc_cli.core.network_policy import collect_proxy_env
from scc_cli.ports.models import (
    SandboxHandle,
    SandboxSpec,
    SandboxState,
    SandboxStatus,
)
from scc_cli.ports.runtime_probe import RuntimeProbe

# Timeouts for subprocess calls (seconds)
_CREATE_TIMEOUT = 60
_START_TIMEOUT = 30
_INSPECT_TIMEOUT = 10
_DEFAULT_TIMEOUT = 15

# Label used to identify OCI-backend containers
_OCI_LABEL = "scc.backend=oci"

# Claude-specific defaults for OCI sandbox runtime
_CLAUDE_AGENT_NAME = "claude"
_CLAUDE_DATA_VOLUME = "docker-claude-sandbox-data"

# Agent home inside the container
_AGENT_HOME = "/home/agent"


def _container_name(workspace: Path, provider_id: str = "") -> str:
    """Derive a deterministic container name from a workspace path and provider.

    When ``provider_id`` is non-empty the hash input changes, producing a
    different container name per provider for the same workspace.  This
    prevents coexistence collisions when two providers target the same
    directory.
    """
    hash_input = f"{provider_id}:{workspace}" if provider_id else str(workspace)
    digest = hashlib.sha256(hash_input.encode()).hexdigest()[:12]
    return f"scc-oci-{digest}"


def _run_docker(
    args: list[str],
    *,
    timeout: int = _DEFAULT_TIMEOUT,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a ``docker`` subprocess with standard error handling.

    Raises:
        SandboxLaunchError: on non-zero exit or timeout.
    """
    cmd = ["docker", *args]
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=check,
        )
    except subprocess.TimeoutExpired as exc:
        raise SandboxLaunchError(
            user_message=f"Docker command timed out after {timeout}s",
            command=" ".join(cmd),
            stderr=str(exc),
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise SandboxLaunchError(
            user_message="Docker command failed",
            command=" ".join(cmd),
            stderr=exc.stderr or "",
        ) from exc


class OciSandboxRuntime:
    """SandboxRuntime backed by plain OCI container commands.

    Unlike :class:`DockerSandboxRuntime`, this adapter:

    * Does **not** require Docker Desktop's sandbox feature.
    * Actually consumes ``spec.image`` for the container image.
    * Uses volume mounts at container creation time for credential
      persistence instead of Desktop's symlink pattern.
    """

    def __init__(self, probe: RuntimeProbe) -> None:
        self._probe = probe
        self._topology: NetworkTopologyManager | None = None

    # ── SandboxRuntime protocol ──────────────────────────────────────────

    def ensure_available(self) -> None:
        """Probe the runtime and raise if OCI container support is missing."""
        info = self._probe.probe()

        if info.version is None and not info.daemon_reachable:
            raise DockerNotFoundError()

        if not info.daemon_reachable:
            raise DockerDaemonNotRunningError()

        if not info.supports_oci:
            raise DockerNotFoundError(
                user_message="Docker runtime does not support OCI containers",
                suggested_action=(
                    "Install Docker Engine, OrbStack, Colima, or another "
                    "OCI-compatible container runtime"
                ),
            )

    def run(self, spec: SandboxSpec) -> SandboxHandle:
        """Create, start, and exec into an OCI container.

        The method replaces the current process via :func:`os.execvp` for
        the final ``docker exec`` call, so it **does not return** in normal
        operation.  The :class:`SandboxHandle` return is provided for the
        protocol signature and for testing with a mocked ``os.execvp``.
        """
        container_name = _container_name(spec.workspace_mount.source, spec.provider_id)

        # -- Set up egress topology for enforced mode ----------------------
        network_name: str | None = None
        proxy_env: dict[str, str] = {}

        if spec.network_policy == NetworkPolicy.WEB_EGRESS_ENFORCED.value:
            allow_rules = destination_sets_to_allow_rules(spec.destination_sets)
            plan = build_egress_plan(
                NetworkPolicy.WEB_EGRESS_ENFORCED,
                destination_sets=spec.destination_sets,
                egress_rules=allow_rules,
            )
            acl_config = compile_squid_acl(plan)
            self._topology = NetworkTopologyManager(session_id=container_name)
            topo_info = self._topology.setup(acl_config)
            network_name = topo_info.network_name
            proxy_env = {
                "HTTP_PROXY": topo_info.proxy_endpoint,
                "HTTPS_PROXY": topo_info.proxy_endpoint,
                "NO_PROXY": "",
            }
            # Also forward host proxy env for parity with DockerSandboxRuntime
            proxy_env.update(collect_proxy_env())

        # -- Build docker create command ------------------------------------
        create_cmd = self._build_create_cmd(
            spec, container_name, network_name=network_name, proxy_env=proxy_env,
        )
        result = _run_docker(create_cmd, timeout=_CREATE_TIMEOUT)
        container_id = result.stdout.strip()

        # -- Start the container -------------------------------------------
        _run_docker(["start", container_id], timeout=_START_TIMEOUT)

        # -- Inject agent settings via docker cp if needed -----------------
        if spec.agent_settings is not None:
            self._inject_settings(container_id, spec)

        # -- Build docker exec command and hand off ------------------------
        exec_cmd = self._build_exec_cmd(spec, container_id)
        os.execvp("docker", ["docker", *exec_cmd])

        # execvp replaces the process; the lines below execute only when
        # os.execvp is mocked in tests.
        return SandboxHandle(sandbox_id=container_id, name=container_name)

    def resume(self, handle: SandboxHandle) -> None:
        """Start a previously stopped container."""
        _run_docker(["start", handle.sandbox_id], timeout=_START_TIMEOUT)

    def stop(self, handle: SandboxHandle) -> None:
        """Stop a running container."""
        _run_docker(["stop", handle.sandbox_id], timeout=_DEFAULT_TIMEOUT)
        self._teardown_topology()

    def remove(self, handle: SandboxHandle) -> None:
        """Force-remove a container."""
        _run_docker(["rm", "-f", handle.sandbox_id], timeout=_DEFAULT_TIMEOUT)
        self._teardown_topology()

    def list_running(self) -> list[SandboxHandle]:
        """List containers started by this backend."""
        result = _run_docker(
            [
                "ps",
                "--filter",
                f"label={_OCI_LABEL}",
                "--format",
                "{{.ID}}\t{{.Names}}",
            ],
            timeout=_DEFAULT_TIMEOUT,
        )
        handles: list[SandboxHandle] = []
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            parts = line.split("\t", 1)
            cid = parts[0].strip()
            cname = parts[1].strip() if len(parts) > 1 else None
            handles.append(SandboxHandle(sandbox_id=cid, name=cname))
        return handles

    def status(self, handle: SandboxHandle) -> SandboxStatus:
        """Inspect container state and map to SandboxState."""
        try:
            result = subprocess.run(
                [
                    "docker",
                    "inspect",
                    "--format",
                    "{{.State.Status}}",
                    handle.sandbox_id,
                ],
                capture_output=True,
                text=True,
                timeout=_INSPECT_TIMEOUT,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return SandboxStatus(state=SandboxState.UNKNOWN)

        if result.returncode != 0:
            return SandboxStatus(state=SandboxState.UNKNOWN)

        raw = result.stdout.strip().lower()
        state_map: dict[str, SandboxState] = {
            "created": SandboxState.CREATED,
            "running": SandboxState.RUNNING,
            "exited": SandboxState.STOPPED,
            "dead": SandboxState.STOPPED,
            "paused": SandboxState.RUNNING,
            "restarting": SandboxState.RUNNING,
        }
        return SandboxStatus(state=state_map.get(raw, SandboxState.UNKNOWN))

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _build_create_cmd(
        spec: SandboxSpec,
        container_name: str,
        *,
        network_name: str | None = None,
        proxy_env: dict[str, str] | None = None,
    ) -> list[str]:
        """Assemble the ``docker create`` argument list."""
        # Resolve data volume and config dir, falling back to Claude defaults.
        volume_name = spec.data_volume if spec.data_volume else _CLAUDE_DATA_VOLUME
        config_dirname = spec.config_dir if spec.config_dir else ".claude"

        cmd: list[str] = [
            "create",
            "--name",
            container_name,
            # Workspace mount
            "-v",
            f"{spec.workspace_mount.source}:{spec.workspace_mount.target}",
            # Credential volume mount
            "-v",
            f"{volume_name}:{_AGENT_HOME}/{config_dirname}",
            # Working directory
            "-w",
            str(spec.workdir),
            # OCI-backend label
            "--label",
            _OCI_LABEL,
        ]

        # -- Network policy enforcement -----------------------------------
        if spec.network_policy == NetworkPolicy.LOCKED_DOWN_WEB.value:
            cmd.extend(["--network", "none"])
        elif network_name is not None:
            cmd.extend(["--network", network_name])

        # Environment variables
        for key, value in spec.env.items():
            cmd.extend(["-e", f"{key}={value}"])

        # Proxy env vars for enforced egress mode
        if proxy_env:
            for key, value in proxy_env.items():
                cmd.extend(["-e", f"{key}={value}"])

        # Extra mounts
        for mount in spec.extra_mounts:
            mount_str = f"{mount.source}:{mount.target}"
            if mount.read_only:
                mount_str += ":ro"
            cmd.extend(["-v", mount_str])

        # Image — this is the key difference from DockerSandboxRuntime
        cmd.append(spec.image)

        # Keep container alive with a blocking entrypoint
        cmd.extend(["/bin/bash", "-c", "sleep infinity"])

        return cmd

    def _teardown_topology(self) -> None:
        """Tear down egress topology if one was set up."""
        if self._topology is not None:
            self._topology.teardown()
            self._topology = None

    @staticmethod
    def _build_exec_cmd(spec: SandboxSpec, container_id: str) -> list[str]:
        """Assemble the ``docker exec`` argument list."""
        cmd: list[str] = [
            "exec",
            "-it",
            "-w",
            str(spec.workdir),
            container_id,
        ]

        if spec.agent_argv:
            cmd.extend(list(spec.agent_argv))
        else:
            cmd.extend([_CLAUDE_AGENT_NAME, "--dangerously-skip-permissions"])

        if spec.continue_session:
            cmd.append("-c")

        return cmd

    @staticmethod
    def _inject_settings(container_id: str, spec: SandboxSpec) -> None:
        """Write agent settings into the container via ``docker cp``."""
        if spec.agent_settings is None:
            return  # pragma: no cover

        settings_json = json.dumps(spec.agent_settings.content)
        target_path = str(spec.agent_settings.path)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as tmp:
            tmp.write(settings_json)
            tmp_path = tmp.name

        try:
            _run_docker(
                ["cp", tmp_path, f"{container_id}:{target_path}"],
                timeout=_DEFAULT_TIMEOUT,
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)
