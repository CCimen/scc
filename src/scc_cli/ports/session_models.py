"""Session models used by session ports and services."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SessionRecord:
    """Persisted session record stored on disk.

    Invariants:
        - Serialized field names must remain stable for the sessions JSON schema.
        - Optional fields are omitted when serialized.

    Args:
        workspace: Workspace path as a string.
        team: Team identifier or None for standalone sessions.
        name: Optional friendly session name.
        container_name: Container name linked to the session.
        branch: Git branch name for the session.
        last_used: ISO 8601 timestamp string of last use.
        created_at: ISO 8601 timestamp string of creation time.
        schema_version: Schema version for migration support.
    """

    workspace: str
    team: str | None = None
    name: str | None = None
    container_name: str | None = None
    branch: str | None = None
    last_used: str | None = None
    created_at: str | None = None
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Serialize the record for JSON storage.

        Returns:
            Dictionary suitable for JSON serialization.
        """
        return {key: value for key, value in asdict(self).items() if value is not None}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionRecord:
        """Hydrate a record from stored JSON.

        Args:
            data: Raw session dictionary from the sessions file.

        Returns:
            Parsed SessionRecord instance.
        """
        return cls(
            workspace=data.get("workspace", ""),
            team=data.get("team"),
            name=data.get("name"),
            container_name=data.get("container_name"),
            branch=data.get("branch"),
            last_used=data.get("last_used"),
            created_at=data.get("created_at"),
            schema_version=data.get("schema_version", 1),
        )


@dataclass(frozen=True)
class SessionSummary:
    """Summary view of a session for list output.

    Invariants:
        - Fields must align with existing CLI session list keys.

    Args:
        name: Display name for the session.
        workspace: Workspace path string.
        team: Team identifier or None.
        last_used: ISO 8601 timestamp string (format at edges).
        container_name: Linked container name.
        branch: Git branch name for the session.
    """

    name: str
    workspace: str
    team: str | None
    last_used: str | None
    container_name: str | None
    branch: str | None


@dataclass(frozen=True)
class SessionFilter:
    """Filter options for listing sessions.

    Invariants:
        - Limit values must remain non-negative.

    Args:
        limit: Maximum number of sessions to return.
        team: Optional team filter.
        include_all: Whether to ignore team filtering.
    """

    limit: int = 10
    team: str | None = None
    include_all: bool = False


@dataclass(frozen=True)
class SessionListResult:
    """Result payload for session list operations.

    Invariants:
        - Count reflects the number of session summaries.

    Args:
        sessions: Summaries returned by a list operation.
        team: Team filter applied to the list.
        count: Count of sessions returned.
    """

    sessions: list[SessionSummary]
    team: str | None = None
    count: int = 0

    @classmethod
    def from_sessions(
        cls,
        sessions: list[SessionSummary],
        *,
        team: str | None = None,
    ) -> SessionListResult:
        """Build a list result with count calculated.

        Args:
            sessions: Session summaries returned by the list operation.
            team: Team filter applied to the list.

        Returns:
            SessionListResult populated with count.
        """
        return cls(sessions=sessions, team=team, count=len(sessions))
