"""Tests for provider display helpers and provider-neutral branding."""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock, patch

from rich.console import Console
from rich.panel import Panel

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
    def test_header_says_sandboxed_coding_cli_unicode(self, _mock: object) -> None:
        header = get_version_header("1.7.3")
        assert "Sandboxed Coding CLI" in header
        assert "Claude" not in header

    @patch("scc_cli.ui.branding.supports_unicode", return_value=False)
    def test_header_says_sandboxed_coding_cli_ascii(self, _mock: object) -> None:
        header = get_version_header("1.7.3")
        assert "Sandboxed Coding CLI" in header
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


# ── show_launch_panel ────────────────────────────────────────────────────────


def _capture_panel_title(fn: object, *args: object, **kwargs: object) -> str:
    """Call a render function and return the Panel title from the first Panel printed."""
    panels: list[Panel] = []

    def capturing_layout(*a: object, **kw: object) -> None:
        for arg in a:
            if isinstance(arg, Panel):
                panels.append(arg)

    with patch("scc_cli.commands.launch.render.console") as mock_console:
        mock_console.print = MagicMock()
        with patch("scc_cli.commands.launch.render.print_with_layout", capturing_layout):
            fn(*args, **kwargs)  # type: ignore[operator]

    assert panels, "No Panel was printed"
    title = panels[0].title
    # Rich title is a Text or str; convert to plain string
    return str(title) if title else ""


class TestShowLaunchPanel:
    """show_launch_panel() adapts the panel title to display_name."""

    def test_default_display_name_is_claude_code(self) -> None:
        from scc_cli.commands.launch.render import show_launch_panel

        title = _capture_panel_title(
            show_launch_panel,
            workspace=Path("/tmp/ws"),
            team=None,
            session_name=None,
            branch=None,
            is_resume=False,
        )
        assert "Launching Claude Code" in title

    def test_codex_display_name(self) -> None:
        from scc_cli.commands.launch.render import show_launch_panel

        title = _capture_panel_title(
            show_launch_panel,
            workspace=Path("/tmp/ws"),
            team=None,
            session_name=None,
            branch=None,
            is_resume=False,
            display_name="Codex",
        )
        assert "Launching Codex" in title

    def test_custom_display_name(self) -> None:
        from scc_cli.commands.launch.render import show_launch_panel

        title = _capture_panel_title(
            show_launch_panel,
            workspace=Path("/tmp/ws"),
            team=None,
            session_name=None,
            branch=None,
            is_resume=False,
            display_name="My Agent",
        )
        assert "Launching My Agent" in title


# ── show_launch_context_panel ────────────────────────────────────────────────


class TestShowLaunchContextPanel:
    """show_launch_context_panel() adapts the panel title to display_name."""

    def _make_ctx(self) -> MagicMock:
        ctx = MagicMock()
        ctx.workspace_root = Path("/tmp/ws")
        ctx.entry_dir = Path("/tmp/ws")
        ctx.entry_dir_relative = "."
        ctx.mount_root = Path("/tmp/ws")
        ctx.container_workdir = "/tmp/ws"
        ctx.team = None
        ctx.branch = None
        ctx.session_name = None
        ctx.mode = "new"
        return ctx

    def test_default_title_is_claude_code(self) -> None:
        from scc_cli.commands.launch.render import show_launch_context_panel

        title = _capture_panel_title(show_launch_context_panel, self._make_ctx())
        assert "Launching Claude Code" in title

    def test_codex_title(self) -> None:
        from scc_cli.commands.launch.render import show_launch_context_panel

        title = _capture_panel_title(
            show_launch_context_panel,
            self._make_ctx(),
            display_name="Codex",
        )
        assert "Launching Codex" in title


# ── render_doctor_results ────────────────────────────────────────────────────


class TestRenderDoctorResults:
    """render_doctor_results() adapts the summary line to provider_id."""

    def _make_ok_result(self) -> MagicMock:
        result = MagicMock()
        result.all_ok = True
        result.checks = []
        result.error_count = 0
        result.warning_count = 0
        return result

    def test_default_summary_says_claude_code(self) -> None:
        from scc_cli.doctor.render import render_doctor_results

        buf = Console(file=__import__("io").StringIO(), force_terminal=True)
        render_doctor_results(buf, self._make_ok_result())
        output = buf.file.getvalue()  # type: ignore[union-attr]
        assert "Claude Code" in output

    def test_codex_summary(self) -> None:
        from scc_cli.doctor.render import render_doctor_results

        buf = Console(file=__import__("io").StringIO(), force_terminal=True)
        render_doctor_results(buf, self._make_ok_result(), provider_id="codex")
        output = buf.file.getvalue()  # type: ignore[union-attr]
        assert "Codex" in output
        assert "Claude Code" not in output


# ── Guardrail: no "Claude Code" in non-adapter user-facing code ─────────────

# Directories and file prefixes that are allowed to mention "Claude Code"
# because they are Claude-specific adapters or infrastructure.
_ALLOWED_DIRS = {"adapters", "docker", "marketplace"}
_ALLOWED_PREFIXES = {"claude_"}

# Files that legitimately contain the string as a lookup value or default
_ALLOWED_FILES = {
    "provider_resolution.py",  # lookup table mapping "claude" -> "Claude Code"
    "provider_registry.py",  # registry data: display_name is a factual field, not UI copy
}

# Pattern for default parameter values like `display_name: str = "Claude Code"`
# These are acceptable because the default is overridden at call sites.
_DEFAULT_PARAM_RE = re.compile(r'display_name:\s*str\s*=\s*"Claude Code"')


class TestNoCloudeCodeInNonAdapterModules:
    """Guardrail: scan src/scc_cli/ for 'Claude Code' or 'Sandboxed Claude'
    outside adapter/infrastructure modules. Any unexpected match fails the test.
    """

    def _collect_violations(self) -> list[str]:
        src_root = Path(__file__).resolve().parent.parent / "src" / "scc_cli"
        violations: list[str] = []

        for py_file in sorted(src_root.rglob("*.py")):
            rel = py_file.relative_to(src_root)
            parts = rel.parts

            # Skip __pycache__
            if "__pycache__" in parts:
                continue

            # Skip allowed directories
            if parts[0] in _ALLOWED_DIRS:
                continue

            # Skip files with allowed prefixes (e.g. claude_renderer.py)
            if any(parts[-1].startswith(p) for p in _ALLOWED_PREFIXES):
                continue

            # Skip allowed individual files
            if parts[-1] in _ALLOWED_FILES:
                continue

            try:
                content = py_file.read_text(encoding="utf-8")
            except OSError:
                continue

            for lineno, line in enumerate(content.splitlines(), start=1):
                # Skip default parameter values — these are overridden at call sites
                if _DEFAULT_PARAM_RE.search(line):
                    continue

                if "Claude Code" in line or "Sandboxed Claude" in line:
                    violations.append(f"{rel}:{lineno}: {line.strip()}")

        return violations

    def test_no_claude_code_references(self) -> None:
        violations = self._collect_violations()
        assert violations == [], (
            "Found 'Claude Code' or 'Sandboxed Claude' in non-adapter modules:\n"
            + "\n".join(f"  {v}" for v in violations)
        )
