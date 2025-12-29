"""Tests for Quick Resume context recording warnings."""

from pathlib import Path
from unittest.mock import patch


def test_context_recording_failure_warns_user(tmp_path: Path) -> None:
    """Failure to record context should emit a warning in human mode."""
    from scc_cli.cli_launch import _launch_sandbox

    workspace = tmp_path / "repo"
    workspace.mkdir()

    with (
        patch("scc_cli.cli_launch.config.load_cached_org_config", return_value={}),
        patch("scc_cli.cli_launch.docker.prepare_sandbox_volume_for_credentials"),
        patch(
            "scc_cli.cli_launch.docker.get_or_create_container",
            return_value=("docker run".split(), False),
        ),
        patch("scc_cli.cli_launch.sessions.record_session"),
        patch("scc_cli.cli_launch.git.get_worktree_main_repo", return_value=workspace),
        patch("scc_cli.cli_launch.record_context", side_effect=OSError("disk full")),
        patch("scc_cli.cli_launch._show_launch_panel"),
        patch("scc_cli.cli_launch.docker.run"),
        patch("scc_cli.cli_launch.print_human") as mock_print,
    ):
        _launch_sandbox(
            workspace_path=workspace,
            mount_path=workspace,
            team="platform",
            session_name="session",
            current_branch="main",
            should_continue_session=False,
            fresh=False,
        )

    assert mock_print.called
