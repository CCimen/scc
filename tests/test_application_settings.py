from __future__ import annotations

from pathlib import Path

from scc_cli import config
from scc_cli.application import settings as app_settings
from scc_cli.core.personal_profiles import APPLIED_STATE_FILE


def test_load_settings_state_uses_saved_sync_path(temp_config_dir: Path, tmp_path: Path) -> None:
    config.save_user_config({"sync": {"last_repo": "/tmp/scc-sync"}})

    view_model = app_settings.load_settings_state(app_settings.SettingsContext(workspace=tmp_path))

    assert view_model.sync_repo_path == "/tmp/scc-sync"


def test_apply_settings_change_updates_sync_path(temp_config_dir: Path, tmp_path: Path) -> None:
    request = app_settings.SettingsChangeRequest(
        action_id="profile_sync",
        workspace=tmp_path,
        payload=app_settings.ProfileSyncPathPayload(new_path="/tmp/new-sync"),
    )

    result = app_settings.apply_settings_change(request)

    assert result.status == app_settings.SettingsActionStatus.SUCCESS

    updated = config.load_user_config()
    assert updated["sync"]["last_repo"] == "/tmp/new-sync"


def test_apply_settings_change_profile_save_writes_profile_and_state(
    temp_config_dir: Path, tmp_path: Path
) -> None:
    workspace = tmp_path / "workspace"
    settings_path = workspace / ".claude" / "settings.local.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text('{"foo": "bar"}')

    request = app_settings.SettingsChangeRequest(
        action_id="profile_save",
        workspace=workspace,
    )

    result = app_settings.apply_settings_change(request)

    assert result.status == app_settings.SettingsActionStatus.SUCCESS
    profiles_dir = config.CONFIG_DIR / "personal" / "projects"
    profiles = list(profiles_dir.glob("*.json"))
    assert len(profiles) == 1
    assert (workspace / ".claude" / APPLIED_STATE_FILE).exists()


def test_apply_settings_change_profile_sync_export_writes_repo_index(
    temp_config_dir: Path, tmp_path: Path
) -> None:
    workspace = tmp_path / "workspace"
    settings_path = workspace / ".claude" / "settings.local.json"
    settings_path.parent.mkdir(parents=True)
    settings_path.write_text('{"foo": "bar"}')

    app_settings.apply_settings_change(
        app_settings.SettingsChangeRequest(
            action_id="profile_save",
            workspace=workspace,
        )
    )

    repo_path = tmp_path / "profile-repo"
    request = app_settings.SettingsChangeRequest(
        action_id="profile_sync",
        workspace=workspace,
        payload=app_settings.ProfileSyncPayload(
            mode=app_settings.ProfileSyncMode.EXPORT,
            repo_path=repo_path,
            create_dir=True,
        ),
    )

    result = app_settings.apply_settings_change(request)

    assert result.status == app_settings.SettingsActionStatus.SUCCESS
    profiles_dir = repo_path / ".scc" / "profiles"
    index_path = profiles_dir / "index.json"
    profile_files = [path for path in profiles_dir.glob("*.json") if path.name != "index.json"]
    assert index_path.exists()
    assert len(profile_files) == 1
