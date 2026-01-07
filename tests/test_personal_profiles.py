"""Tests for personal project profiles."""

from pathlib import Path

from scc_cli.core import personal_profiles
from scc_cli.marketplace.managed import ManagedState, save_managed_state


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(__import__("json").dumps(data, indent=2))


def test_repo_id_uses_remote(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        personal_profiles, "_get_remote_url", lambda _: "git@github.com:Org/Repo.git"
    )
    repo_id = personal_profiles.get_repo_id(tmp_path)
    assert repo_id == "remote:github.com/Org/Repo"


def test_repo_id_falls_back_to_path(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(personal_profiles, "_get_remote_url", lambda _: None)
    repo_id = personal_profiles.get_repo_id(tmp_path)
    assert repo_id.startswith("path:")


def test_save_and_load_profile(tmp_path: Path) -> None:
    settings_path = tmp_path / ".claude" / "settings.local.json"
    mcp_path = tmp_path / ".mcp.json"

    _write_json(settings_path, {"enabledPlugins": {"a@b": True}})
    _write_json(mcp_path, {"mcpServers": [{"name": "test", "type": "sse"}]})

    profile = personal_profiles.save_personal_profile(
        tmp_path,
        personal_profiles.load_workspace_settings(tmp_path) or {},
        personal_profiles.load_workspace_mcp(tmp_path) or {},
    )
    loaded = personal_profiles.load_personal_profile(tmp_path)

    assert loaded is not None
    assert loaded.repo_id == profile.repo_id
    assert loaded.settings == {"enabledPlugins": {"a@b": True}}
    assert loaded.mcp == {"mcpServers": [{"name": "test", "type": "sse"}]}


def test_merge_personal_settings_respects_managed(tmp_path: Path) -> None:
    # Managed plugin should be overridable by personal profile
    save_managed_state(
        tmp_path,
        ManagedState(managed_plugins=["team@market"], managed_marketplaces=[]),
    )

    existing = {"enabledPlugins": {"team@market": True, "user@market": True}}
    personal = {"enabledPlugins": {"team@market": False, "new@market": True}}

    merged = personal_profiles.merge_personal_settings(tmp_path, existing, personal)

    assert merged["enabledPlugins"]["team@market"] is False
    assert merged["enabledPlugins"]["user@market"] is True
    assert merged["enabledPlugins"]["new@market"] is True


def test_drift_detection(tmp_path: Path) -> None:
    settings_path = tmp_path / ".claude" / "settings.local.json"
    _write_json(settings_path, {"enabledPlugins": {"a@b": True}})

    personal_profiles.save_applied_state(
        tmp_path,
        "profile",
        personal_profiles.compute_fingerprints(tmp_path),
    )

    assert personal_profiles.detect_drift(tmp_path) is False

    _write_json(settings_path, {"enabledPlugins": {"a@b": False}})
    assert personal_profiles.detect_drift(tmp_path) is True


def test_compute_sandbox_import_candidates() -> None:
    workspace = {
        "enabledPlugins": {"alpha@market": True},
        "extraKnownMarketplaces": {"official": {"source": {"path": "x"}}},
    }
    sandbox = {
        "enabledPlugins": {"alpha@market": True, "beta@market": True},
        "extraKnownMarketplaces": {
            "official": {"source": {"path": "x"}},
            "extra": {"source": {"path": "y"}},
        },
    }

    missing_plugins, missing_marketplaces = personal_profiles.compute_sandbox_import_candidates(
        workspace, sandbox
    )

    assert missing_plugins == ["beta@market"]
    assert list(missing_marketplaces.keys()) == ["extra"]


def test_merge_sandbox_imports() -> None:
    workspace = {
        "enabledPlugins": {"alpha@market": True},
        "extraKnownMarketplaces": {"official": {"source": {"path": "x"}}},
    }
    merged = personal_profiles.merge_sandbox_imports(
        workspace,
        ["beta@market"],
        {"extra": {"source": {"path": "y"}}},
    )

    assert merged["enabledPlugins"]["beta@market"] is True
    assert "extra" in merged["extraKnownMarketplaces"]
