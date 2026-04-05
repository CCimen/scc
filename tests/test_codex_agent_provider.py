"""Characterization tests for CodexAgentProvider.

These tests pin the exact AgentLaunchSpec shape that CodexAgentProvider
produces so that regressions in the adapter seam are caught immediately.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scc_cli.adapters.codex_agent_provider import CodexAgentProvider

# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def provider() -> CodexAgentProvider:
    return CodexAgentProvider()


# ═══════════════════════════════════════════════════════════════════════════════
# capability_profile
# ═══════════════════════════════════════════════════════════════════════════════


def test_capability_profile_returns_codex_metadata(provider: CodexAgentProvider) -> None:
    """capability_profile() must return the stable Codex provider metadata."""
    profile = provider.capability_profile()

    assert profile.provider_id == "codex"
    assert profile.display_name == "Codex"
    assert profile.required_destination_set == "openai-core"
    assert profile.supports_resume is False


# ═══════════════════════════════════════════════════════════════════════════════
# prepare_launch — without settings_path
# ═══════════════════════════════════════════════════════════════════════════════


def test_prepare_launch_without_settings_produces_clean_spec(
    provider: CodexAgentProvider, tmp_path: Path
) -> None:
    """No settings_path → artifact_paths is empty, env is empty, argv is canonical."""
    spec = provider.prepare_launch(config={}, workspace=tmp_path, settings_path=None)

    assert spec.provider_id == "codex"
    assert spec.argv == ("codex",)
    assert spec.env == {}
    assert spec.artifact_paths == ()
    assert spec.required_destination_sets == ("openai-core",)
    assert spec.workdir == tmp_path


# ═══════════════════════════════════════════════════════════════════════════════
# prepare_launch — with settings_path
# ═══════════════════════════════════════════════════════════════════════════════


def test_prepare_launch_with_settings_includes_artifact_path(
    provider: CodexAgentProvider, tmp_path: Path
) -> None:
    """settings_path present → it appears in artifact_paths; env stays empty."""
    fake_settings = tmp_path / "codex-settings.json"
    fake_settings.write_text("{}")

    spec = provider.prepare_launch(
        config={}, workspace=tmp_path, settings_path=fake_settings
    )

    assert fake_settings in spec.artifact_paths
    assert spec.env == {}


# ═══════════════════════════════════════════════════════════════════════════════
# prepare_launch — env contract (D003 / KNOWLEDGE.md)
# ═══════════════════════════════════════════════════════════════════════════════


def test_prepare_launch_env_is_clean_str_to_str(
    provider: CodexAgentProvider, tmp_path: Path
) -> None:
    """All env values must be plain str, never nested dicts (D003 contract)."""
    spec = provider.prepare_launch(config={"key": "value"}, workspace=tmp_path)

    for key, val in spec.env.items():
        assert isinstance(key, str), f"env key {key!r} is not str"
        assert isinstance(val, str), f"env value for {key!r} is not str: {val!r}"


# ═══════════════════════════════════════════════════════════════════════════════
# auth_check — D037: adapter-owned auth readiness
# ═══════════════════════════════════════════════════════════════════════════════


def _mock_docker_run_codex(
    *,
    volume_rc: int = 0,
    cat_rc: int = 0,
    cat_stdout: bytes = b'{"token":"xyz"}',
    volume_exc: Exception | None = None,
    cat_exc: Exception | None = None,
) -> MagicMock:
    """Route subprocess.run by Docker subcommand for Codex auth checks."""

    def _side_effect(cmd: list[str], **_kw: object) -> subprocess.CompletedProcess[bytes]:
        if "volume" in cmd and "inspect" in cmd:
            if volume_exc is not None:
                raise volume_exc
            return subprocess.CompletedProcess(cmd, volume_rc, b"", b"")
        if "cat" in cmd:
            if cat_exc is not None:
                raise cat_exc
            return subprocess.CompletedProcess(cmd, cat_rc, cat_stdout, b"")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    return MagicMock(side_effect=_side_effect)


class TestCodexAuthCheck:
    """auth_check() validates Codex auth.json credential presence (D037)."""

    @patch("scc_cli.adapters.codex_agent_provider.subprocess.run")
    def test_auth_present_valid_json(self, mock_run: MagicMock, provider: CodexAgentProvider) -> None:
        mock_run.side_effect = _mock_docker_run_codex(
            cat_stdout=json.dumps({"api_key": "sk-abc"}).encode()
        ).side_effect
        result = provider.auth_check()
        assert result.status == "present"
        assert result.mechanism == "auth_json_file"
        assert "auth cache present" in result.guidance

    @patch("scc_cli.adapters.codex_agent_provider.subprocess.run")
    def test_auth_file_missing(self, mock_run: MagicMock, provider: CodexAgentProvider) -> None:
        mock_run.side_effect = _mock_docker_run_codex(cat_rc=1).side_effect
        result = provider.auth_check()
        assert result.status == "missing"
        assert "auth.json" in result.guidance

    @patch("scc_cli.adapters.codex_agent_provider.subprocess.run")
    def test_auth_file_empty(self, mock_run: MagicMock, provider: CodexAgentProvider) -> None:
        mock_run.side_effect = _mock_docker_run_codex(cat_stdout=b"").side_effect
        result = provider.auth_check()
        assert result.status == "missing"
        assert "empty" in result.guidance

    @patch("scc_cli.adapters.codex_agent_provider.subprocess.run")
    def test_auth_file_invalid_json(self, mock_run: MagicMock, provider: CodexAgentProvider) -> None:
        mock_run.side_effect = _mock_docker_run_codex(
            cat_stdout=b"corrupt-data!!!",
        ).side_effect
        result = provider.auth_check()
        assert result.status == "missing"
        assert "invalid JSON" in result.guidance

    @patch("scc_cli.adapters.codex_agent_provider.subprocess.run")
    def test_volume_missing(self, mock_run: MagicMock, provider: CodexAgentProvider) -> None:
        mock_run.side_effect = _mock_docker_run_codex(volume_rc=1).side_effect
        result = provider.auth_check()
        assert result.status == "missing"
        assert "scc start" in result.guidance

    @patch("scc_cli.adapters.codex_agent_provider.subprocess.run")
    def test_docker_not_reachable(self, mock_run: MagicMock, provider: CodexAgentProvider) -> None:
        mock_run.side_effect = _mock_docker_run_codex(
            volume_exc=FileNotFoundError("docker not found")
        ).side_effect
        result = provider.auth_check()
        assert result.status == "missing"
        assert "Cannot reach Docker" in result.guidance

    @patch("scc_cli.adapters.codex_agent_provider.subprocess.run")
    def test_cat_timeout(self, mock_run: MagicMock, provider: CodexAgentProvider) -> None:
        mock_run.side_effect = _mock_docker_run_codex(
            cat_exc=subprocess.TimeoutExpired(cmd=["docker"], timeout=30)
        ).side_effect
        result = provider.auth_check()
        assert result.status == "missing"
        assert "Timed out" in result.guidance
