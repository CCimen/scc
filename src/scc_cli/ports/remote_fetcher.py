"""Remote fetcher port definition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RemoteResponse:
    """Normalized response data for remote fetch operations."""

    status_code: int
    text: str
    content: bytes
    headers: dict[str, str]


class RemoteFetcher(Protocol):
    """Abstract HTTP fetcher for remote config."""

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> RemoteResponse:
        """Perform an HTTP GET request."""
