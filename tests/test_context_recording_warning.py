"""Tests for Quick Resume context recording warnings."""

from pathlib import Path
from unittest.mock import patch


def test_context_recording_failure_warns_user(tmp_path: Path) -> None:
    """Failure to record context should emit a warning in human mode."""
    from scc_cli.commands.launch import _launch_sandbox

    workspace = tmp_path / "repo"
    workspace.mkdir()

    with (
        patch("scc_cli.commands.launch.config.load_cached_org_config", return_value={}),
        patch("scc_cli.commands.launch.docker.prepare_sandbox_volume_for_credentials"),
        patch(
            "scc_cli.commands.launch.docker.get_or_create_container",
            return_value=("docker run".split(), False),
        ),
        patch("scc_cli.commands.launch.sessions.record_session"),
        patch("scc_cli.commands.launch.git.get_worktree_main_repo", return_value=workspace),
        patch("scc_cli.commands.launch.record_context", side_effect=OSError("disk full")),
        patch("scc_cli.commands.launch._show_launch_panel"),
        patch("scc_cli.commands.launch.docker.run"),
        patch("scc_cli.commands.launch.print_human") as mock_print,
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
