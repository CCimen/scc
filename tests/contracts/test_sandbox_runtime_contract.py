"""Contract tests for SandboxRuntime implementations."""

from __future__ import annotations

from pathlib import Path

from scc_cli.ports.models import MountSpec, SandboxSpec, SandboxState
from tests.fakes.fake_sandbox_runtime import FakeSandboxRuntime


def _make_spec(tmp_path: Path) -> SandboxSpec:
    mount = MountSpec(source=tmp_path, target=tmp_path)
    return SandboxSpec(image="sandbox-image", workspace_mount=mount, workdir=tmp_path)


def test_sandbox_runtime_lifecycle(tmp_path: Path) -> None:
    runtime = FakeSandboxRuntime()
    spec = _make_spec(tmp_path)

    handle = runtime.run(spec)

    assert runtime.status(handle).state == SandboxState.RUNNING
    assert runtime.list_running() == [handle]

    runtime.stop(handle)
    assert runtime.status(handle).state == SandboxState.STOPPED
    assert runtime.list_running() == []

    runtime.resume(handle)
    assert runtime.status(handle).state == SandboxState.RUNNING
    assert runtime.list_running() == [handle]

    runtime.remove(handle)
    assert runtime.status(handle).state == SandboxState.UNKNOWN
    assert runtime.list_running() == []
