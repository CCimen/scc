"""Opt-in smoke tests against a real Docker daemon.

These tests are skipped by default. They exist to prove runtime/devcontainer
claims on machines that intentionally opt into live Docker checks.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from scc_cli.adapters.oci_sandbox_runtime import OciSandboxRuntime
from scc_cli.application.dev_environment_bridge import (
    DEV_ENVIRONMENT_HEALTH_CHECK_ACTION,
    DEV_ENVIRONMENT_LOG_ACTION,
    RunDevEnvironmentCommandDependencies,
    RunDevEnvironmentCommandRequest,
    run_dev_environment_command,
)
from scc_cli.application.effective_config_models import DevEnvironmentCommand, EffectiveConfig
from scc_cli.core.enums import NetworkPolicy
from scc_cli.core.runtime_mounts import WORKSPACE_PATH_MAP_ENV, resolve_runtime_mount_source
from scc_cli.ports.models import MountSpec, SandboxSpec
from scc_cli.services.dev_environment_command_runner import run_subprocess_bounded
from tests.fakes import FakeAuditEventSink

_DEFAULT_IMAGE = "scc-agent-claude:latest"
_SMOKE_ENV = "SCC_REAL_RUNTIME_SMOKE"
_IMAGE_ENV = "SCC_REAL_RUNTIME_IMAGE"

pytestmark = [
    pytest.mark.real_runtime,
    pytest.mark.skipif(
        os.environ.get(_SMOKE_ENV) != "1",
        reason=f"Set {_SMOKE_ENV}=1 to run real Docker smoke tests.",
    ),
]


def _docker(
    args: list[str],
    *,
    timeout: int = 30,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
    )


def _docker_run_shell(
    image: str,
    command: str,
    *,
    run_args: list[str] | None = None,
    timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
    args = ["run", "--rm"]
    if run_args:
        args.extend(run_args)
    args.extend(["--entrypoint", "sh", image, "-c", command])
    return _docker(args, timeout=timeout)


def _require_smoke_image() -> str:
    image = os.environ.get(_IMAGE_ENV, _DEFAULT_IMAGE)
    try:
        _docker(["info"], timeout=10)
    except FileNotFoundError:
        pytest.skip("docker CLI is not installed")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        pytest.skip(f"Docker daemon is not reachable: {exc}")

    try:
        _docker(["image", "inspect", image], timeout=10)
    except subprocess.CalledProcessError:
        pytest.skip(f"Docker image {image!r} is not available locally")
    except subprocess.TimeoutExpired as exc:
        pytest.skip(f"Docker image inspect timed out: {exc}")

    try:
        _docker_run_shell(image, "true", timeout=20)
    except subprocess.CalledProcessError:
        pytest.skip(f"Docker image {image!r} does not provide a POSIX shell")
    except subprocess.TimeoutExpired as exc:
        pytest.skip(f"Docker shell smoke timed out: {exc}")

    return image


def test_real_docker_accepts_devcontainer_path_map_mount(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = _require_smoke_image()
    logical_workspace = Path("/workspaces/scc-smoke")
    (tmp_path / "marker.txt").write_text("ok", encoding="utf-8")
    monkeypatch.setenv(WORKSPACE_PATH_MAP_ENV, f"{logical_workspace}:{tmp_path}")

    runtime_mount_source = resolve_runtime_mount_source(logical_workspace)

    assert runtime_mount_source == tmp_path
    result = _docker_run_shell(
        image,
        "test -f marker.txt && pwd",
        run_args=[
            "-v",
            f"{runtime_mount_source}:{logical_workspace}:ro",
            "-w",
            str(logical_workspace),
        ],
        timeout=30,
    )
    assert result.stdout.strip() == str(logical_workspace)


def test_real_docker_create_accepts_locked_down_network_with_mapped_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = _require_smoke_image()
    logical_workspace = Path("/workspaces/scc-smoke")
    monkeypatch.setenv(WORKSPACE_PATH_MAP_ENV, f"{logical_workspace}:{tmp_path}")
    runtime_mount_source = resolve_runtime_mount_source(logical_workspace)
    container_name = f"scc-smoke-{uuid4().hex[:12]}"
    spec = SandboxSpec(
        image=image,
        workspace_mount=MountSpec(source=runtime_mount_source, target=logical_workspace),
        workdir=logical_workspace,
        network_policy=NetworkPolicy.LOCKED_DOWN_WEB.value,
    )

    try:
        create_result = _docker(
            OciSandboxRuntime._build_create_cmd(spec, container_name),
            timeout=30,
        )
        container_id = create_result.stdout.strip()
        inspect_result = _docker(
            [
                "inspect",
                "--format",
                "{{.HostConfig.NetworkMode}}|{{range .Mounts}}{{.Source}}>{{.Destination}}{{end}}",
                container_id,
            ],
            timeout=10,
        )
    finally:
        _docker(["rm", "-f", container_name], timeout=15, check=False)

    inspect_output = inspect_result.stdout.strip()
    assert inspect_output.startswith("none|")
    assert f"{runtime_mount_source}>{logical_workspace}" in inspect_output


def test_real_docker_bridge_reads_service_logs_and_health(tmp_path: Path) -> None:
    image = _require_smoke_image()
    container_name = f"scc-bridge-smoke-{uuid4().hex[:12]}"
    try:
        _docker(
            [
                "run",
                "-d",
                "--name",
                container_name,
                "--entrypoint",
                "sh",
                image,
                "-c",
                "printf bridge-ready; sleep 30",
            ],
            timeout=30,
        )
        effective = EffectiveConfig(
            dev_environment_logs=[
                DevEnvironmentCommand(
                    name="service",
                    argv=("docker", "logs", container_name),
                    timeout_seconds=10,
                )
            ],
            dev_environment_health_checks=[
                DevEnvironmentCommand(
                    name="service",
                    argv=(
                        "docker",
                        "inspect",
                        "-f",
                        "{{.State.Running}}",
                        container_name,
                    ),
                    timeout_seconds=10,
                )
            ],
        )
        sink = FakeAuditEventSink()

        logs = run_dev_environment_command(
            RunDevEnvironmentCommandRequest(
                command_name="service",
                workspace_path=tmp_path,
                effective_config=effective,
                team_name="platform",
                team_source="test",
                action_type=DEV_ENVIRONMENT_LOG_ACTION,
            ),
            dependencies=RunDevEnvironmentCommandDependencies(
                audit_sink=sink,
                command_runner=run_subprocess_bounded,
            ),
        )
        health = run_dev_environment_command(
            RunDevEnvironmentCommandRequest(
                command_name="service",
                workspace_path=tmp_path,
                effective_config=effective,
                team_name="platform",
                team_source="test",
                action_type=DEV_ENVIRONMENT_HEALTH_CHECK_ACTION,
            ),
            dependencies=RunDevEnvironmentCommandDependencies(
                audit_sink=sink,
                command_runner=run_subprocess_bounded,
            ),
        )
    finally:
        _docker(["rm", "-f", container_name], timeout=15, check=False)

    assert logs.status == "succeeded"
    assert "bridge-ready" in logs.stdout.tail
    assert health.status == "succeeded"
    assert health.stdout.tail.strip() == "true"
    assert [event.event_type for event in sink.events] == [
        "dev_environment.log.started",
        "dev_environment.log.succeeded",
        "dev_environment.health_check.started",
        "dev_environment.health_check.succeeded",
    ]
