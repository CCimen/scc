"""JSON mapping helpers for session flows."""

from __future__ import annotations

from typing import Any

from ...json_output import build_envelope
from ...kinds import Kind


def build_session_list_data(
    sessions: list[dict[str, Any]],
    *,
    team: str | None = None,
) -> dict[str, Any]:
    """Build JSON-ready session list data.

    Invariants:
        - Preserve keys: `sessions`, `count`, and `team`.

    Args:
        sessions: Serialized session dictionaries.
        team: Optional team filter label.

    Returns:
        Dictionary payload for session list output.
    """
    return {
        "sessions": sessions,
        "count": len(sessions),
        "team": team,
    }


def build_session_list_envelope(data: dict[str, Any]) -> dict[str, Any]:
    """Build the JSON envelope for session list output.

    Invariants:
        - Keep `Kind.SESSION_LIST` stable.

    Args:
        data: Session list data payload.

    Returns:
        JSON envelope for the session list.
    """
    return build_envelope(Kind.SESSION_LIST, data=data)
