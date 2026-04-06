"""JSON mapping helpers for launch-audit support output."""

from __future__ import annotations

from ...application.launch.audit_log import LaunchAuditDiagnostics
from ...json_output import build_envelope
from ...kinds import Kind


def build_launch_audit_envelope(diagnostics: LaunchAuditDiagnostics) -> dict[str, object]:
    """Build the JSON envelope for launch-audit support output."""
    return build_envelope(Kind.LAUNCH_AUDIT, data=diagnostics.to_dict())
