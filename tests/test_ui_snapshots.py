"""UI Snapshot Tests (A.7) - Structural regression tests for UI components.

These tests verify UI structure WITHOUT exact pixel matching. This prevents
tests from breaking on minor styling changes while ensuring key elements
are present.

Philosophy:
- Assert on substrings and presence, not exact rendering
- Test that key elements exist, not their exact format
- Use fixed-width console for consistent output
"""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from scc_cli.panels import (
    create_error_panel,
    create_info_panel,
    create_success_panel,
    create_warning_panel,
)


def render_to_string(renderable: object) -> str:
    """Capture Rich renderable to string for testing.

    Uses fixed width for consistent output across environments.
    """
    console = Console(file=StringIO(), force_terminal=True, width=80)
    console.print(renderable)
    return console.file.getvalue()  # type: ignore[union-attr]


class TestInfoPanelSnapshots:
    """Structural tests for create_info_panel()."""

    def test_info_panel_contains_title(self) -> None:
        """Info panel includes the title."""
        panel = create_info_panel("Important Notice", "Check your settings")
        rendered = render_to_string(panel)

        assert "Important Notice" in rendered

    def test_info_panel_contains_content(self) -> None:
        """Info panel includes the content text."""
        panel = create_info_panel("Notice", "Please review the configuration")
        rendered = render_to_string(panel)

        assert "review the configuration" in rendered

    def test_info_panel_contains_subtitle_when_provided(self) -> None:
        """Info panel includes subtitle when provided."""
        panel = create_info_panel("Notice", "Content here", subtitle="v1.2.0")
        rendered = render_to_string(panel)

        assert "v1.2.0" in rendered


class TestWarningPanelSnapshots:
    """Structural tests for create_warning_panel()."""

    def test_warning_panel_contains_title(self) -> None:
        """Warning panel includes the title."""
        panel = create_warning_panel("Deprecation Warning", "This feature is deprecated")
        rendered = render_to_string(panel)

        assert "Deprecation Warning" in rendered

    def test_warning_panel_contains_message(self) -> None:
        """Warning panel includes the warning message."""
        panel = create_warning_panel("Warning", "Please update your config")
        rendered = render_to_string(panel)

        assert "update your config" in rendered

    def test_warning_panel_contains_hint_when_provided(self) -> None:
        """Warning panel includes hint when provided."""
        panel = create_warning_panel("Warning", "Issue detected", hint="Run scc doctor")
        rendered = render_to_string(panel)

        assert "scc doctor" in rendered


class TestSuccessPanelSnapshots:
    """Structural tests for create_success_panel()."""

    def test_success_panel_contains_title(self) -> None:
        """Success panel includes the title."""
        panel = create_success_panel("Setup Complete", {"status": "ready"})
        rendered = render_to_string(panel)

        assert "Setup Complete" in rendered

    def test_success_panel_contains_item_keys(self) -> None:
        """Success panel includes all item keys."""
        panel = create_success_panel(
            "Configuration",
            {"workspace": "/path/to/project", "profile": "default"},
        )
        rendered = render_to_string(panel)

        assert "workspace" in rendered
        assert "profile" in rendered

    def test_success_panel_contains_item_values(self) -> None:
        """Success panel includes all item values."""
        panel = create_success_panel(
            "Ready",
            {"team": "platform", "branch": "feature/auth"},
        )
        rendered = render_to_string(panel)

        assert "platform" in rendered
        assert "feature/auth" in rendered


class TestErrorPanelSnapshots:
    """Structural tests for create_error_panel()."""

    def test_error_panel_contains_title(self) -> None:
        """Error panel includes the title."""
        panel = create_error_panel("Connection Failed", "Unable to reach server")
        rendered = render_to_string(panel)

        assert "Connection Failed" in rendered

    def test_error_panel_contains_message(self) -> None:
        """Error panel includes the error message."""
        panel = create_error_panel("Error", "Docker is not running")
        rendered = render_to_string(panel)

        assert "Docker is not running" in rendered

    def test_error_panel_contains_hint_when_provided(self) -> None:
        """Error panel includes hint when provided."""
        panel = create_error_panel(
            "Missing Dependency",
            "Docker not found",
            hint="Install Docker Desktop",
        )
        rendered = render_to_string(panel)

        assert "Install Docker Desktop" in rendered


class TestNoColorFallback:
    """Verify icon fallbacks work without crashing.

    These tests ensure the UI renders without Unicode/color support.
    """

    def test_info_panel_renders_without_color(self) -> None:
        """Info panel renders in no-color mode."""
        console = Console(
            file=StringIO(),
            force_terminal=True,
            width=80,
            no_color=True,
        )
        panel = create_info_panel("Test", "Content")
        console.print(panel)
        output = console.file.getvalue()  # type: ignore[union-attr]

        # Should still contain text content
        assert "Test" in output
        assert "Content" in output

    def test_error_panel_renders_without_color(self) -> None:
        """Error panel renders in no-color mode."""
        console = Console(
            file=StringIO(),
            force_terminal=True,
            width=80,
            no_color=True,
        )
        panel = create_error_panel("Oops", "Something went wrong")
        console.print(panel)
        output = console.file.getvalue()  # type: ignore[union-attr]

        # Should still contain text content
        assert "Oops" in output
        assert "Something went wrong" in output
