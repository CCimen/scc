"""JSON mapping helpers for support bundle output."""

from __future__ import annotations

from typing import Any

from ...json_output import build_envelope
from ...kinds import Kind


def build_support_bundle_envelope(bundle_data: dict[str, Any]) -> dict[str, Any]:
    """Build the JSON envelope for support bundle output.

    Invariants:
        - Keep `Kind.SUPPORT_BUNDLE` stable.
        - Preserve bundle manifest keys.

    Args:
        bundle_data: Support bundle manifest data.

    Returns:
        JSON envelope for the support bundle manifest.
    """
    return build_envelope(Kind.SUPPORT_BUNDLE, data=bundle_data)
