"""Contract tests for Clock implementations."""

from __future__ import annotations

from datetime import timezone

from scc_cli.adapters.system_clock import SystemClock


def test_system_clock_returns_utc_time() -> None:
    clock = SystemClock()
    now = clock.now()

    assert now.tzinfo is not None
    assert now.tzinfo.utcoffset(now) == timezone.utc.utcoffset(now)
