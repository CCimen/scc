"""Relative time formatting helpers for UI output."""

from __future__ import annotations

from datetime import datetime, timezone


def format_relative_time_compact(iso_timestamp: str) -> str:
    """Format an ISO timestamp as compact relative time.

    Args:
        iso_timestamp: ISO 8601 timestamp string.

    Returns:
        Relative time string (e.g., "2h ago"), or empty if parsing fails.
    """
    try:
        timestamp = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        delta = now - timestamp

        seconds = int(delta.total_seconds())
        if seconds < 0:
            return ""
        if seconds < 60:
            return "just now"
        if seconds < 3600:
            minutes = seconds // 60
            return f"{minutes}m ago"
        if seconds < 86400:
            hours = seconds // 3600
            return f"{hours}h ago"
        if seconds < 604800:
            days = seconds // 86400
            return f"{days}d ago"
        weeks = seconds // 604800
        return f"{weeks}w ago"
    except (ValueError, TypeError):
        return ""


def format_relative_time_calendar(iso_timestamp: str) -> str:
    """Format an ISO timestamp with calendar-style labels.

    Examples:
        2 minutes ago → "2m ago"
        yesterday → "yesterday"
        older → "Dec 20"

    Args:
        iso_timestamp: ISO 8601 timestamp string.

    Returns:
        Calendar-style relative time string, or empty if parsing fails.
    """
    try:
        if iso_timestamp.endswith("Z"):
            iso_timestamp = iso_timestamp[:-1] + "+00:00"

        timestamp = datetime.fromisoformat(iso_timestamp)
        now = datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        delta = now - timestamp
        seconds = delta.total_seconds()

        if seconds < 60:
            return "just now"
        if seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes}m ago"
        if seconds < 86400:
            hours = int(seconds / 3600)
            return f"{hours}h ago"
        if seconds < 172800:
            return "yesterday"
        if seconds < 604800:
            days = int(seconds / 86400)
            return f"{days}d ago"
        return timestamp.strftime("%b %d")
    except (ValueError, AttributeError):
        return ""


def format_relative_time_from_datetime(dt: datetime) -> str:
    """Format a datetime as a relative time string.

    Args:
        dt: Datetime to format.

    Returns:
        Relative time string (e.g., "2h ago").
    """
    now = datetime.now()
    diff = now - dt

    seconds = diff.total_seconds()

    if seconds < 60:
        return "just now"
    if seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes}m ago"
    if seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours}h ago"
    if seconds < 604800:
        days = int(seconds / 86400)
        return f"{days}d ago"
    weeks = int(seconds / 604800)
    return f"{weeks}w ago"
