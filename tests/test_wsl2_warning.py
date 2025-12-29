"""Tests for WSL2 warning behavior in non-interactive mode."""

from pathlib import Path
from unittest.mock import patch


def test_wsl2_warning_emitted_in_non_interactive(tmp_path: Path) -> None:
    """WSL2 performance warning should be emitted without prompting."""
    from scc_cli.cli_launch import _validate_and_resolve_workspace

    workspace = tmp_path / "repo"
    workspace.mkdir()

    with (
        patch("scc_cli.cli_launch.platform_module.is_wsl2", return_value=True),
        patch(
            "scc_cli.cli_launch.platform_module.check_path_performance",
            return_value=(False, "warning"),
        ),
        patch("scc_cli.cli_launch.is_interactive_allowed", return_value=False),
        patch("scc_cli.cli_launch.Confirm.ask") as mock_confirm,
        patch("scc_cli.cli_launch.print_human") as mock_print,
    ):
        resolved = _validate_and_resolve_workspace(str(workspace))

    assert resolved == workspace.resolve()
    mock_confirm.assert_not_called()
    assert mock_print.called
