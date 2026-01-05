"""Quick Resume gating and filtering.

Centralizes Quick Resume logic to prevent drift between entry points.

Policy (explicit):
- Show QR only if:
  - Interactive allowed (TTY, not --json, not --non-interactive)
  - None of --resume, --select, --fresh set
  - If --interactive is set => wizard only, NO QR (force wizard bypasses QR)
  - Sessions exist for WR

- QR selection list filtering:
  - Filter by workspace_root == WR (only sessions for this workspace)
  - AND team scoping: --team X shows only team X; standalone shows only team=None
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from scc_cli.contexts import WorkContext


def should_show_quick_resume(
    *,
    json_mode: bool = False,
    non_interactive: bool = False,
    resume: bool = False,
    select: bool = False,
    fresh: bool = False,
    interactive_flag: bool = False,
) -> bool:
    """Determine if Quick Resume picker should be shown.

    Returns False if any bypass condition is met.

    Args:
        json_mode: --json flag set
        non_interactive: --non-interactive flag set
        resume: --resume flag set
        select: --select flag set
        fresh: --fresh flag set
        interactive_flag: --interactive flag set (forces wizard, bypasses QR)

    Returns:
        True if QR should be shown, False otherwise
    """
    # Non-interactive modes never show QR
    if json_mode or non_interactive:
        return False

    # Explicit flags bypass QR
    if resume or select or fresh:
        return False

    # --interactive forces wizard, bypasses QR
    if interactive_flag:
        return False

    return True


def load_contexts_for_workspace_and_team(
    workspace_root: Path,
    team: str | None,
    limit: int = 10,
) -> list[WorkContext]:
    """Load contexts filtered by workspace and team.

    Args:
        workspace_root: Only return contexts matching this workspace
        team: Team filter:
            - None: return only standalone contexts (team=None)
            - str: return only contexts matching this team
        limit: Maximum number of contexts to return

    Returns:
        List of WorkContext objects matching filters
    """
    from scc_cli.contexts import load_recent_contexts

    # Load all recent contexts
    all_contexts = load_recent_contexts(limit=limit * 3)  # Load extra for filtering

    filtered = []
    for ctx in all_contexts:
        # Filter by workspace
        ctx_workspace = Path(ctx.repo_root) if ctx.repo_root else None
        if ctx_workspace is None:
            continue

        # Resolve both paths for comparison
        try:
            if ctx_workspace.resolve() != workspace_root.resolve():
                continue
        except OSError:
            continue

        # Filter by team
        if team is None:
            # Standalone mode: only show contexts with no team
            if ctx.team is not None:
                continue
        else:
            # Team mode: only show contexts matching this team
            if ctx.team != team:
                continue

        filtered.append(ctx)

        if len(filtered) >= limit:
            break

    return filtered
