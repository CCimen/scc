from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from rich.console import Console

from scc_cli.commands.launch.preflight import (
    AuthStatus,
    ImageStatus,
    LaunchReadiness,
    ProviderResolutionSource,
)
from scc_cli.core.exit_codes import EXIT_CANCELLED


def _console() -> tuple[Console, StringIO]:
    stream = StringIO()
    return Console(file=stream, force_terminal=False), stream


def _ready_readiness(provider_id: str = "codex") -> LaunchReadiness:
    return LaunchReadiness(
        provider_id=provider_id,
        resolution_source=ProviderResolutionSource.GLOBAL_PREFERRED,
        image_status=ImageStatus.AVAILABLE,
        auth_status=AuthStatus.PRESENT,
        requires_image_bootstrap=False,
        requires_auth_bootstrap=False,
        launch_ready=True,
    )


def _not_ready_readiness(provider_id: str = "codex") -> LaunchReadiness:
    return LaunchReadiness(
        provider_id=provider_id,
        resolution_source=ProviderResolutionSource.GLOBAL_PREFERRED,
        image_status=ImageStatus.AVAILABLE,
        auth_status=AuthStatus.MISSING,
        requires_image_bootstrap=False,
        requires_auth_bootstrap=True,
        launch_ready=False,
    )


def test_created_worktree_autostart_preserves_existing_launch_sequence(
    tmp_path: Path,
) -> None:
    from scc_cli.commands.launch.worktree_autostart import (
        CreatedWorktreeLaunchRequest,
        launch_created_worktree,
    )

    console, _stream = _console()
    adapters = MagicMock()
    normalized_org = MagicMock()
    start_dependencies = MagicMock()
    start_plan = MagicMock()
    worktree_path = tmp_path / "feature"
    call_order: list[str] = []

    with (
        patch(
            "scc_cli.commands.launch.worktree_autostart.config.load_user_config",
            return_value={"selected_profile": "platform", "selected_provider": "codex"},
        ),
        patch(
            "scc_cli.commands.launch.worktree_autostart.config.is_standalone_mode",
            return_value=False,
        ),
        patch(
            "scc_cli.commands.launch.worktree_autostart.config.load_cached_org_config",
            return_value={"teams": {}},
        ),
        patch(
            "scc_cli.commands.launch.worktree_autostart.NormalizedOrgConfig.from_dict",
            return_value=normalized_org,
        ),
        patch(
            "scc_cli.commands.launch.worktree_autostart.resolve_launch_provider",
            side_effect=lambda **_kwargs: call_order.append("resolve")
            or ("codex", ProviderResolutionSource.GLOBAL_PREFERRED),
        ) as mock_resolve_provider,
        patch(
            "scc_cli.commands.launch.worktree_autostart.collect_launch_readiness",
            side_effect=lambda *_args, **_kwargs: call_order.append("readiness")
            or _ready_readiness(),
        ) as mock_readiness,
        patch(
            "scc_cli.commands.launch.worktree_autostart.ensure_launch_ready"
        ) as mock_ensure_ready,
        patch(
            "scc_cli.commands.launch.worktree_autostart.prepare_live_start_plan",
            side_effect=lambda *_args, **_kwargs: call_order.append("prepare")
            or (start_dependencies, start_plan),
        ) as mock_prepare,
        patch(
            "scc_cli.commands.launch.worktree_autostart.finalize_launch",
            side_effect=lambda *_args, **_kwargs: call_order.append("finalize"),
        ) as mock_finalize,
        patch(
            "scc_cli.commands.launch.conflict_resolution.resolve_launch_conflict"
        ) as mock_conflict,
        patch("scc_cli.commands.launch.render.show_launch_panel") as mock_launch_panel,
        patch("scc_cli.workspace_local_config.set_workspace_last_used_provider") as mock_persist,
    ):
        launch_created_worktree(
            CreatedWorktreeLaunchRequest(worktree_path=worktree_path),
            adapters=adapters,
            console=console,
        )

    assert call_order == ["resolve", "readiness", "prepare", "finalize"]
    mock_resolve_provider.assert_called_once()
    assert mock_resolve_provider.call_args.kwargs["workspace_path"] == worktree_path
    assert mock_resolve_provider.call_args.kwargs["config_provider"] == "codex"
    assert mock_resolve_provider.call_args.kwargs["normalized_org"] is normalized_org
    assert mock_resolve_provider.call_args.kwargs["team"] == "platform"
    assert mock_readiness.call_args.args == (
        "codex",
        ProviderResolutionSource.GLOBAL_PREFERRED,
        adapters,
    )
    mock_ensure_ready.assert_not_called()

    request = mock_prepare.call_args.args[0]
    assert request.workspace_path == worktree_path
    assert request.workspace_arg == str(worktree_path)
    assert request.entry_dir == worktree_path
    assert request.team == "platform"
    assert request.session_name is None
    assert request.resume is False
    assert request.fresh is False
    assert request.offline is False
    assert request.standalone is False
    assert request.dry_run is False
    assert request.allow_suspicious is False
    assert request.org_config is normalized_org
    assert request.raw_org_config == {"teams": {}}
    assert request.provider_id == "codex"
    mock_prepare.assert_called_once_with(
        request,
        adapters=adapters,
        console=console,
        provider_id="codex",
    )
    mock_finalize.assert_called_once_with(start_plan, dependencies=start_dependencies)
    mock_conflict.assert_not_called()
    mock_launch_panel.assert_not_called()
    mock_persist.assert_not_called()


def test_created_worktree_autostart_cancels_when_provider_picker_cancels(
    tmp_path: Path,
) -> None:
    from scc_cli.commands.launch.worktree_autostart import (
        CreatedWorktreeLaunchRequest,
        launch_created_worktree,
    )

    console, stream = _console()
    adapters = MagicMock()

    with (
        patch(
            "scc_cli.commands.launch.worktree_autostart.config.load_user_config",
            return_value={},
        ),
        patch(
            "scc_cli.commands.launch.worktree_autostart.config.is_standalone_mode",
            return_value=True,
        ),
        patch(
            "scc_cli.commands.launch.worktree_autostart.resolve_launch_provider",
            return_value=(None, ProviderResolutionSource.GLOBAL_PREFERRED),
        ),
        patch("scc_cli.commands.launch.worktree_autostart.prepare_live_start_plan") as mock_prepare,
        pytest.raises(typer.Exit) as exc_info,
    ):
        launch_created_worktree(
            CreatedWorktreeLaunchRequest(worktree_path=tmp_path),
            adapters=adapters,
            console=console,
        )

    assert exc_info.value.exit_code == EXIT_CANCELLED
    assert "Cancelled." in stream.getvalue()
    mock_prepare.assert_not_called()


def test_created_worktree_autostart_uses_warning_panel_for_readiness_notice(
    tmp_path: Path,
) -> None:
    from scc_cli.commands.launch.worktree_autostart import (
        CreatedWorktreeLaunchRequest,
        launch_created_worktree,
    )

    console, _stream = _console()
    adapters = MagicMock()
    start_dependencies = MagicMock()
    start_plan = MagicMock()

    def ensure_ready_side_effect(*_args: object, **kwargs: object) -> None:
        show_notice = kwargs["show_notice"]
        show_notice("Auth Required", "Log in first", "Run scc doctor")

    with (
        patch(
            "scc_cli.commands.launch.worktree_autostart.config.load_user_config",
            return_value={},
        ),
        patch(
            "scc_cli.commands.launch.worktree_autostart.config.is_standalone_mode",
            return_value=True,
        ),
        patch(
            "scc_cli.commands.launch.worktree_autostart.resolve_launch_provider",
            return_value=("codex", ProviderResolutionSource.GLOBAL_PREFERRED),
        ),
        patch(
            "scc_cli.commands.launch.worktree_autostart.collect_launch_readiness",
            return_value=_not_ready_readiness(),
        ),
        patch(
            "scc_cli.commands.launch.worktree_autostart.ensure_launch_ready",
            side_effect=ensure_ready_side_effect,
        ) as mock_ensure_ready,
        patch(
            "scc_cli.commands.launch.worktree_autostart.create_warning_panel",
            return_value="PANEL",
        ) as mock_warning_panel,
        patch(
            "scc_cli.commands.launch.worktree_autostart.prepare_live_start_plan",
            return_value=(start_dependencies, start_plan),
        ),
        patch("scc_cli.commands.launch.worktree_autostart.finalize_launch"),
    ):
        launch_created_worktree(
            CreatedWorktreeLaunchRequest(worktree_path=tmp_path),
            adapters=adapters,
            console=console,
        )

    mock_ensure_ready.assert_called_once()
    mock_warning_panel.assert_called_once_with(
        "Auth Required",
        "Log in first",
        "Run scc doctor",
    )
