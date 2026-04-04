"""Characterization tests for commands/config.py.

Lock current behavior of pure helper functions: enforcement status
entry construction, serialization, and advisory warning collection.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from scc_cli.commands.config import (
    EnforcementStatusEntry,
    _collect_advisory_warnings,
    _serialize_enforcement_status_entries,
)

# ═══════════════════════════════════════════════════════════════════════════════
# EnforcementStatusEntry
# ═══════════════════════════════════════════════════════════════════════════════


class TestEnforcementStatusEntry:
    """Frozen dataclass for enforcement display."""

    def test_construction(self) -> None:
        entry = EnforcementStatusEntry(
            surface="plugins",
            status="enforced",
            detail="All plugins validated",
        )
        assert entry.surface == "plugins"
        assert entry.status == "enforced"
        assert entry.detail == "All plugins validated"


class TestSerializeEnforcementStatusEntries:
    """Serialization for JSON output."""

    def test_empty_list(self) -> None:
        assert _serialize_enforcement_status_entries([]) == []

    def test_single_entry(self) -> None:
        entries = [
            EnforcementStatusEntry(
                surface="network_policy",
                status="active",
                detail="Proxy configured",
            )
        ]
        result = _serialize_enforcement_status_entries(entries)
        assert len(result) == 1
        assert result[0]["surface"] == "network_policy"
        assert result[0]["status"] == "active"
        assert result[0]["detail"] == "Proxy configured"

    def test_multiple_entries(self) -> None:
        entries = [
            EnforcementStatusEntry("a", "active", "detail-a"),
            EnforcementStatusEntry("b", "inactive", "detail-b"),
        ]
        result = _serialize_enforcement_status_entries(entries)
        assert len(result) == 2
        assert result[0]["surface"] == "a"
        assert result[1]["surface"] == "b"


# ═══════════════════════════════════════════════════════════════════════════════
# _collect_advisory_warnings
# ═══════════════════════════════════════════════════════════════════════════════


class TestCollectAdvisoryWarnings:
    """Advisory warning collection for config validate display."""

    def test_no_warnings_for_minimal_config(self, tmp_path: Path) -> None:
        with patch("scc_cli.commands.config.config") as mock_config:
            mock_config.read_project_config.return_value = None
            warnings = _collect_advisory_warnings(
                org_config={},
                team_name="team-a",
                workspace_path=tmp_path,
                effective_network_policy=None,
            )
        assert warnings == []

    def test_auto_resume_advisory(self, tmp_path: Path) -> None:
        with patch("scc_cli.commands.config.config") as mock_config:
            mock_config.read_project_config.return_value = None
            warnings = _collect_advisory_warnings(
                org_config={
                    "defaults": {"session": {"auto_resume": True}},
                },
                team_name="team-a",
                workspace_path=tmp_path,
                effective_network_policy=None,
            )
        assert any("auto_resume" in w and "advisory" in w for w in warnings)

    def test_team_less_restrictive_warning(self, tmp_path: Path) -> None:
        with patch("scc_cli.commands.config.config") as mock_config:
            mock_config.read_project_config.return_value = None
            warnings = _collect_advisory_warnings(
                org_config={
                    "defaults": {"network_policy": "locked-down-web"},
                    "profiles": {"team-a": {"network_policy": "open"}},
                },
                team_name="team-a",
                workspace_path=tmp_path,
                effective_network_policy=None,
            )
        assert any("less restrictive" in w for w in warnings)

    def test_web_egress_no_proxy_warning(self, tmp_path: Path) -> None:
        with (
            patch("scc_cli.commands.config.config") as mock_config,
            patch("scc_cli.commands.config.collect_proxy_env", return_value={}),
        ):
            mock_config.read_project_config.return_value = None
            warnings = _collect_advisory_warnings(
                org_config={},
                team_name="team-a",
                workspace_path=tmp_path,
                effective_network_policy="web-egress-enforced",
            )
        assert any("proxy" in w.lower() for w in warnings)
