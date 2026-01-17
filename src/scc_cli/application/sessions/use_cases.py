"""Session persistence use cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from scc_cli.ports.session_models import (
    SessionFilter,
    SessionListResult,
    SessionRecord,
    SessionSummary,
)
from scc_cli.ports.session_store import SessionStore


@dataclass(frozen=True)
class SessionService:
    """Coordinate session persistence and retrieval.

    Invariants:
        - Session records are sorted by last_used descending when listed.
        - Workspace+branch pairs uniquely identify a session entry.

    Args:
        store: SessionStore implementation for persistence.
    """

    store: SessionStore

    def list_recent(self, session_filter: SessionFilter) -> SessionListResult:
        """Return recent sessions filtered by team and limit.

        Args:
            session_filter: Filtering options for the session list.

        Returns:
            SessionListResult with summaries and count.
        """
        sessions = self.store.load_sessions()
        sessions = _filter_sessions(sessions, session_filter)
        sessions.sort(key=lambda record: record.last_used or "", reverse=True)
        sessions = sessions[: session_filter.limit]
        summaries = [
            SessionSummary(
                name=record.name or _generate_session_name(record),
                workspace=record.workspace,
                team=record.team,
                last_used=record.last_used,
                container_name=record.container_name,
                branch=record.branch,
            )
            for record in sessions
        ]
        team_label = None if session_filter.include_all else session_filter.team
        return SessionListResult.from_sessions(summaries, team=team_label)

    def record_session(
        self,
        *,
        workspace: str,
        team: str | None = None,
        session_name: str | None = None,
        container_name: str | None = None,
        branch: str | None = None,
    ) -> SessionRecord:
        """Record a session creation or update.

        Args:
            workspace: Workspace path as a string.
            team: Team identifier or None for standalone sessions.
            session_name: Optional session display name.
            container_name: Optional container name.
            branch: Optional git branch name.

        Returns:
            SessionRecord that was written.
        """
        now = datetime.now().isoformat()
        with self.store.lock():
            sessions = self.store.load_sessions()
            existing_index = _find_session_index(sessions, workspace, branch)
            created_at = sessions[existing_index].created_at if existing_index is not None else now
            record = SessionRecord(
                workspace=workspace,
                team=team,
                name=session_name,
                container_name=container_name,
                branch=branch,
                last_used=now,
                created_at=created_at,
            )
            if existing_index is not None:
                sessions[existing_index] = record
            else:
                sessions.insert(0, record)
            self.store.save_sessions(sessions)
            return record

    def update_session_container(
        self,
        *,
        workspace: str,
        container_name: str,
        branch: str | None = None,
    ) -> None:
        """Update the container name for an existing session.

        Args:
            workspace: Workspace path string.
            container_name: Container name to set.
            branch: Optional branch to match when updating.
        """
        now = datetime.now().isoformat()
        with self.store.lock():
            sessions = self.store.load_sessions()
            for record in sessions:
                if record.workspace == workspace and (branch is None or record.branch == branch):
                    updated = SessionRecord(
                        workspace=record.workspace,
                        team=record.team,
                        name=record.name,
                        container_name=container_name,
                        branch=record.branch,
                        last_used=now,
                        created_at=record.created_at,
                        schema_version=record.schema_version,
                    )
                    sessions[sessions.index(record)] = updated
                    break
            self.store.save_sessions(sessions)

    def prune_orphaned_sessions(self) -> int:
        """Remove sessions whose workspace paths no longer exist.

        Returns:
            Number of sessions removed.
        """
        with self.store.lock():
            sessions = self.store.load_sessions()
            remaining = [
                record for record in sessions if Path(record.workspace).expanduser().exists()
            ]
            removed = len(sessions) - len(remaining)
            self.store.save_sessions(remaining)
            return removed


def _filter_sessions(
    sessions: list[SessionRecord],
    session_filter: SessionFilter,
) -> list[SessionRecord]:
    if session_filter.include_all:
        return sessions
    if session_filter.team is None:
        return [record for record in sessions if record.team is None]
    return [record for record in sessions if record.team == session_filter.team]


def _generate_session_name(record: SessionRecord) -> str:
    """Generate a display name for sessions without explicit names."""
    if record.workspace:
        return Path(record.workspace).name
    return "Unnamed"


def _find_session_index(
    sessions: list[SessionRecord],
    workspace: str,
    branch: str | None,
) -> int | None:
    for index, record in enumerate(sessions):
        if record.workspace == workspace and record.branch == branch:
            return index
    return None
