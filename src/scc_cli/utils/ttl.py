"""Provide TTL parsing and expiration utilities for SCC Phase 2.1.

Handle parsing of time-bounded exception durations:
- TTL format: 30m, 2h, 8h, 1d
- RFC3339 timestamps: 2025-12-21T17:00:00+01:00
- Time-of-day: HH:MM (next occurrence)

Key behaviors:
- All internal timestamps are UTC
- --until uses local timezone, always schedules next occurrence
- DST edge cases (missing/ambiguous times) raise errors with guidance
- Hard max limit of 24h (configurable in future phases)
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_TTL = timedelta(hours=8)
MAX_TTL = timedelta(hours=24)

# Pattern for TTL format: 30m, 8h, 1d
TTL_PATTERN = re.compile(r"^(\d+)([mhdMHD])$")

# Pattern for HH:MM format
UNTIL_PATTERN = re.compile(r"^(\d{2}):(\d{2})$")


# ═══════════════════════════════════════════════════════════════════════════════
# Internal Helpers (for test mocking)
# ═══════════════════════════════════════════════════════════════════════════════


def _get_now() -> datetime:
    """Get current UTC time. Extracted for test mocking."""
    return datetime.now(timezone.utc)


def _get_local_tz() -> ZoneInfo | timezone:
    """Get local timezone. Extracted for test mocking."""
    try:
        import os

        # Try to get proper timezone from TZ environment variable
        tz_env = os.environ.get("TZ")
        if tz_env:
            return ZoneInfo(tz_env)
        # Fallback: use UTC offset from system
        local_offset = datetime.now().astimezone().utcoffset()
        if local_offset is not None:
            return timezone(local_offset)
    except Exception:
        pass
    return timezone.utc


# ═══════════════════════════════════════════════════════════════════════════════
# TTL Parsing (--ttl)
# ═══════════════════════════════════════════════════════════════════════════════


def parse_ttl(ttl_string: str) -> timedelta:
    """Parse a TTL duration string like '30m', '8h', or '1d'.

    Args:
        ttl_string: Duration in format like "30m", "8h", "1d"

    Returns:
        timedelta representing the duration

    Raises:
        ValueError: If format is invalid or duration is non-positive
    """
    if not ttl_string:
        raise ValueError("TTL cannot be empty")

    match = TTL_PATTERN.match(ttl_string)
    if not match:
        raise ValueError(
            f"Invalid TTL '{ttl_string}'. "
            f"Use: --ttl 8h, --ttl 30m, or --expires-at 2025-12-21T17:00:00+01:00"
        )

    value = int(match.group(1))
    unit = match.group(2).lower()

    if value <= 0:
        raise ValueError("TTL must be positive")

    if unit == "m":
        return timedelta(minutes=value)
    elif unit == "h":
        return timedelta(hours=value)
    elif unit == "d":
        return timedelta(days=value)
    else:
        raise ValueError(f"Unknown TTL unit: {unit}")


def validate_ttl_duration(duration: timedelta) -> None:
    """Validate that a TTL duration is within allowed limits.

    Args:
        duration: The duration to validate

    Raises:
        ValueError: If duration exceeds MAX_TTL
    """
    if duration > MAX_TTL:
        max_hours = int(MAX_TTL.total_seconds() // 3600)
        raise ValueError(f"TTL exceeds maximum allowed duration of {max_hours} hours")


# ═══════════════════════════════════════════════════════════════════════════════
# RFC3339 Parsing (--expires-at)
# ═══════════════════════════════════════════════════════════════════════════════


def parse_expires_at(timestamp: str) -> datetime:
    """Parse an RFC3339 timestamp for expiration.

    Args:
        timestamp: RFC3339 formatted timestamp like "2025-12-21T17:00:00Z"

    Returns:
        datetime with timezone info (converted to UTC internally)

    Raises:
        ValueError: If format is invalid or time is in the past
    """
    try:
        # Handle Z suffix (UTC)
        if timestamp.endswith("Z"):
            timestamp = timestamp[:-1] + "+00:00"

        dt = datetime.fromisoformat(timestamp)

        # Ensure timezone-aware
        if dt.tzinfo is None:
            raise ValueError(
                "Timestamp must include timezone. "
                "Format: --expires-at 2025-12-21T17:00:00+01:00 or 2025-12-21T17:00:00Z"
            )

    except ValueError as e:
        if "Invalid isoformat" in str(e) or "fromisoformat" in str(e):
            raise ValueError(
                "Invalid timestamp format. Use RFC3339: --expires-at 2025-12-21T17:00:00+01:00"
            ) from e
        raise

    # Check not in the past
    now = _get_now()
    if dt.astimezone(timezone.utc) <= now:
        raise ValueError("Expiration time is in the past. Provide a future timestamp.")

    return dt.astimezone(timezone.utc)


# ═══════════════════════════════════════════════════════════════════════════════
# Time-of-Day Parsing (--until)
# ═══════════════════════════════════════════════════════════════════════════════


def parse_until(time_string: str) -> datetime:
    """Parse a time-of-day string like '17:00' for next occurrence.

    Args:
        time_string: Time in HH:MM format

    Returns:
        datetime (in local timezone) for next occurrence of that time

    Raises:
        ValueError: If format is invalid, time doesn't exist (DST spring-forward),
                   or time is ambiguous (DST fall-back)
    """
    match = UNTIL_PATTERN.match(time_string)
    if not match:
        raise ValueError(
            f"Invalid time format '{time_string}'. Use HH:MM format like: --until 17:00"
        )

    hour = int(match.group(1))
    minute = int(match.group(2))

    if hour > 23:
        raise ValueError(f"Invalid hour: {hour}. Must be 00-23.")
    if minute > 59:
        raise ValueError(f"Invalid minute: {minute}. Must be 00-59.")

    now = _get_now()
    local_tz = _get_local_tz()

    # Convert current time to local timezone
    now_local = now.astimezone(local_tz)

    # Start with today's date at the specified time
    target_date = now_local.date()
    target_time_today = _make_local_datetime(target_date, hour, minute, local_tz)

    # If time has passed or is exactly now, schedule for tomorrow
    if target_time_today is None or target_time_today <= now_local:
        tomorrow = target_date + timedelta(days=1)
        target_time_tomorrow = _make_local_datetime(tomorrow, hour, minute, local_tz)
        if target_time_tomorrow is None:
            raise ValueError(
                f"Time {time_string} does not exist tomorrow due to DST transition. "
                f"Use --expires-at with explicit UTC offset instead."
            )
        return target_time_tomorrow.astimezone(timezone.utc)

    return target_time_today.astimezone(timezone.utc)


def _make_local_datetime(
    target_date: date, hour: int, minute: int, tz: ZoneInfo | timezone
) -> datetime | None:
    """Create a datetime in local timezone, handling DST edge cases.

    Returns:
        datetime if valid, None if time doesn't exist (spring-forward)

    Raises:
        ValueError: If time is ambiguous (fall-back)
    """
    try:
        # Create naive datetime first
        naive_dt = datetime(target_date.year, target_date.month, target_date.day, hour, minute, 0)

        # For ZoneInfo timezones, check for DST issues
        if isinstance(tz, ZoneInfo):
            # Try to localize - this can raise for ambiguous times
            try:
                # Use fold=0 first, then check if fold=1 gives different result
                dt_fold0 = naive_dt.replace(tzinfo=tz, fold=0)
                dt_fold1 = naive_dt.replace(tzinfo=tz, fold=1)

                # If the UTC offsets differ, time is ambiguous (fall-back)
                if dt_fold0.utcoffset() != dt_fold1.utcoffset():
                    raise ValueError(
                        f"Time {hour:02d}:{minute:02d} is ambiguous due to DST transition. "
                        f"Use --expires-at with explicit UTC offset instead."
                    )

                # Check if time exists (spring-forward case)
                # After localization, convert back to naive and check if it matches
                utc_time = dt_fold0.astimezone(timezone.utc)
                back_to_local = utc_time.astimezone(tz)
                if back_to_local.hour != hour or back_to_local.minute != minute:
                    # Time doesn't exist (was skipped in spring-forward)
                    return None

                return dt_fold0

            except Exception as e:
                if "ambiguous" in str(e).lower():
                    raise ValueError(
                        f"Time {hour:02d}:{minute:02d} is ambiguous due to DST transition. "
                        f"Use --expires-at with explicit UTC offset instead."
                    ) from e
                raise
        else:
            # Simple timezone (like UTC or fixed offset)
            return naive_dt.replace(tzinfo=tz)

    except ValueError:
        raise


# ═══════════════════════════════════════════════════════════════════════════════
# Expiration Calculation
# ═══════════════════════════════════════════════════════════════════════════════


def calculate_expiration(
    ttl: str | None = None,
    expires_at: str | None = None,
    until: str | None = None,
) -> datetime:
    """Calculate expiration datetime from one of the timing options.

    Args:
        ttl: Duration string like "8h"
        expires_at: RFC3339 timestamp
        until: Time-of-day like "17:00"

    Returns:
        datetime in UTC for expiration

    Raises:
        ValueError: If multiple options specified (mutually exclusive)
    """
    # Count how many options were provided
    provided = sum(1 for opt in [ttl, expires_at, until] if opt is not None)

    if provided > 1:
        raise ValueError(
            "Only one of --ttl, --expires-at, or --until can be specified. "
            "These options are mutually exclusive."
        )

    if ttl is not None:
        duration = parse_ttl(ttl)
        validate_ttl_duration(duration)
        return _get_now() + duration

    if expires_at is not None:
        return parse_expires_at(expires_at)

    if until is not None:
        return parse_until(until)

    # Default: use DEFAULT_TTL
    return _get_now() + DEFAULT_TTL


# ═══════════════════════════════════════════════════════════════════════════════
# Formatting
# ═══════════════════════════════════════════════════════════════════════════════


def format_expiration(dt: datetime) -> str:
    """Format a datetime as RFC3339 string.

    Args:
        dt: datetime to format (should be timezone-aware)

    Returns:
        RFC3339 formatted string like "2025-12-21T17:00:00Z"
    """
    # Convert to UTC and format with Z suffix
    utc_dt = dt.astimezone(timezone.utc)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def format_relative(expires: datetime) -> str:
    """Format remaining time until expiration as human-readable string.

    Args:
        expires: expiration datetime

    Returns:
        String like "7h45m", "30m", "1d", or "expired"
    """
    now = _get_now()
    delta = expires - now

    if delta.total_seconds() <= 0:
        return "expired"

    total_seconds = int(delta.total_seconds())
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60

    if days > 0:
        if hours == 0 and minutes == 0:
            return f"{days}d"
        elif hours > 0:
            return f"{days}d{hours}h"
        else:
            return f"{days}d{minutes}m"

    if hours > 0:
        if minutes > 0:
            return f"{hours}h{minutes}m"
        return f"{hours}h"

    return f"{minutes}m"
