"""Tests for WSL2 warning behavior in non-interactive mode."""

from pathlib import Path
from unittest.mock import patch

from tests.fakes import FakePlatformProbe


def test_wsl2_warning_emitted_in_non_interactive(tmp_path: Path) -> None:
    """WSL2 performance warning should be emitted without prompting."""
    from scc_cli.commands.launch import validate_and_resolve_workspace

    workspace = tmp_path / "repo"
    workspace.mkdir()

    with (
        patch(
            "scc_cli.commands.launch.workspace.build_platform_probe",
            return_value=FakePlatformProbe(is_wsl2=True, is_optimal=False),
        ),
        patch("scc_cli.commands.launch.workspace.is_interactive_allowed", return_value=False),
        patch("scc_cli.commands.launch.workspace.Confirm.ask") as mock_confirm,
        patch("scc_cli.commands.launch.workspace.print_human") as mock_print,
    ):
        resolved = validate_and_resolve_workspace(str(workspace))

    assert resolved == workspace.resolve()
    mock_confirm.assert_not_called()
    assert mock_print.called
