from __future__ import annotations

from datetime import datetime, timedelta, timezone

from scc_cli import config, sessions
from scc_cli.ports.session_models import SessionRecord

from .backups import _create_backup
from .health_checks import _get_size
from .types import ResetResult, RiskTier


def prune_sessions(
    older_than_days: int = 30,
    keep_n: int = 20,
    team: str | None = None,
    dry_run: bool = False,
) -> ResetResult:
    """Prune old sessions while keeping recent ones.

    Risk: Tier 1 (Changes State) - Safe prune with defaults.

    Args:
        older_than_days: Remove sessions older than this (default: 30)
        keep_n: Keep at least this many recent sessions per team (default: 20)
        team: Only prune sessions for this team (None = all)
        dry_run: Preview only, don't actually delete
    """
    result = ResetResult(
        success=True,
        action_id="prune_sessions",
        risk_tier=RiskTier.CHANGES_STATE,
        paths=[config.SESSIONS_FILE],
        message=f"Pruned sessions older than {older_than_days}d (kept newest {keep_n} per team)",
    )

    try:
        store = sessions.get_session_store()
        with store.lock():
            all_sessions = store.load_sessions()
            original_count = len(all_sessions)

            if original_count == 0:
                result.message = "No sessions to prune"
                return result

            cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)

            by_team: dict[str | None, list[SessionRecord]] = {}
            for session in all_sessions:
                by_team.setdefault(session.team, []).append(session)

            kept_sessions: list[SessionRecord] = []
            for _team, team_sessions in by_team.items():
                team_sessions.sort(key=lambda s: s.last_used or "", reverse=True)

                kept = team_sessions[:keep_n]
                remaining = team_sessions[keep_n:]

                for session in remaining:
                    last_used = session.last_used or ""
                    if last_used:
                        try:
                            dt = datetime.fromisoformat(last_used.replace("Z", "+00:00"))
                            if dt > cutoff:
                                kept.append(session)
                        except (ValueError, TypeError):
                            pass

                kept_sessions.extend(kept)

            result.removed_count = original_count - len(kept_sessions)

            if result.removed_count == 0:
                result.message = "No sessions to prune"
                return result

            if dry_run:
                result.message = (
                    f"Would prune {result.removed_count} sessions older than {older_than_days}d "
                    f"(kept newest {keep_n} per team)"
                )
                return result

            result.bytes_freed = _get_size(config.SESSIONS_FILE)

            store.save_sessions(kept_sessions)

            new_size = _get_size(config.SESSIONS_FILE)
            result.bytes_freed = result.bytes_freed - new_size

            result.message = (
                f"Pruned {result.removed_count} sessions older than {older_than_days}d "
                f"(kept newest {keep_n} per team)"
            )

    except Exception as exc:
        result.success = False
        result.error = str(exc)
        result.message = f"Failed to prune sessions: {exc}"

    return result


def delete_all_sessions(
    dry_run: bool = False,
    create_backup: bool = True,
) -> ResetResult:
    """Delete entire sessions store.

    Risk: Tier 2 (Destructive) - Removes all session history.
    """
    result = ResetResult(
        success=True,
        action_id="delete_all_sessions",
        risk_tier=RiskTier.DESTRUCTIVE,
        paths=[config.SESSIONS_FILE],
        message="All sessions deleted",
        next_steps=["Your session history is now empty. New sessions will appear as you work."],
    )

    if not config.SESSIONS_FILE.exists():
        result.message = "No sessions to delete"
        return result

    try:
        store = sessions.get_session_store()
        all_sessions = store.load_sessions()
        result.removed_count = len(all_sessions)
    except Exception:
        result.removed_count = 0

    result.bytes_freed = _get_size(config.SESSIONS_FILE)

    if dry_run:
        result.message = f"Would delete {result.removed_count} sessions"
        return result

    if create_backup:
        result.backup_path = _create_backup(config.SESSIONS_FILE)

    try:
        sessions.clear_history()
        result.message = f"Deleted {result.removed_count} sessions"
    except Exception as exc:
        result.success = False
        result.error = str(exc)
        result.message = f"Failed to delete sessions: {exc}"

    return result
