"""Fake SandboxRuntime for contract tests."""

from __future__ import annotations

from dataclasses import dataclass

from scc_cli.ports.models import SandboxHandle, SandboxSpec, SandboxState, SandboxStatus


@dataclass
class _SandboxRecord:
    handle: SandboxHandle
    status: SandboxStatus


class FakeSandboxRuntime:
    """In-memory sandbox runtime for tests."""

    def __init__(self) -> None:
        self._records: dict[str, _SandboxRecord] = {}
        self._counter = 0

    def ensure_available(self) -> None:
        return None

    def run(self, spec: SandboxSpec) -> SandboxHandle:
        self._counter += 1
        handle = SandboxHandle(sandbox_id=f"sandbox-{self._counter}")
        status = SandboxStatus(state=SandboxState.RUNNING)
        self._records[handle.sandbox_id] = _SandboxRecord(handle=handle, status=status)
        return handle

    def resume(self, handle: SandboxHandle) -> None:
        record = self._records.get(handle.sandbox_id)
        if record:
            record.status = SandboxStatus(state=SandboxState.RUNNING)

    def stop(self, handle: SandboxHandle) -> None:
        record = self._records.get(handle.sandbox_id)
        if record:
            record.status = SandboxStatus(state=SandboxState.STOPPED)

    def remove(self, handle: SandboxHandle) -> None:
        self._records.pop(handle.sandbox_id, None)

    def list_running(self) -> list[SandboxHandle]:
        return [
            record.handle
            for record in self._records.values()
            if record.status.state == SandboxState.RUNNING
        ]

    def status(self, handle: SandboxHandle) -> SandboxStatus:
        record = self._records.get(handle.sandbox_id)
        if record:
            return record.status
        return SandboxStatus(state=SandboxState.UNKNOWN)
