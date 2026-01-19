"""Session persistence port for application use cases."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Protocol

from .session_models import SessionRecord


class SessionStore(Protocol):
    """Persist and retrieve session records for the application layer.

    Invariants:
        - Persistence must preserve session JSON schema fields.
        - Calls must be safe for concurrent CLI invocations.
    """

    def lock(self) -> AbstractContextManager[None]:
        """Return a context manager for exclusive session store access.

        Returns:
            Context manager enforcing exclusive access while reading/writing.
        """
        ...

    def load_sessions(self) -> list[SessionRecord]:
        """Load all session records.

        Returns:
            List of stored session records.
        """
        ...

    def save_sessions(self, sessions: list[SessionRecord]) -> None:
        """Persist all session records.

        Args:
            sessions: Session records to store.
        """
        ...
