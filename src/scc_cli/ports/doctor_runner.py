"""Doctor runner port definition."""

from __future__ import annotations

from typing import Protocol

from scc_cli.doctor.types import DoctorResult


class DoctorRunner(Protocol):
    """Run doctor checks via injected adapter."""

    def run(self, workspace: str | None = None) -> DoctorResult:
        """Return doctor results for an optional workspace."""
