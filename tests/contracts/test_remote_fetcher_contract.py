"""Contract tests for RemoteFetcher implementations."""

from __future__ import annotations

import responses

from scc_cli.adapters.requests_fetcher import RequestsFetcher


@responses.activate
def test_requests_fetcher_get_returns_response() -> None:
    url = "https://example.com/config.json"
    responses.add(
        responses.GET,
        url,
        body='{"ok": true}',
        status=200,
        headers={"ETag": "abc"},
    )

    fetcher = RequestsFetcher()
    response = fetcher.get(url)

    assert response.status_code == 200
    assert response.text == '{"ok": true}'
    assert response.headers.get("ETag") == "abc"
