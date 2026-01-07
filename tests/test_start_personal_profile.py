"""Tests for personal profile integration in start flow."""

from pathlib import Path

from scc_cli.commands.launch import app as launch_app
from scc_cli.core import personal_profiles
from scc_cli.marketplace.managed import ManagedState, save_managed_state


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(__import__("json").dumps(data, indent=2))


def test_apply_personal_profile_applies(tmp_path: Path) -> None:
    settings_path = tmp_path / ".claude" / "settings.local.json"
    _write_json(settings_path, {"enabledPlugins": {"team@market": True}})

    save_managed_state(
        tmp_path,
        ManagedState(managed_plugins=["team@market"], managed_marketplaces=[]),
    )

    personal_profiles.save_personal_profile(
        tmp_path,
        {"enabledPlugins": {"team@market": False, "user@market": True}},
        {},
    )

    profile_id, applied = launch_app._apply_personal_profile(
        tmp_path, json_mode=True, non_interactive=True
    )

    assert applied is True
    assert profile_id is not None

    updated = personal_profiles.load_workspace_settings(tmp_path) or {}
    assert updated.get("enabledPlugins", {}).get("team@market") is False
    assert updated.get("enabledPlugins", {}).get("user@market") is True

    state = personal_profiles.load_applied_state(tmp_path)
    assert state is not None
    assert state.profile_id == profile_id
