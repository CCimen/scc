"""Fake RuntimeProbe for tests."""

from __future__ import annotations

from scc_cli.core.contracts import RuntimeInfo

# Default: fully-capable Docker Desktop scenario.
_DEFAULT_RUNTIME_INFO = RuntimeInfo(
    runtime_id="docker",
    display_name="Docker Desktop",
    cli_name="docker",
    supports_oci=True,
    supports_internal_networks=True,
    supports_host_network=True,
    version="Docker version 27.5.1, build abc1234",
    desktop_version="4.50.0",
    daemon_reachable=True,
    sandbox_available=True,
    preferred_backend="docker-sandbox",
)


class FakeRuntimeProbe:
    """In-memory runtime probe returning configurable RuntimeInfo."""

    def __init__(self, info: RuntimeInfo | None = None) -> None:
        self._info = info or _DEFAULT_RUNTIME_INFO

    def probe(self) -> RuntimeInfo:
        return self._info
