from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from rich.console import Console

from scc_cli.application import settings as app_settings
from scc_cli.maintenance import RiskTier
from scc_cli.ui.settings import SettingsScreen


def _settings_view_model() -> app_settings.SettingsViewModel:
    action = app_settings.SettingsAction(
        id="clear_cache",
        label="Clear cache",
        description="Remove cached data",
        risk_tier=RiskTier.CHANGES_STATE,
        category=app_settings.SettingsCategory.MAINTENANCE,
    )
    return app_settings.SettingsViewModel(
        header=app_settings.SettingsHeader(profile_name="platform", org_name="Example Org"),
        categories=list(app_settings.SettingsCategory),
        actions_by_category={app_settings.SettingsCategory.MAINTENANCE: [action]},
        sync_repo_path="",
    )


def _render_settings_screen(*, show_help: bool = False) -> str:
    output = StringIO()
    console = Console(file=output, force_terminal=True, width=100, color_system=None)

    with (
        patch("scc_cli.ui.settings.get_err_console", return_value=console),
        patch(
            "scc_cli.ui.settings.app_settings.load_settings_state",
            return_value=_settings_view_model(),
        ),
    ):
        screen = SettingsScreen(initial_category=app_settings.SettingsCategory.MAINTENANCE)
        screen._show_help = show_help
        console.print(screen._render())

    return output.getvalue()


def test_settings_screen_render_includes_header_actions_and_hints() -> None:
    rendered = _render_settings_screen()

    assert "Settings" in rendered
    assert "platform" in rendered
    assert "Example Org" in rendered
    assert "Clear cache" in rendered
    assert "navigate" in rendered


def test_settings_screen_help_overlay_renders_shortcuts() -> None:
    rendered = _render_settings_screen(show_help=True)

    assert "Keyboard Shortcuts" in rendered
    assert "Navigate actions" in rendered
