"""Characterization tests for setup.py.

Lock the current behavior of pure helper functions in the setup wizard
before S02 surgery. Targets: config preview building, proposed config
assembly, dotted-path config access, and config diff rendering.
"""

from __future__ import annotations

from typing import Any

from scc_cli.setup import (
    _build_config_changes,
    _build_config_preview,
    _build_proposed_config,
    _format_preview_value,
    _get_config_value,
)

# ═══════════════════════════════════════════════════════════════════════════════
# _format_preview_value
# ═══════════════════════════════════════════════════════════════════════════════


class TestFormatPreviewValue:
    """Em-dash sentinel for unset values."""

    def test_none_returns_em_dash(self) -> None:
        assert _format_preview_value(None) == "—"

    def test_empty_string_returns_em_dash(self) -> None:
        assert _format_preview_value("") == "—"

    def test_value_returned_as_is(self) -> None:
        assert _format_preview_value("https://example.com") == "https://example.com"

    def test_whitespace_preserved(self) -> None:
        assert _format_preview_value("  spaced  ") == "  spaced  "


# ═══════════════════════════════════════════════════════════════════════════════
# _get_config_value
# ═══════════════════════════════════════════════════════════════════════════════


class TestGetConfigValue:
    """Dotted-path access into nested config dicts."""

    def test_top_level_key(self) -> None:
        assert _get_config_value({"standalone": True}, "standalone") == "True"

    def test_nested_key(self) -> None:
        cfg = {"organization_source": {"url": "https://example.com"}}
        assert _get_config_value(cfg, "organization_source.url") == "https://example.com"

    def test_missing_key_returns_none(self) -> None:
        assert _get_config_value({}, "nonexistent") is None

    def test_missing_nested_key_returns_none(self) -> None:
        assert _get_config_value({"a": {}}, "a.b") is None

    def test_none_value_returns_none(self) -> None:
        assert _get_config_value({"key": None}, "key") is None

    def test_deep_nesting(self) -> None:
        cfg: dict[str, Any] = {"a": {"b": {"c": "deep"}}}
        assert _get_config_value(cfg, "a.b.c") == "deep"


# ═══════════════════════════════════════════════════════════════════════════════
# _build_proposed_config
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildProposedConfig:
    """Config dict assembly for write operations."""

    def test_standalone_mode(self) -> None:
        cfg = _build_proposed_config(
            org_url=None,
            auth=None,
            auth_header=None,
            profile=None,
            hooks_enabled=True,
            standalone=True,
        )
        assert cfg["standalone"] is True
        assert cfg["organization_source"] is None
        assert cfg["hooks"]["enabled"] is True
        assert cfg["config_version"] == "1.0.0"

    def test_organization_mode(self) -> None:
        cfg = _build_proposed_config(
            org_url="https://example.com/config.json",
            auth="env:SCC_TOKEN",
            auth_header=None,
            profile="team-alpha",
            hooks_enabled=False,
            standalone=False,
        )
        assert "standalone" not in cfg
        assert cfg["organization_source"]["url"] == "https://example.com/config.json"
        assert cfg["organization_source"]["auth"] == "env:SCC_TOKEN"
        assert cfg["selected_profile"] == "team-alpha"
        assert cfg["hooks"]["enabled"] is False

    def test_organization_mode_with_auth_header(self) -> None:
        cfg = _build_proposed_config(
            org_url="https://example.com",
            auth="env:TOKEN",
            auth_header="X-Custom-Auth",
            profile="team-a",
            hooks_enabled=True,
            standalone=False,
        )
        assert cfg["organization_source"]["auth_header"] == "X-Custom-Auth"

    def test_organization_mode_no_url(self) -> None:
        cfg = _build_proposed_config(
            org_url=None,
            auth=None,
            auth_header=None,
            profile=None,
            hooks_enabled=True,
            standalone=False,
        )
        # No org_url means no organization_source key at all
        assert "organization_source" not in cfg or cfg.get("organization_source") is None


# ═══════════════════════════════════════════════════════════════════════════════
# _build_config_preview (Rich Text)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildConfigPreview:
    """Config preview Rich Text output shape."""

    def test_standalone_preview_contains_mode(self) -> None:
        preview = _build_config_preview(
            org_url=None,
            auth=None,
            auth_header=None,
            profile=None,
            hooks_enabled=True,
            standalone=True,
        )
        text = preview.plain
        assert "standalone" in text.lower()

    def test_organization_preview_contains_url(self) -> None:
        preview = _build_config_preview(
            org_url="https://example.com/config.json",
            auth="env:TOKEN",
            auth_header=None,
            profile="team-a",
            hooks_enabled=False,
            standalone=False,
        )
        text = preview.plain
        assert "org.url" in text
        assert "example.com" in text
        assert "team-a" in text


# ═══════════════════════════════════════════════════════════════════════════════
# _build_config_changes (Rich Text diff)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBuildConfigChanges:
    """Config diff rendering for before/after comparison."""

    def test_no_changes_detected(self) -> None:
        cfg = {"standalone": True, "hooks": {"enabled": True}}
        changes = _build_config_changes(cfg, cfg)
        assert "no changes" in changes.plain.lower()

    def test_changes_shown(self) -> None:
        before: dict[str, Any] = {"standalone": True}
        after: dict[str, Any] = {"standalone": False}
        changes = _build_config_changes(before, after)
        text = changes.plain
        assert "standalone" in text

    def test_url_change(self) -> None:
        before: dict[str, Any] = {"organization_source": {"url": "https://old.com"}}
        after: dict[str, Any] = {"organization_source": {"url": "https://new.com"}}
        changes = _build_config_changes(before, after)
        text = changes.plain
        assert "old.com" in text
        assert "new.com" in text
