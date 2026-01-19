"""Local adapter for running doctor checks."""

from __future__ import annotations

from pathlib import Path

from scc_cli.doctor.core import run_doctor
from scc_cli.doctor.types import DoctorResult
from scc_cli.ports.doctor_runner import DoctorRunner


class LocalDoctorRunner(DoctorRunner):
    """Adapter that executes doctor checks locally."""

    def run(self, workspace: str | None = None) -> DoctorResult:
        workspace_path = Path(workspace) if workspace else None
        return run_doctor(workspace_path)
