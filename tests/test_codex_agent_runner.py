"""Tests for CodexAgentRunner adapter."""

from __future__ import annotations

from pathlib import Path

import tomllib

from scc_cli.adapters.codex_agent_runner import DEFAULT_SETTINGS_PATH, CodexAgentRunner


class TestCodexAgentRunner:
    """Canonical 4-test shape for CodexAgentRunner."""

    def test_build_settings_returns_codex_path(self) -> None:
        runner = CodexAgentRunner()
        settings = runner.build_settings({}, path=DEFAULT_SETTINGS_PATH)
        assert settings.path == Path("/home/agent/.codex/config.toml")
        assert settings.suffix == ".toml"

    def test_build_settings_renders_toml_bytes(self) -> None:
        """D035: runner serialises config to TOML, not dict passthrough."""
        runner = CodexAgentRunner()
        config = {"cli_auth_credentials_store": "file", "model": "o3"}
        settings = runner.build_settings(config, path=DEFAULT_SETTINGS_PATH)
        assert isinstance(settings.rendered_bytes, bytes)
        # Verify it's valid TOML by round-tripping through tomllib
        parsed = tomllib.loads(settings.rendered_bytes.decode())
        assert parsed["cli_auth_credentials_store"] == "file"
        assert parsed["model"] == "o3"

    def test_build_settings_renders_nested_toml(self) -> None:
        """TOML sections for nested dicts."""
        runner = CodexAgentRunner()
        config = {"sandbox": {"auto_approve": True}, "model": "o3"}
        settings = runner.build_settings(config, path=DEFAULT_SETTINGS_PATH)
        parsed = tomllib.loads(settings.rendered_bytes.decode())
        assert parsed["model"] == "o3"
        assert parsed["sandbox"]["auto_approve"] is True

    def test_build_command_returns_codex_argv(self) -> None:
        runner = CodexAgentRunner()
        settings = runner.build_settings({}, path=DEFAULT_SETTINGS_PATH)
        command = runner.build_command(settings)
        assert command.argv[0] == "codex"
        # D033: must include bypass flag for container-level sandbox deferral
        assert "--dangerously-bypass-approvals-and-sandbox" in command.argv
        # Claude-style flag must NOT appear
        assert "--dangerously-skip-permissions" not in command.argv

    def test_build_command_includes_d033_bypass_flag(self) -> None:
        """D033: Codex launched with --dangerously-bypass-approvals-and-sandbox.

        SCC's container isolation is the hard boundary; Codex's OS-level
        sandbox is redundant inside Docker and may interfere.
        """
        runner = CodexAgentRunner()
        settings = runner.build_settings({}, path=DEFAULT_SETTINGS_PATH)
        command = runner.build_command(settings)
        assert command.argv == ["codex", "--dangerously-bypass-approvals-and-sandbox"]

    def test_describe_returns_codex(self) -> None:
        runner = CodexAgentRunner()
        assert runner.describe() == "Codex"

    def test_env_is_clean_str_to_str(self) -> None:
        """D003 contract guard: env dict must be empty str→str."""
        runner = CodexAgentRunner()
        settings = runner.build_settings({}, path=DEFAULT_SETTINGS_PATH)
        command = runner.build_command(settings)
        assert command.env == {}
        assert isinstance(command.env, dict)


class TestD040FileBasedAuth:
    """D040: SCC always injects cli_auth_credentials_store='file' for Codex."""

    def test_empty_config_gets_file_auth_store(self) -> None:
        """Even with no caller config, file-based auth is present."""
        runner = CodexAgentRunner()
        settings = runner.build_settings({}, path=DEFAULT_SETTINGS_PATH)
        parsed = tomllib.loads(settings.rendered_bytes.decode())
        assert parsed["cli_auth_credentials_store"] == "file"

    def test_caller_config_preserved_alongside_auth_store(self) -> None:
        """Caller-supplied keys merge with SCC-managed defaults."""
        runner = CodexAgentRunner()
        config = {"model": "o3", "history": True}
        settings = runner.build_settings(config, path=DEFAULT_SETTINGS_PATH)
        parsed = tomllib.loads(settings.rendered_bytes.decode())
        assert parsed["cli_auth_credentials_store"] == "file"
        assert parsed["model"] == "o3"
        assert parsed["history"] is True

    def test_explicit_override_takes_precedence(self) -> None:
        """If governed config explicitly sets a different store, it wins."""
        runner = CodexAgentRunner()
        config = {"cli_auth_credentials_store": "keyring"}
        settings = runner.build_settings(config, path=DEFAULT_SETTINGS_PATH)
        parsed = tomllib.loads(settings.rendered_bytes.decode())
        # Caller-supplied value overrides the SCC default
        assert parsed["cli_auth_credentials_store"] == "keyring"

    def test_auth_json_path_in_persistent_volume(self) -> None:
        """Auth.json lives in the persistent provider volume at /home/agent/.codex/.

        The data_volume (docker-codex-sandbox-data) is mounted to
        /home/agent/.codex, so auth.json persists across container restarts.
        """
        from scc_cli.core.provider_registry import get_runtime_spec

        spec = get_runtime_spec("codex")
        # The data volume mounts to /home/agent/<config_dir> → /home/agent/.codex
        auth_path = Path("/home/agent") / spec.config_dir / "auth.json"
        assert auth_path == Path("/home/agent/.codex/auth.json")
        # The volume name is stable across launches
        assert spec.data_volume == "docker-codex-sandbox-data"
