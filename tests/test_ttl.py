"""Tests for TTL parsing utilities (Phase 2.1).

TDD approach: Write tests first, implement to make them pass.

Tests cover:
- TTL format parsing (30m, 2h, 8h, 1d)
- RFC3339 timestamp parsing (--expires-at)
- Time-of-day parsing (--until HH:MM)
- DST edge case handling
- Mutual exclusivity validation
- TTL limits enforcement
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest

if TYPE_CHECKING:
    from pytest import MonkeyPatch


# ═══════════════════════════════════════════════════════════════════════════════
# TTL Duration Parsing Tests (--ttl)
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseTTL:
    """Tests for parsing --ttl duration format."""

    def test_parse_minutes(self):
        """Parse minute durations like '30m'."""
        from scc_cli.utils.ttl import parse_ttl

        result = parse_ttl("30m")
        assert result == timedelta(minutes=30)

    def test_parse_hours(self):
        """Parse hour durations like '8h'."""
        from scc_cli.utils.ttl import parse_ttl

        result = parse_ttl("8h")
        assert result == timedelta(hours=8)

    def test_parse_days(self):
        """Parse day durations like '1d'."""
        from scc_cli.utils.ttl import parse_ttl

        result = parse_ttl("1d")
        assert result == timedelta(days=1)

    def test_parse_multi_digit(self):
        """Parse multi-digit durations."""
        from scc_cli.utils.ttl import parse_ttl

        assert parse_ttl("120m") == timedelta(minutes=120)
        assert parse_ttl("24h") == timedelta(hours=24)
        assert parse_ttl("7d") == timedelta(days=7)

    def test_parse_case_insensitive(self):
        """TTL parsing is case insensitive."""
        from scc_cli.utils.ttl import parse_ttl

        assert parse_ttl("8H") == timedelta(hours=8)
        assert parse_ttl("30M") == timedelta(minutes=30)
        assert parse_ttl("1D") == timedelta(days=1)

    def test_parse_invalid_format_raises(self):
        """Invalid formats raise ValueError with helpful message."""
        from scc_cli.utils.ttl import parse_ttl

        with pytest.raises(ValueError) as exc_info:
            parse_ttl("8hours")
        assert "Invalid TTL" in str(exc_info.value)
        assert "--ttl 8h" in str(exc_info.value)  # Includes example

    def test_parse_empty_raises(self):
        """Empty string raises ValueError."""
        from scc_cli.utils.ttl import parse_ttl

        with pytest.raises(ValueError):
            parse_ttl("")

    def test_parse_zero_raises(self):
        """Zero duration raises ValueError."""
        from scc_cli.utils.ttl import parse_ttl

        with pytest.raises(ValueError) as exc_info:
            parse_ttl("0h")
        assert "must be positive" in str(exc_info.value).lower()

    def test_parse_negative_raises(self):
        """Negative duration raises ValueError."""
        from scc_cli.utils.ttl import parse_ttl

        with pytest.raises(ValueError):
            parse_ttl("-8h")


# ═══════════════════════════════════════════════════════════════════════════════
# RFC3339 Timestamp Parsing Tests (--expires-at)
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseExpiresAt:
    """Tests for parsing --expires-at RFC3339 timestamps."""

    def test_parse_utc_zulu(self, monkeypatch: MonkeyPatch):
        """Parse UTC timestamp with Z suffix."""
        from scc_cli.utils.ttl import parse_expires_at

        # Mock current time to before the test timestamp
        fixed_now = datetime(2025, 12, 21, 10, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr("scc_cli.utils.ttl._get_now", lambda: fixed_now)

        result = parse_expires_at("2025-12-21T17:00:00Z")
        assert result == datetime(2025, 12, 21, 17, 0, 0, tzinfo=timezone.utc)

    def test_parse_with_positive_offset(self, monkeypatch: MonkeyPatch):
        """Parse timestamp with positive timezone offset."""
        from scc_cli.utils.ttl import parse_expires_at

        # Mock current time to before the test timestamp
        fixed_now = datetime(2025, 12, 21, 10, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr("scc_cli.utils.ttl._get_now", lambda: fixed_now)

        result = parse_expires_at("2025-12-21T17:00:00+01:00")
        # Should be 16:00 UTC
        assert result.astimezone(timezone.utc).hour == 16

    def test_parse_with_negative_offset(self, monkeypatch: MonkeyPatch):
        """Parse timestamp with negative timezone offset."""
        from scc_cli.utils.ttl import parse_expires_at

        # Mock current time to before the test timestamp
        fixed_now = datetime(2025, 12, 21, 10, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr("scc_cli.utils.ttl._get_now", lambda: fixed_now)

        result = parse_expires_at("2025-12-21T17:00:00-05:00")
        # Should be 22:00 UTC
        assert result.astimezone(timezone.utc).hour == 22

    def test_parse_past_time_raises(self):
        """Timestamps in the past raise ValueError."""
        from scc_cli.utils.ttl import parse_expires_at

        with pytest.raises(ValueError) as exc_info:
            parse_expires_at("2020-01-01T00:00:00Z")
        assert "past" in str(exc_info.value).lower()

    def test_parse_invalid_format_raises(self):
        """Invalid format raises ValueError with guidance."""
        from scc_cli.utils.ttl import parse_expires_at

        with pytest.raises(ValueError) as exc_info:
            parse_expires_at("2025-12-21 17:00:00")  # Missing T and timezone
        assert "RFC3339" in str(exc_info.value) or "format" in str(exc_info.value).lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Time-of-Day Parsing Tests (--until)
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseUntil:
    """Tests for parsing --until HH:MM time-of-day format."""

    def test_parse_basic_time(self, monkeypatch: MonkeyPatch):
        """Parse basic HH:MM format."""
        from scc_cli.utils.ttl import parse_until

        # Mock current time to 10:00 on Dec 21, 2025
        fixed_now = datetime(2025, 12, 21, 10, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr("scc_cli.utils.ttl._get_now", lambda: fixed_now)
        # Use UTC as local timezone for predictable test behavior
        monkeypatch.setattr("scc_cli.utils.ttl._get_local_tz", lambda: timezone.utc)

        result = parse_until("17:00")
        # Should be 17:00 same day (7 hours later)
        assert result.hour == 17
        assert result.day == 21

    def test_next_day_if_time_passed(self, monkeypatch: MonkeyPatch):
        """If time already passed today, schedule for tomorrow."""
        from scc_cli.utils.ttl import parse_until

        # Mock current time to 23:00 on Dec 21, 2025
        fixed_now = datetime(2025, 12, 21, 23, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr("scc_cli.utils.ttl._get_now", lambda: fixed_now)
        # Use UTC as local timezone for predictable test behavior
        monkeypatch.setattr("scc_cli.utils.ttl._get_local_tz", lambda: timezone.utc)

        result = parse_until("02:00")
        # Should be 02:00 next day (Dec 22)
        assert result.hour == 2
        assert result.day == 22

    def test_same_minute_schedules_tomorrow(self, monkeypatch: MonkeyPatch):
        """If time equals current minute, schedule for tomorrow."""
        from scc_cli.utils.ttl import parse_until

        # Mock current time to exactly 17:00
        fixed_now = datetime(2025, 12, 21, 17, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr("scc_cli.utils.ttl._get_now", lambda: fixed_now)
        # Use UTC as local timezone for predictable test behavior
        monkeypatch.setattr("scc_cli.utils.ttl._get_local_tz", lambda: timezone.utc)

        result = parse_until("17:00")
        # Should be 17:00 next day
        assert result.day == 22

    def test_invalid_format_raises(self):
        """Invalid time format raises ValueError."""
        from scc_cli.utils.ttl import parse_until

        with pytest.raises(ValueError) as exc_info:
            parse_until("5pm")
        assert "HH:MM" in str(exc_info.value)

    def test_invalid_hour_raises(self):
        """Hour > 23 raises ValueError."""
        from scc_cli.utils.ttl import parse_until

        with pytest.raises(ValueError):
            parse_until("25:00")

    def test_invalid_minute_raises(self):
        """Minute > 59 raises ValueError."""
        from scc_cli.utils.ttl import parse_until

        with pytest.raises(ValueError):
            parse_until("17:60")


# ═══════════════════════════════════════════════════════════════════════════════
# DST Edge Case Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDSTHandling:
    """Tests for Daylight Saving Time edge cases."""

    def test_spring_forward_missing_time_raises(self, monkeypatch: MonkeyPatch):
        """Times that don't exist due to spring-forward raise ValueError."""
        from scc_cli.utils.ttl import parse_until

        # Mock current time to just before spring forward (March 9, 2025 in US)
        # In US Eastern, 2:00 AM becomes 3:00 AM (2:30 doesn't exist)
        fixed_now = datetime(2025, 3, 9, 1, 0, 0, tzinfo=ZoneInfo("America/New_York"))
        monkeypatch.setattr("scc_cli.utils.ttl._get_now", lambda: fixed_now)
        monkeypatch.setattr("scc_cli.utils.ttl._get_local_tz", lambda: ZoneInfo("America/New_York"))

        with pytest.raises(ValueError) as exc_info:
            parse_until("02:30")
        assert "does not exist" in str(exc_info.value).lower() or "DST" in str(exc_info.value)
        assert "--expires-at" in str(exc_info.value)  # Guidance provided

    def test_fall_back_ambiguous_time_raises(self, monkeypatch: MonkeyPatch):
        """Ambiguous times due to fall-back raise ValueError."""
        from scc_cli.utils.ttl import parse_until

        # Mock current time to just before fall back (Nov 2, 2025 in US)
        # In US Eastern, 1:30 AM occurs twice
        fixed_now = datetime(2025, 11, 2, 0, 30, 0, tzinfo=ZoneInfo("America/New_York"))
        monkeypatch.setattr("scc_cli.utils.ttl._get_now", lambda: fixed_now)
        monkeypatch.setattr("scc_cli.utils.ttl._get_local_tz", lambda: ZoneInfo("America/New_York"))

        with pytest.raises(ValueError) as exc_info:
            parse_until("01:30")
        assert "ambiguous" in str(exc_info.value).lower() or "DST" in str(exc_info.value)
        assert "--expires-at" in str(exc_info.value)  # Guidance provided


# ═══════════════════════════════════════════════════════════════════════════════
# TTL Limits Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestTTLLimits:
    """Tests for TTL enforcement limits."""

    def test_default_ttl(self):
        """Default TTL is 8 hours."""
        from scc_cli.utils.ttl import DEFAULT_TTL

        assert DEFAULT_TTL == timedelta(hours=8)

    def test_max_ttl(self):
        """Maximum TTL is 24 hours."""
        from scc_cli.utils.ttl import MAX_TTL

        assert MAX_TTL == timedelta(hours=24)

    def test_exceeds_max_raises(self):
        """TTL exceeding max raises ValueError."""
        from scc_cli.utils.ttl import parse_ttl, validate_ttl_duration

        duration = parse_ttl("48h")
        with pytest.raises(ValueError) as exc_info:
            validate_ttl_duration(duration)
        assert "24" in str(exc_info.value)  # References max limit

    def test_at_max_is_valid(self):
        """TTL exactly at max is valid."""
        from scc_cli.utils.ttl import parse_ttl, validate_ttl_duration

        duration = parse_ttl("24h")
        validate_ttl_duration(duration)  # Should not raise


# ═══════════════════════════════════════════════════════════════════════════════
# Expiration Calculation Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestCalculateExpiration:
    """Tests for calculating expiration timestamps."""

    def test_from_ttl(self, monkeypatch: MonkeyPatch):
        """Calculate expiration from TTL duration."""
        from scc_cli.utils.ttl import calculate_expiration

        fixed_now = datetime(2025, 12, 21, 10, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr("scc_cli.utils.ttl._get_now", lambda: fixed_now)

        result = calculate_expiration(ttl="8h")
        assert result == datetime(2025, 12, 21, 18, 0, 0, tzinfo=timezone.utc)

    def test_from_expires_at(self, monkeypatch: MonkeyPatch):
        """Use explicit expiration timestamp."""
        from scc_cli.utils.ttl import calculate_expiration

        # Mock current time to before the test timestamp
        fixed_now = datetime(2025, 12, 21, 10, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr("scc_cli.utils.ttl._get_now", lambda: fixed_now)

        result = calculate_expiration(expires_at="2025-12-21T17:00:00Z")
        assert result == datetime(2025, 12, 21, 17, 0, 0, tzinfo=timezone.utc)

    def test_from_until(self, monkeypatch: MonkeyPatch):
        """Calculate expiration from --until time."""
        from scc_cli.utils.ttl import calculate_expiration

        fixed_now = datetime(2025, 12, 21, 10, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr("scc_cli.utils.ttl._get_now", lambda: fixed_now)
        monkeypatch.setattr("scc_cli.utils.ttl._get_local_tz", lambda: timezone.utc)

        result = calculate_expiration(until="17:00")
        assert result.hour == 17
        assert result.day == 21

    def test_default_when_none_specified(self, monkeypatch: MonkeyPatch):
        """Uses default TTL when no option specified."""
        from scc_cli.utils.ttl import calculate_expiration

        fixed_now = datetime(2025, 12, 21, 10, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr("scc_cli.utils.ttl._get_now", lambda: fixed_now)

        result = calculate_expiration()
        # Default is 8h
        assert result == datetime(2025, 12, 21, 18, 0, 0, tzinfo=timezone.utc)

    def test_mutual_exclusivity(self):
        """Specifying multiple options raises ValueError."""
        from scc_cli.utils.ttl import calculate_expiration

        with pytest.raises(ValueError) as exc_info:
            calculate_expiration(ttl="8h", expires_at="2025-12-21T17:00:00Z")
        assert (
            "mutually exclusive" in str(exc_info.value).lower()
            or "one of" in str(exc_info.value).lower()
        )

    def test_all_three_raises(self):
        """Specifying all three options raises ValueError."""
        from scc_cli.utils.ttl import calculate_expiration

        with pytest.raises(ValueError):
            calculate_expiration(ttl="8h", expires_at="2025-12-21T17:00:00Z", until="17:00")


# ═══════════════════════════════════════════════════════════════════════════════
# Formatting Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormatExpiration:
    """Tests for expiration display formatting."""

    def test_format_to_rfc3339(self):
        """Format datetime to RFC3339 string."""
        from scc_cli.utils.ttl import format_expiration

        dt = datetime(2025, 12, 21, 17, 0, 0, tzinfo=timezone.utc)
        result = format_expiration(dt)
        assert result == "2025-12-21T17:00:00Z"

    def test_format_relative_hours(self, monkeypatch: MonkeyPatch):
        """Format relative time in hours."""
        from scc_cli.utils.ttl import format_relative

        fixed_now = datetime(2025, 12, 21, 10, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr("scc_cli.utils.ttl._get_now", lambda: fixed_now)

        expires = datetime(2025, 12, 21, 17, 45, 0, tzinfo=timezone.utc)
        result = format_relative(expires)
        assert result == "7h45m"

    def test_format_relative_minutes_only(self, monkeypatch: MonkeyPatch):
        """Format relative time when less than an hour."""
        from scc_cli.utils.ttl import format_relative

        fixed_now = datetime(2025, 12, 21, 10, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr("scc_cli.utils.ttl._get_now", lambda: fixed_now)

        expires = datetime(2025, 12, 21, 10, 30, 0, tzinfo=timezone.utc)
        result = format_relative(expires)
        assert result == "30m"

    def test_format_relative_days(self, monkeypatch: MonkeyPatch):
        """Format relative time in days when appropriate."""
        from scc_cli.utils.ttl import format_relative

        fixed_now = datetime(2025, 12, 21, 10, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr("scc_cli.utils.ttl._get_now", lambda: fixed_now)

        expires = datetime(2025, 12, 22, 10, 0, 0, tzinfo=timezone.utc)
        result = format_relative(expires)
        assert result == "1d"

    def test_format_relative_expired(self, monkeypatch: MonkeyPatch):
        """Format expired time returns 'expired'."""
        from scc_cli.utils.ttl import format_relative

        fixed_now = datetime(2025, 12, 21, 17, 0, 0, tzinfo=timezone.utc)
        monkeypatch.setattr("scc_cli.utils.ttl._get_now", lambda: fixed_now)

        expires = datetime(2025, 12, 21, 10, 0, 0, tzinfo=timezone.utc)
        result = format_relative(expires)
        assert result == "expired"
