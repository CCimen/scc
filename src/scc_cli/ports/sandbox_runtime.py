"""Sandbox runtime port definition."""

from __future__ import annotations

from typing import Protocol

from scc_cli.ports.models import SandboxHandle, SandboxSpec, SandboxStatus


class SandboxRuntime(Protocol):
    """Abstract sandbox runtime operations."""

    def ensure_available(self) -> None:
        """Ensure the runtime is available and ready for use."""

    def run(self, spec: SandboxSpec) -> SandboxHandle:
        """Launch a sandbox session for the given spec."""

    def resume(self, handle: SandboxHandle) -> None:
        """Resume a stopped sandbox session."""

    def stop(self, handle: SandboxHandle) -> None:
        """Stop a running sandbox session."""

    def remove(self, handle: SandboxHandle) -> None:
        """Remove a sandbox session."""

    def list_running(self) -> list[SandboxHandle]:
        """List running sandbox sessions."""

    def status(self, handle: SandboxHandle) -> SandboxStatus:
        """Return status details for a sandbox session."""
