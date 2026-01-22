"""Tests for proxy env propagation in legacy launch flow."""

from pathlib import Path
from unittest.mock import patch


def test_launch_sandbox_passes_proxy_env(tmp_path: Path, monkeypatch) -> None:
    from scc_cli.commands.launch import launch_sandbox

    workspace = tmp_path / "repo"
    workspace.mkdir()
    org_config = {"defaults": {"network_policy": "corp-proxy-only"}}

    monkeypatch.setenv("HTTP_PROXY", "http://proxy.example.com:8080")

    with (
        patch(
            "scc_cli.commands.launch.sandbox.config.load_cached_org_config", return_value=org_config
        ),
        patch("scc_cli.commands.launch.sandbox.docker.prepare_sandbox_volume_for_credentials"),
        patch(
            "scc_cli.commands.launch.sandbox.docker.get_or_create_container",
            return_value=(["docker", "run"], False),
        ) as mock_get_container,
        patch("scc_cli.commands.launch.sandbox.sessions.record_session"),
        patch("scc_cli.commands.launch.sandbox.git.get_worktree_main_repo", return_value=workspace),
        patch("scc_cli.commands.launch.sandbox.record_context"),
        patch("scc_cli.commands.launch.sandbox.show_launch_panel"),
        patch("scc_cli.commands.launch.sandbox.docker.run"),
        patch("scc_cli.commands.launch.sandbox.config.set_workspace_team"),
    ):
        launch_sandbox(
            workspace_path=workspace,
            mount_path=workspace,
            team="platform",
            session_name="session",
            current_branch="main",
            should_continue_session=False,
            fresh=False,
        )

    _, kwargs = mock_get_container.call_args
    assert kwargs["env_vars"]["HTTP_PROXY"] == "http://proxy.example.com:8080"
