"""
JSON envelope builder for CLI output.

Provide structured, versioned JSON envelopes for machine-readable output.
All JSON output MUST use this builder to ensure consistency.

Usage:
    from scc_cli.json_output import build_envelope
    from scc_cli.kinds import Kind

    envelope = build_envelope(Kind.TEAM_LIST, data={"teams": [...]})
"""

from datetime import datetime, timezone
from typing import Any

from . import __version__
from .kinds import Kind

# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

API_VERSION = "scc.cli/v1"


# ═══════════════════════════════════════════════════════════════════════════════
# Envelope Builder
# ═══════════════════════════════════════════════════════════════════════════════


def build_envelope(
    kind: Kind,
    *,
    data: dict[str, Any] | None = None,
    ok: bool = True,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Build a JSON envelope with standard structure.

    All JSON output follows this contract for consistency and parseability.

    Args:
        kind: The envelope kind (from Kind enum)
        data: The command-specific payload
        ok: Whether the operation was successful
        errors: List of error messages (sets ok=False if non-empty)
        warnings: List of warning messages

    Returns:
        A structured envelope dict ready for JSON serialization:
        {
            "apiVersion": "scc.cli/v1",
            "kind": "TeamList",
            "metadata": {
                "generatedAt": "2025-12-23T10:00:00Z",
                "cliVersion": "1.2.3"
            },
            "status": {
                "ok": true,
                "errors": [],
                "warnings": []
            },
            "data": { ... }
        }
    """
    # Normalize optional parameters
    if data is None:
        data = {}
    if errors is None:
        errors = []
    if warnings is None:
        warnings = []

    # If errors provided, ok should be False
    if errors and ok:
        ok = False

    # Generate ISO 8601 timestamp in UTC
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "apiVersion": API_VERSION,
        "kind": str(kind.value) if hasattr(kind, "value") else str(kind),
        "metadata": {
            "generatedAt": generated_at,
            "cliVersion": __version__,
        },
        "status": {
            "ok": ok,
            "errors": errors,
            "warnings": warnings,
        },
        "data": data,
    }
