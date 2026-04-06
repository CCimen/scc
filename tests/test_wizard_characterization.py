"""Characterization tests for ui/wizard.py.

Lock current behavior of pure helpers: path normalization, answer
construction, and workspace source option building.
"""

from __future__ import annotations

from pathlib import Path

from scc_cli.ui.wizard import (
    StartWizardAction,
    StartWizardAnswerKind,
    _answer_back,
    _answer_cancelled,
    _answer_selected,
    _normalize_path,
)

# ══════════════════════════════════════════���══════════════════════════════════��═
# _normalize_path
# ═══════════════════════════════════════════════════════════════════════════════


class TestNormalizePath:
    """Path display normalization for wizard UI."""

    def test_home_prefix_collapsed(self) -> None:
        home = str(Path.home())
        result = _normalize_path(f"{home}/projects/api")
        assert result.startswith("~")
        assert "api" in result

    def test_non_home_path_unchanged(self) -> None:
        result = _normalize_path("/opt/data/files")
        assert result == "/opt/data/files"

    def test_long_path_truncated(self) -> None:
        home = str(Path.home())
        long_path = f"{home}/very/deeply/nested/path/structure/with/many/levels/to/project"
        result = _normalize_path(long_path)
        assert "…" in result
        # Preserves last 2 segments
        assert "to/project" in result

    def test_short_relative_path_under_home(self) -> None:
        home = str(Path.home())
        result = _normalize_path(f"{home}/dev")
        assert result == "~/dev"


# ═══════════════════════════════════════════════════════════════════════════════
# StartWizardAnswer construction
# ═══════════════════════════════════════════════════════════════════════════════


class TestStartWizardAnswer:
    """Answer factory functions produce correct kinds."""

    def test_cancelled(self) -> None:
        answer = _answer_cancelled()
        assert answer.kind == StartWizardAnswerKind.CANCELLED
        assert answer.value is None

    def test_back(self) -> None:
        answer = _answer_back()
        assert answer.kind == StartWizardAnswerKind.BACK
        assert answer.value is None

    def test_selected(self) -> None:
        answer = _answer_selected("some_value")
        assert answer.kind == StartWizardAnswerKind.SELECTED
        assert answer.value == "some_value"

    def test_selected_with_enum(self) -> None:
        answer = _answer_selected(StartWizardAction.NEW_SESSION)
        assert answer.kind == StartWizardAnswerKind.SELECTED
        assert answer.value == StartWizardAction.NEW_SESSION


# ═════════════════════════════════════════════���═════════════════════════════════
# StartWizardAction enum
# ════════════════════════════════════════════��══════════════════════════════════


class TestStartWizardAction:
    """Wizard action enum values are stable."""

    def test_action_values(self) -> None:
        assert StartWizardAction.NEW_SESSION.value == "new_session"
        assert StartWizardAction.TOGGLE_ALL_TEAMS.value == "toggle_all_teams"
        assert StartWizardAction.SWITCH_TEAM.value == "switch_team"

    def test_answer_kind_values(self) -> None:
        assert StartWizardAnswerKind.SELECTED.value == "selected"
        assert StartWizardAnswerKind.BACK.value == "back"
        assert StartWizardAnswerKind.CANCELLED.value == "cancelled"
