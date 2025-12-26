"""
Usage statistics tracking.

Phase 1: User-level only.
- Stats stored at ~/.cache/scc/usage.jsonl
- Users see only their own stats
- Manual aggregation via scc stats export

Handle:
- Session start/end recording
- Event JSONL file operations
- Stats aggregation and reporting
- Export functionality
"""

from __future__ import annotations

import getpass
import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from scc_cli.config import CACHE_DIR

if TYPE_CHECKING:
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════════

USAGE_FILE = "usage.jsonl"


# ═══════════════════════════════════════════════════════════════════════════════
# Identity Pseudonymization
# ═══════════════════════════════════════════════════════════════════════════════


def _get_machine_salt() -> str:
    """Get a machine-specific salt for hashing.

    Uses hostname + home directory to create a unique salt per machine.
    This ensures hashes are consistent on the same machine but different
    across machines, protecting user privacy.
    """
    import socket

    hostname = socket.gethostname()
    home = str(Path.home())
    return f"{hostname}:{home}"


def hash_identifier(identifier: str) -> str:
    """Hash an identifier for pseudonymization.

    Creates a one-way hash that is:
    - Consistent: same input always produces same output
    - Not reversible: original identifier cannot be recovered
    - Machine-specific: different machines produce different hashes

    Args:
        identifier: The identifier to hash (e.g., username, email)

    Returns:
        A hex string hash of the identifier
    """
    salt = _get_machine_salt()
    combined = f"{salt}:{identifier}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()[:32]


def get_username() -> str:
    """Get the current username.

    This is separated into its own function for easier testing/mocking.
    """
    return getpass.getuser()


# ═══════════════════════════════════════════════════════════════════════════════
# JSONL File Operations
# ═══════════════════════════════════════════════════════════════════════════════


def _get_usage_file() -> Path:
    """Get the path to the usage JSONL file."""
    return CACHE_DIR / USAGE_FILE


def _write_event(event: dict[str, Any]) -> None:
    """Append an event to the JSONL file.

    Args:
        event: Event dict to write
    """
    usage_file = _get_usage_file()
    usage_file.parent.mkdir(parents=True, exist_ok=True)

    with open(usage_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def read_usage_events() -> list[dict[str, Any]]:
    """Read all events from the usage JSONL file.

    Returns:
        List of event dicts. Empty list if file doesn't exist or is empty.
        Malformed JSON lines are skipped silently.
    """
    usage_file = _get_usage_file()

    if not usage_file.exists():
        return []

    events = []
    try:
        with open(usage_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    # Skip malformed lines
                    continue
    except OSError:
        return []

    return events


# ═══════════════════════════════════════════════════════════════════════════════
# Session Recording
# ═══════════════════════════════════════════════════════════════════════════════


def record_session_start(
    session_id: str,
    project_name: str,
    team_name: str | None,
    expected_duration_hours: int,
    stats_config: dict[str, Any] | None = None,
) -> None:
    """Record a session start event.

    Args:
        session_id: Unique identifier for this session
        project_name: Name of the project/workspace
        team_name: Name of the team (optional)
        expected_duration_hours: Expected session duration from config
        stats_config: Stats configuration dict (optional). If stats_config.enabled
            is False, no event is recorded.
    """
    # Check if stats are enabled
    if stats_config is not None and not stats_config.get("enabled", True):
        return

    # Determine user identity mode
    identity_mode = "hash"
    if stats_config is not None:
        identity_mode = stats_config.get("user_identity_mode", "hash")

    # Build user_id_hash based on identity mode
    user_id_hash: str | None = None
    if identity_mode == "hash":
        user_id_hash = hash_identifier(get_username())
    # If identity_mode == "none", user_id_hash stays None

    event = {
        "event_type": "session_start",
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
        "project_name": project_name,
        "team_name": team_name,
        "expected_duration_hours": expected_duration_hours,
    }

    if user_id_hash is not None:
        event["user_id_hash"] = user_id_hash

    _write_event(event)


def record_session_end(
    session_id: str,
    actual_duration_minutes: int,
    exit_status: str = "clean",
    stats_config: dict[str, Any] | None = None,
) -> None:
    """Record a session end event.

    Args:
        session_id: Unique identifier matching the session start
        actual_duration_minutes: Actual session duration in minutes
        exit_status: How the session ended ('clean', 'crash', 'interrupted')
        stats_config: Stats configuration dict (optional). If stats_config.enabled
            is False, no event is recorded.
    """
    # Check if stats are enabled
    if stats_config is not None and not stats_config.get("enabled", True):
        return

    event = {
        "event_type": "session_end",
        "session_id": session_id,
        "timestamp": datetime.now().isoformat(),
        "actual_duration_minutes": actual_duration_minutes,
        "exit_status": exit_status,
    }

    _write_event(event)


# ═══════════════════════════════════════════════════════════════════════════════
# Stats Report Dataclass
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class StatsReport:
    """Aggregated usage statistics report.

    Attributes:
        total_sessions: Number of sessions in the period
        total_duration_minutes: Sum of actual duration from completed sessions
        incomplete_sessions: Sessions without a session_end event
        by_project: Per-project breakdown {project: {sessions, duration_minutes}}
        period_start: Start of the reporting period
        period_end: End of the reporting period
    """

    total_sessions: int
    total_duration_minutes: int
    incomplete_sessions: int
    by_project: dict[str, dict[str, int]]
    period_start: datetime
    period_end: datetime

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "total_sessions": self.total_sessions,
            "total_duration_minutes": self.total_duration_minutes,
            "incomplete_sessions": self.incomplete_sessions,
            "by_project": self.by_project,
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Stats Aggregation
# ═══════════════════════════════════════════════════════════════════════════════


def get_stats(days: int | None = None) -> StatsReport:
    """Aggregate usage statistics.

    Args:
        days: Number of days to include (None for all time)

    Returns:
        StatsReport with aggregated statistics
    """
    events = read_usage_events()

    # Determine period
    period_end = datetime.now()
    if days is not None:
        period_start = period_end - timedelta(days=days)
    else:
        period_start = datetime.min

    # Filter events by period
    session_starts: dict[str, dict[str, Any]] = {}
    session_ends: dict[str, dict[str, Any]] = {}

    for event in events:
        event_time_str = event.get("timestamp")
        if event_time_str:
            try:
                event_time = datetime.fromisoformat(event_time_str)
                if days is not None and event_time < period_start:
                    continue
            except (ValueError, TypeError):
                pass

        event_type = event.get("event_type")
        session_id = event.get("session_id")

        if event_type == "session_start" and session_id:
            session_starts[session_id] = event
        elif event_type == "session_end" and session_id:
            session_ends[session_id] = event

    # Count sessions and calculate duration
    total_sessions = len(session_starts)
    incomplete_sessions = 0
    total_duration_minutes = 0

    # Per-project breakdown
    by_project: dict[str, dict[str, int]] = {}

    for session_id, start_event in session_starts.items():
        project = start_event.get("project_name", "unknown")

        # Initialize project stats
        if project not in by_project:
            by_project[project] = {"sessions": 0, "duration_minutes": 0}

        by_project[project]["sessions"] += 1

        # Check if session has ended
        if session_id in session_ends:
            end_event = session_ends[session_id]
            duration = end_event.get("actual_duration_minutes", 0)
            total_duration_minutes += duration
            by_project[project]["duration_minutes"] += duration
        else:
            incomplete_sessions += 1

    return StatsReport(
        total_sessions=total_sessions,
        total_duration_minutes=total_duration_minutes,
        incomplete_sessions=incomplete_sessions,
        by_project=by_project,
        period_start=period_start if days is not None else datetime.min,
        period_end=period_end,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Export Functions
# ═══════════════════════════════════════════════════════════════════════════════


def export_stats(days: int | None = None) -> str:
    """Export aggregated stats as JSON.

    Args:
        days: Number of days to include (None for all time)

    Returns:
        JSON string of StatsReport
    """
    report = get_stats(days=days)
    return json.dumps(report.to_dict(), indent=2)


def export_raw_events() -> str:
    """Export raw events as JSON array.

    Returns:
        JSON string containing array of all events
    """
    events = read_usage_events()
    return json.dumps(events, indent=2)


# ═══════════════════════════════════════════════════════════════════════════════
# Session ID Generation
# ═══════════════════════════════════════════════════════════════════════════════


def generate_session_id() -> str:
    """Generate a unique session ID.

    Returns:
        UUID string for session identification
    """
    return str(uuid.uuid4())
