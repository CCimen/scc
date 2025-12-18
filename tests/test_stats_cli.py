"""Tests for stats CLI commands.

TDD tests for Task 2.3 - CLI Commands for usage statistics.

Commands to implement:
- scc stats: Show user's own usage statistics
- scc stats export --json: Export stats as JSON
- scc stats aggregate: Aggregate multiple stats files
"""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from scc_cli import cli, stats

runner = CliRunner()


# ═══════════════════════════════════════════════════════════════════════════════
# Test fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_stats_report():
    """Create a mock StatsReport for testing."""
    return stats.StatsReport(
        total_sessions=5,
        total_duration_minutes=240,
        incomplete_sessions=1,
        by_project={
            "project-a": {"sessions": 3, "duration_minutes": 180},
            "project-b": {"sessions": 2, "duration_minutes": 60},
        },
        period_start=datetime(2024, 1, 1),
        period_end=datetime(2024, 1, 31),
    )


@pytest.fixture
def sample_events():
    """Sample events for testing."""
    return [
        {
            "event_type": "session_start",
            "session_id": "abc123",
            "timestamp": "2024-01-15T10:00:00",
            "project_name": "project-a",
            "team_name": "dev",
            "expected_duration_hours": 8,
            "user_id_hash": "hash123",
        },
        {
            "event_type": "session_end",
            "session_id": "abc123",
            "timestamp": "2024-01-15T14:00:00",
            "actual_duration_minutes": 240,
            "exit_status": "clean",
        },
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for scc stats command
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatsCommand:
    """Tests for `scc stats` command showing user's statistics."""

    def test_stats_shows_summary(self, mock_stats_report):
        """Should display summary of user's usage statistics."""
        with patch("scc_cli.cli_admin.stats.get_stats", return_value=mock_stats_report):
            result = runner.invoke(cli.app, ["stats"])

        assert result.exit_code == 0
        assert "5" in result.output  # total sessions
        assert "240" in result.output or "4" in result.output  # duration (minutes or hours)

    def test_stats_shows_project_breakdown(self, mock_stats_report):
        """Should show per-project breakdown."""
        with patch("scc_cli.cli_admin.stats.get_stats", return_value=mock_stats_report):
            result = runner.invoke(cli.app, ["stats"])

        assert result.exit_code == 0
        assert "project-a" in result.output
        assert "project-b" in result.output

    def test_stats_shows_incomplete_sessions(self, mock_stats_report):
        """Should indicate incomplete sessions."""
        with patch("scc_cli.cli_admin.stats.get_stats", return_value=mock_stats_report):
            result = runner.invoke(cli.app, ["stats"])

        assert result.exit_code == 0
        assert "incomplete" in result.output.lower() or "1" in result.output

    def test_stats_with_days_filter(self, mock_stats_report):
        """Should accept --days filter."""
        with patch("scc_cli.cli_admin.stats.get_stats", return_value=mock_stats_report) as mock_get:
            result = runner.invoke(cli.app, ["stats", "--days", "7"])

        assert result.exit_code == 0
        mock_get.assert_called_once_with(days=7)

    def test_stats_empty_no_sessions(self):
        """Should handle no sessions gracefully."""
        empty_report = stats.StatsReport(
            total_sessions=0,
            total_duration_minutes=0,
            incomplete_sessions=0,
            by_project={},
            period_start=datetime.min,
            period_end=datetime.now(),
        )
        with patch("scc_cli.cli_admin.stats.get_stats", return_value=empty_report):
            result = runner.invoke(cli.app, ["stats"])

        assert result.exit_code == 0
        # Should show message about no sessions
        assert "no" in result.output.lower() or "0" in result.output


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for scc stats export command
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatsExportCommand:
    """Tests for `scc stats export` command."""

    def test_export_json_outputs_valid_json(self, mock_stats_report):
        """Should output valid JSON."""
        with patch("scc_cli.cli_admin.stats.get_stats", return_value=mock_stats_report):
            result = runner.invoke(cli.app, ["stats", "export", "--json"])

        assert result.exit_code == 0
        # Should be valid JSON
        data = json.loads(result.output)
        assert "total_sessions" in data
        assert data["total_sessions"] == 5

    def test_export_json_with_days_filter(self, mock_stats_report):
        """Should accept --days filter for export."""
        with patch("scc_cli.cli_admin.stats.get_stats", return_value=mock_stats_report) as mock_get:
            result = runner.invoke(cli.app, ["stats", "export", "--json", "--days", "30"])

        assert result.exit_code == 0
        mock_get.assert_called_once_with(days=30)

    def test_export_raw_events(self, sample_events):
        """Should export raw events when --raw flag is used."""
        with patch("scc_cli.cli_admin.stats.read_usage_events", return_value=sample_events):
            result = runner.invoke(cli.app, ["stats", "export", "--raw"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["event_type"] == "session_start"

    def test_export_to_file(self, mock_stats_report, tmp_path):
        """Should export to file when --output is specified."""
        output_file = tmp_path / "stats.json"
        with patch("scc_cli.cli_admin.stats.get_stats", return_value=mock_stats_report):
            result = runner.invoke(
                cli.app, ["stats", "export", "--json", "--output", str(output_file)]
            )

        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data["total_sessions"] == 5


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for scc stats aggregate command
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatsAggregateCommand:
    """Tests for `scc stats aggregate` command."""

    def test_aggregate_multiple_files(self, tmp_path):
        """Should aggregate multiple JSON stats files."""
        # Create two stats files
        file1 = tmp_path / "stats1.json"
        file1.write_text(
            json.dumps(
                {
                    "total_sessions": 5,
                    "total_duration_minutes": 240,
                    "incomplete_sessions": 1,
                    "by_project": {"project-a": {"sessions": 5, "duration_minutes": 240}},
                    "period_start": "2024-01-01T00:00:00",
                    "period_end": "2024-01-31T23:59:59",
                }
            )
        )

        file2 = tmp_path / "stats2.json"
        file2.write_text(
            json.dumps(
                {
                    "total_sessions": 3,
                    "total_duration_minutes": 120,
                    "incomplete_sessions": 0,
                    "by_project": {"project-b": {"sessions": 3, "duration_minutes": 120}},
                    "period_start": "2024-01-01T00:00:00",
                    "period_end": "2024-01-31T23:59:59",
                }
            )
        )

        result = runner.invoke(cli.app, ["stats", "aggregate", str(file1), str(file2)])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_sessions"] == 8
        assert data["total_duration_minutes"] == 360
        assert "project-a" in data["by_project"]
        assert "project-b" in data["by_project"]

    def test_aggregate_empty_list_error(self):
        """Should error when no files provided."""
        result = runner.invoke(cli.app, ["stats", "aggregate"])

        # Should exit with error
        assert result.exit_code != 0

    def test_aggregate_invalid_file_error(self, tmp_path):
        """Should handle invalid file gracefully."""
        bad_file = tmp_path / "invalid.json"
        bad_file.write_text("not json")

        result = runner.invoke(cli.app, ["stats", "aggregate", str(bad_file)])

        assert result.exit_code != 0
        assert "error" in result.output.lower() or "invalid" in result.output.lower()

    def test_aggregate_missing_file_error(self, tmp_path):
        """Should handle missing file gracefully."""
        missing = tmp_path / "missing.json"

        result = runner.invoke(cli.app, ["stats", "aggregate", str(missing)])

        assert result.exit_code != 0

    def test_aggregate_output_to_file(self, tmp_path):
        """Should output aggregated stats to file when --output specified."""
        # Create input file
        file1 = tmp_path / "stats1.json"
        file1.write_text(
            json.dumps(
                {
                    "total_sessions": 5,
                    "total_duration_minutes": 240,
                    "incomplete_sessions": 1,
                    "by_project": {"project-a": {"sessions": 5, "duration_minutes": 240}},
                    "period_start": "2024-01-01T00:00:00",
                    "period_end": "2024-01-31T23:59:59",
                }
            )
        )

        output_file = tmp_path / "aggregated.json"
        result = runner.invoke(
            cli.app, ["stats", "aggregate", str(file1), "--output", str(output_file)]
        )

        assert result.exit_code == 0
        assert output_file.exists()
        data = json.loads(output_file.read_text())
        assert data["total_sessions"] == 5

    def test_aggregate_glob_pattern(self, tmp_path):
        """Should support glob patterns for input files."""
        # Create multiple stats files
        for i in range(3):
            file = tmp_path / f"stats{i}.json"
            file.write_text(
                json.dumps(
                    {
                        "total_sessions": 2,
                        "total_duration_minutes": 60,
                        "incomplete_sessions": 0,
                        "by_project": {f"project-{i}": {"sessions": 2, "duration_minutes": 60}},
                        "period_start": "2024-01-01T00:00:00",
                        "period_end": "2024-01-31T23:59:59",
                    }
                )
            )

        result = runner.invoke(cli.app, ["stats", "aggregate", str(tmp_path / "stats*.json")])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_sessions"] == 6  # 2 * 3 files


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for stats help and error handling
# ═══════════════════════════════════════════════════════════════════════════════


class TestStatsHelpAndErrors:
    """Tests for help messages and error handling."""

    def test_stats_help(self):
        """Should show help for stats command."""
        result = runner.invoke(cli.app, ["stats", "--help"])

        assert result.exit_code == 0
        assert "stats" in result.output.lower()

    def test_stats_export_help(self):
        """Should show help for stats export command."""
        result = runner.invoke(cli.app, ["stats", "export", "--help"])

        assert result.exit_code == 0
        assert "export" in result.output.lower() or "json" in result.output.lower()

    def test_stats_aggregate_help(self):
        """Should show help for stats aggregate command."""
        result = runner.invoke(cli.app, ["stats", "aggregate", "--help"])

        assert result.exit_code == 0
        assert "aggregate" in result.output.lower()
