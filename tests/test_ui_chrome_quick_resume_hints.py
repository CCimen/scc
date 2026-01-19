"""Characterization tests for Quick Resume chrome hints."""

from scc_cli.ui.chrome import ChromeConfig


def test_quick_resume_hints_include_expected_actions() -> None:
    config = ChromeConfig.for_quick_resume("Quick Resume")

    hints = [(hint.key, hint.action) for hint in config.footer_hints]

    assert ("n", "new session") in hints
    assert ("a", "all teams") in hints
    assert ("Esc", "back") in hints
    assert ("q", "quit") in hints


def test_quick_resume_hints_dim_all_teams_in_standalone() -> None:
    config = ChromeConfig.for_quick_resume("Quick Resume", standalone=True)

    all_teams_hint = next(hint for hint in config.footer_hints if hint.key == "a")

    assert all_teams_hint.action == "all teams"
    assert all_teams_hint.dimmed is True
