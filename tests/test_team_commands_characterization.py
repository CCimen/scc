"""Characterization tests for commands/team.py.

Lock the current behavior of pure helper functions before S02 surgery:
plugin display formatting, path detection heuristic, and team config
file validation.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scc_cli.commands.team import (
    _format_plugins_for_display,
    _looks_like_path,
    _validate_team_config_file,
)

# ═══════════════════════════════════════════════════════════════════════════════
# _format_plugins_for_display
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormatPluginsForDisplay:
    """Plugin list truncation for table display."""

    def test_empty_list(self) -> None:
        result = _format_plugins_for_display([])
        assert result == "-"

    def test_single_plugin(self) -> None:
        result = _format_plugins_for_display(["tool@marketplace"])
        assert "tool" in result

    def test_two_plugins_under_limit(self) -> None:
        result = _format_plugins_for_display(["a@mp", "b@mp"], max_display=2)
        assert "a" in result
        assert "b" in result

    def test_truncation_with_count(self) -> None:
        plugins = ["a@mp", "b@mp", "c@mp", "d@mp"]
        result = _format_plugins_for_display(plugins, max_display=2)
        assert "+2 more" in result

    def test_strips_marketplace_suffix(self) -> None:
        result = _format_plugins_for_display(["my-plugin@org-marketplace"])
        assert "my-plugin" in result
        assert "@" not in result


# ═══════════════════════════════════════════════════════════════════════════════
# _looks_like_path
# ═══════════════════════════════════════════════════════════════════════════════


class TestLooksLikePath:
    """Heuristic path detection."""

    def test_unix_path(self) -> None:
        assert _looks_like_path("/etc/config.json") is True

    def test_windows_path(self) -> None:
        assert _looks_like_path("C:\\Users\\config.json") is True

    def test_home_tilde(self) -> None:
        assert _looks_like_path("~/config.json") is True

    def test_json_extension(self) -> None:
        assert _looks_like_path("config.json") is True

    def test_jsonc_extension(self) -> None:
        assert _looks_like_path("config.jsonc") is True

    def test_json5_extension(self) -> None:
        assert _looks_like_path("config.json5") is True

    def test_plain_name_not_path(self) -> None:
        assert _looks_like_path("team-alpha") is False

    def test_url_not_path(self) -> None:
        # URLs contain / so they match the heuristic
        assert _looks_like_path("https://example.com/config") is True


# ═══════════════════════════════════════════════════════════════════════════════
# _validate_team_config_file
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateTeamConfigFile:
    """Team config file validation against schema."""

    def test_file_not_found(self, tmp_path: Path) -> None:
        result = _validate_team_config_file(str(tmp_path / "nonexistent.json"), verbose=False)
        assert result["valid"] is False
        assert "not found" in result["error"].lower()
        assert result["mode"] == "file"

    def test_invalid_json(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{not valid json")
        result = _validate_team_config_file(str(bad_file), verbose=False)
        assert result["valid"] is False
        assert "json" in result["error"].lower()

    def test_valid_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / "team.json"
        config_data: dict[str, Any] = {
            "schema_version": "1.0.0",
            "team_name": "test-team",
            "profiles": {},
        }
        config_file.write_text(json.dumps(config_data))
        result = _validate_team_config_file(str(config_file), verbose=False)
        # Note: validity depends on validate_team_config — we lock current behavior
        assert result["mode"] == "file"
        assert "source" in result
        assert isinstance(result["valid"], bool)

    def test_schema_version_included_when_present(self, tmp_path: Path) -> None:
        config_file = tmp_path / "team.json"
        config_data: dict[str, Any] = {"schema_version": "2.0.0"}
        config_file.write_text(json.dumps(config_data))
        result = _validate_team_config_file(str(config_file), verbose=False)
        assert result.get("schema_version") == "2.0.0"
