"""JSON-backed session store adapter."""

from __future__ import annotations

import json
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from scc_cli import config
from scc_cli.ports.filesystem import Filesystem
from scc_cli.ports.session_models import SessionRecord
from scc_cli.utils.locks import file_lock, lock_path


@dataclass(frozen=True)
class JsonSessionStore:
    """Persist session records in the legacy JSON schema.

    Invariants:
        - JSON payload remains `{ "sessions": [...] }` with stable field names.
        - Legacy migrations run on load ("base" team -> None).

    Args:
        filesystem: Filesystem adapter used to read/write session data.
        sessions_file: Path to the sessions JSON file.
        lock_file: Path to the lock file guarding sessions access.
    """

    filesystem: Filesystem
    sessions_file: Path = config.SESSIONS_FILE
    lock_file: Path = field(default_factory=lambda: lock_path("sessions"))

    def lock(self) -> AbstractContextManager[None]:
        """Return an exclusive lock for session operations.

        Returns:
            Context manager enforcing exclusive access to session data.
        """
        return file_lock(self.lock_file)

    def load_sessions(self) -> list[SessionRecord]:
        """Load sessions from disk.

        Returns:
            List of session records, or an empty list on read errors.
        """
        if not self.filesystem.exists(self.sessions_file):
            return []

        try:
            data = json.loads(self.filesystem.read_text(self.sessions_file))
            sessions = cast(list[dict[str, Any]], data.get("sessions", []))
            return [SessionRecord.from_dict(item) for item in _migrate_legacy_sessions(sessions)]
        except (OSError, json.JSONDecodeError, TypeError):
            return []

    def save_sessions(self, sessions: list[SessionRecord]) -> None:
        """Persist sessions to disk.

        Args:
            sessions: Session records to store.
        """
        payload = {"sessions": [record.to_dict() for record in sessions]}
        self.filesystem.write_text(self.sessions_file, json.dumps(payload, indent=2))


def _migrate_legacy_sessions(sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply legacy migrations to session records.

    Invariants:
        - "base" team sentinel becomes None for standalone sessions.

    Args:
        sessions: Raw session dictionaries loaded from disk.

    Returns:
        Migrated session dictionaries.
    """
    for session in sessions:
        if session.get("team") == "base":
            session["team"] = None
    return sessions
