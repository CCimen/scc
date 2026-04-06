"""Sandbox runtime port definition."""

from __future__ import annotations

from typing import Protocol

from scc_cli.ports.models import SandboxConflict, SandboxHandle, SandboxSpec, SandboxStatus


class SandboxRuntime(Protocol):
    """Abstract sandbox runtime operations."""

    def ensure_available(self) -> None:
        """Ensure the runtime is available and ready for use."""
        ...

    def run(self, spec: SandboxSpec) -> SandboxHandle:
        """Launch a sandbox session for the given spec."""
        ...

    def detect_launch_conflict(self, spec: SandboxSpec) -> SandboxConflict | None:
        """Return an existing live conflict for *spec*, if one exists.

        Runtimes should return ``None`` when the requested launch can proceed
        without user intervention.  Typical examples:
        - no prior sandbox exists
        - a stale/stopped sandbox can be auto-replaced safely
        - ``spec.force_new`` already requests replacement

        The command/UI layer owns how interactive users resolve a conflict.
        """
        ...

    def resume(self, handle: SandboxHandle) -> None:
        """Resume a stopped sandbox session."""
        ...

    def stop(self, handle: SandboxHandle) -> None:
        """Stop a running sandbox session."""
        ...

    def remove(self, handle: SandboxHandle) -> None:
        """Remove a sandbox session."""
        ...

    def list_running(self) -> list[SandboxHandle]:
        """List running sandbox sessions."""
        ...

    def status(self, handle: SandboxHandle) -> SandboxStatus:
        """Return status details for a sandbox session."""
        ...
