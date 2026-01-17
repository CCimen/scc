"""Clock port definition."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Abstract clock for time retrieval."""

    def now(self) -> datetime:
        """Return the current time."""
