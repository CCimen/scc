"""Requests adapter for RemoteFetcher port."""

from __future__ import annotations

import requests

from scc_cli.ports.remote_fetcher import RemoteFetcher, RemoteResponse


class RequestsFetcher(RemoteFetcher):
    """RemoteFetcher implementation using requests."""

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> RemoteResponse:
        response = requests.get(url, headers=headers, timeout=timeout)
        normalized_headers = {key: str(value) for key, value in response.headers.items()}
        return RemoteResponse(
            status_code=response.status_code,
            text=response.text,
            content=response.content,
            headers=normalized_headers,
        )
