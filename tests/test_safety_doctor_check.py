"""Tests for doctor.checks.safety — safety-policy doctor check."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

from scc_cli.core.enums import SeverityLevel
from scc_cli.doctor.checks.safety import check_safety_policy

_PATCH_TARGET = "scc_cli.doctor.checks.safety._load_raw_org_config"


def _org(safety_net: dict[str, Any]) -> dict[str, Any]:
    """Build a minimal org config dict."""
    return {"security": {"safety_net": safety_net}}


class TestCheckSafetyPolicy:
    """Covers the four documented scenarios: valid config, no config, no section, malformed."""

    @patch(_PATCH_TARGET)
    def test_check_passes_with_valid_org_config(self, mock_load: Any) -> None:
        mock_load.return_value = _org({"action": "warn"})
        result = check_safety_policy()
        assert result.passed is True
        assert "warn" in result.message

    @patch(_PATCH_TARGET)
    def test_check_warns_when_no_org_config(self, mock_load: Any) -> None:
        mock_load.return_value = None
        result = check_safety_policy()
        assert result.passed is True
        assert result.severity == SeverityLevel.WARNING
        assert "No org config" in result.message

    @patch(_PATCH_TARGET)
    def test_check_warns_when_no_safety_net_section(self, mock_load: Any) -> None:
        mock_load.return_value = {"security": {"other": True}}
        result = check_safety_policy()
        assert result.passed is True
        assert result.severity == SeverityLevel.WARNING
        assert "No safety_net section" in result.message

    @patch(_PATCH_TARGET)
    def test_check_errors_on_invalid_action(self, mock_load: Any) -> None:
        mock_load.return_value = _org({"action": "yolo"})
        result = check_safety_policy()
        assert result.passed is False
        assert result.severity == SeverityLevel.ERROR
        assert "yolo" in result.message
        assert result.fix_hint is not None

    @patch(_PATCH_TARGET)
    def test_check_errors_on_malformed_org_config(self, mock_load: Any) -> None:
        mock_load.side_effect = RuntimeError("corrupt cache")
        result = check_safety_policy()
        assert result.passed is False
        assert result.severity == SeverityLevel.ERROR
        assert "Unexpected error" in result.message

    @patch(_PATCH_TARGET)
    def test_check_passes_with_block_action(self, mock_load: Any) -> None:
        mock_load.return_value = _org({"action": "block"})
        result = check_safety_policy()
        assert result.passed is True
        assert "block" in result.message

    @patch(_PATCH_TARGET)
    def test_check_passes_with_allow_action(self, mock_load: Any) -> None:
        mock_load.return_value = _org({"action": "allow"})
        result = check_safety_policy()
        assert result.passed is True
        assert "allow" in result.message
