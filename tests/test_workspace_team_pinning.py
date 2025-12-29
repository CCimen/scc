"""Tests for workspace-specific team pinning."""

from pathlib import Path
from unittest.mock import patch

from scc_cli.cli_launch import _resolve_workspace_team


def test_explicit_team_wins_over_pinned() -> None:
    """Explicit team selection should override pinned mapping."""
    workspace = Path("/tmp/project")
    workspace_key = str(workspace.resolve())
    cfg = {
        "selected_profile": "platform",
        "workspace_team_map": {workspace_key: "data"},
    }

    result = _resolve_workspace_team(
        workspace,
        team="security",
        cfg=cfg,
        json_mode=False,
        standalone=False,
    )

    assert result == "security"


def test_pinned_team_prompt_accepts() -> None:
    """Interactive prompt should accept pinned team when confirmed."""
    workspace = Path("/tmp/project")
    workspace_key = str(workspace.resolve())
    cfg = {
        "selected_profile": "platform",
        "workspace_team_map": {workspace_key: "data"},
    }

    with (
        patch("scc_cli.cli_launch.is_interactive_allowed", return_value=True),
        patch("scc_cli.cli_launch.Confirm.ask", return_value=True),
    ):
        result = _resolve_workspace_team(
            workspace,
            team=None,
            cfg=cfg,
            json_mode=False,
            standalone=False,
        )

    assert result == "data"


def test_pinned_team_prompt_declines() -> None:
    """Interactive prompt should keep global team when declined."""
    workspace = Path("/tmp/project")
    workspace_key = str(workspace.resolve())
    cfg = {
        "selected_profile": "platform",
        "workspace_team_map": {workspace_key: "data"},
    }

    with (
        patch("scc_cli.cli_launch.is_interactive_allowed", return_value=True),
        patch("scc_cli.cli_launch.Confirm.ask", return_value=False),
    ):
        result = _resolve_workspace_team(
            workspace,
            team=None,
            cfg=cfg,
            json_mode=False,
            standalone=False,
        )

    assert result == "platform"


def test_noninteractive_uses_pinned_team_with_notice() -> None:
    """Non-interactive flow should pick pinned team and warn."""
    workspace = Path("/tmp/project")
    workspace_key = str(workspace.resolve())
    cfg = {
        "selected_profile": "platform",
        "workspace_team_map": {workspace_key: "data"},
    }

    with (
        patch("scc_cli.cli_launch.is_interactive_allowed", return_value=False),
        patch("scc_cli.cli_launch.print_human") as mock_print,
    ):
        result = _resolve_workspace_team(
            workspace,
            team=None,
            cfg=cfg,
            json_mode=False,
            standalone=False,
        )

    assert result == "data"
    assert mock_print.called
