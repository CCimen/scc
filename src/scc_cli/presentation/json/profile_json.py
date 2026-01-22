"""JSON mapping helpers for personal profile operations."""

from __future__ import annotations

from typing import Any

from scc_cli.application.launch import ApplyPersonalProfileResult
from scc_cli.application.personal_profile_policy import ProfilePolicySkip
from scc_cli.json_output import build_envelope
from scc_cli.kinds import Kind


def _serialize_policy_skips(skips: list[ProfilePolicySkip]) -> list[dict[str, str]]:
    return [
        {"item": skip.item, "reason": skip.reason, "target_type": skip.target_type}
        for skip in skips
    ]


def build_profile_apply_envelope(
    result: ApplyPersonalProfileResult,
) -> dict[str, Any]:
    """Build JSON envelope for personal profile apply events."""
    data = {
        "profile_id": result.profile_id,
        "applied": result.applied,
        "skipped_items": _serialize_policy_skips(result.skipped_items),
    }
    return build_envelope(Kind.PROFILE_APPLY, data=data)
