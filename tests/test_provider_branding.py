"""Tests for provider display helpers and provider-neutral branding."""

from __future__ import annotations

from unittest.mock import patch

from scc_cli.core.provider_resolution import get_provider_display_name
from scc_cli.ui.branding import get_brand_tagline, get_version_header


# ── get_provider_display_name ────────────────────────────────────────────────


class TestGetProviderDisplayName:
    def test_claude_returns_claude_code(self) -> None:
        assert get_provider_display_name("claude") == "Claude Code"

    def test_codex_returns_codex(self) -> None:
        assert get_provider_display_name("codex") == "Codex"

    def test_unknown_provider_returns_title_cased(self) -> None:
        assert get_provider_display_name("unknown") == "Unknown"

    def test_multi_word_unknown_provider(self) -> None:
        assert get_provider_display_name("my-agent") == "My-Agent"


# ── get_version_header ───────────────────────────────────────────────────────


class TestGetVersionHeader:
    @patch("scc_cli.ui.branding.supports_unicode", return_value=True)
    def test_header_says_sandboxed_code_cli_unicode(self, _mock: object) -> None:
        header = get_version_header("1.7.3")
        assert "Sandboxed Code CLI" in header
        assert "Claude" not in header

    @patch("scc_cli.ui.branding.supports_unicode", return_value=False)
    def test_header_says_sandboxed_code_cli_ascii(self, _mock: object) -> None:
        header = get_version_header("1.7.3")
        assert "Sandboxed Code CLI" in header
        assert "Claude" not in header


# ── get_brand_tagline ────────────────────────────────────────────────────────


class TestGetBrandTagline:
    def test_default_tagline_is_provider_neutral(self) -> None:
        tagline = get_brand_tagline()
        assert tagline == "Safe development environment manager"
        assert "Claude" not in tagline

    def test_tagline_with_claude_provider(self) -> None:
        tagline = get_brand_tagline(provider_id="claude")
        assert tagline == "Safe development environment manager for Claude Code"

    def test_tagline_with_codex_provider(self) -> None:
        tagline = get_brand_tagline(provider_id="codex")
        assert tagline == "Safe development environment manager for Codex"

    def test_tagline_with_unknown_provider(self) -> None:
        tagline = get_brand_tagline(provider_id="custom")
        assert "Custom" in tagline
