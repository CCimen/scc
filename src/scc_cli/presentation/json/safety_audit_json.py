"""JSON mapping helpers for safety-audit support output."""

from __future__ import annotations

from ...application.safety_audit import SafetyAuditDiagnostics
from ...json_output import build_envelope
from ...kinds import Kind


def build_safety_audit_envelope(diagnostics: SafetyAuditDiagnostics) -> dict[str, object]:
    """Build the JSON envelope for safety-audit support output."""
    return build_envelope(Kind.SAFETY_AUDIT, data=diagnostics.to_dict())
