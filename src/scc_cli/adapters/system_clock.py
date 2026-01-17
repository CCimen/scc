"""System clock adapter for Clock port."""

from __future__ import annotations

from datetime import datetime, timezone

from scc_cli.ports.clock import Clock


class SystemClock(Clock):
    """Clock implementation using system time."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)
