"""JSON mapping helpers for worktree flows."""

from __future__ import annotations

from typing import Any

from ...json_output import build_envelope
from ...kinds import Kind


def build_worktree_list_data(worktrees: list[dict[str, Any]], workspace: str) -> dict[str, Any]:
    """Build JSON-ready worktree list data.

    Invariants:
        - Preserve keys: `worktrees`, `count`, and `workspace`.

    Args:
        worktrees: Serialized worktree dictionaries.
        workspace: Workspace path as a string.

    Returns:
        Dictionary payload for the worktree list envelope.
    """
    return {
        "worktrees": worktrees,
        "count": len(worktrees),
        "workspace": workspace,
    }


def build_worktree_list_envelope(data: dict[str, Any]) -> dict[str, Any]:
    """Build the JSON envelope for worktree list output.

    Invariants:
        - Keep `Kind.WORKTREE_LIST` stable.

    Args:
        data: Worktree list data payload.

    Returns:
        JSON envelope for the worktree list.
    """
    return build_envelope(Kind.WORKTREE_LIST, data=data)
