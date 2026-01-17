"""JSON mapping helpers for launch/start flows."""

from __future__ import annotations

from typing import Any

from ...json_output import build_envelope
from ...kinds import Kind


def build_start_dry_run_envelope(dry_run_data: dict[str, Any]) -> dict[str, Any]:
    """Build the JSON envelope for `scc start --dry-run` output.

    Invariants:
        - Keep `Kind.START_DRY_RUN` stable.
        - Preserve dry-run data keys for downstream tooling.

    Args:
        dry_run_data: Precomputed dry-run data payload.

    Returns:
        JSON envelope for the dry-run preview.
    """
    return build_envelope(Kind.START_DRY_RUN, data=dry_run_data)
