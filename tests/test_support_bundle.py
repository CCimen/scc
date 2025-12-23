"""
Tests for support bundle command (Phase 4).

TDD approach: Tests written before implementation.
These tests define the contract for:
- Support bundle creation with collected data
- Secret redaction (auth, tokens, API keys)
- Path redaction (home paths, repo names)
- JSON manifest output
- Custom output path
"""

import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import click

# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Secret Redaction (Pure Function)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSecretRedaction:
    """Test secret redaction in support bundles."""

    def test_redact_secrets_replaces_auth_values(self) -> None:
        """Auth values should be replaced with [REDACTED]."""
        from scc_cli.cli_support import redact_secrets

        data = {
            "auth": "secret-token-12345",
            "name": "test-config",
        }
        result = redact_secrets(data)

        assert result["auth"] == "[REDACTED]"
        assert result["name"] == "test-config"

    def test_redact_secrets_replaces_token_values(self) -> None:
        """Token values should be replaced with [REDACTED]."""
        from scc_cli.cli_support import redact_secrets

        data = {
            "token": "ghp_abc123xyz",
            "api_token": "sk-proj-12345",
            "access_token": "ya29.abc",
        }
        result = redact_secrets(data)

        assert result["token"] == "[REDACTED]"
        assert result["api_token"] == "[REDACTED]"
        assert result["access_token"] == "[REDACTED]"

    def test_redact_secrets_replaces_api_key_values(self) -> None:
        """API key values should be replaced with [REDACTED]."""
        from scc_cli.cli_support import redact_secrets

        data = {
            "api_key": "sk-ant-api03-xxx",
            "apiKey": "AIzaSyB-xxx",
            "API_KEY": "AKIAIOSFODNN7EXAMPLE",
        }
        result = redact_secrets(data)

        assert result["api_key"] == "[REDACTED]"
        assert result["apiKey"] == "[REDACTED]"
        assert result["API_KEY"] == "[REDACTED]"

    def test_redact_secrets_replaces_password_values(self) -> None:
        """Password values should be replaced with [REDACTED]."""
        from scc_cli.cli_support import redact_secrets

        data = {
            "password": "super-secret",
            "db_password": "postgres123",
        }
        result = redact_secrets(data)

        assert result["password"] == "[REDACTED]"
        assert result["db_password"] == "[REDACTED]"

    def test_redact_secrets_handles_nested_dicts(self) -> None:
        """Nested dictionaries should have secrets redacted."""
        from scc_cli.cli_support import redact_secrets

        data = {
            "config": {
                "auth": "nested-secret",
                "name": "nested-name",
            }
        }
        result = redact_secrets(data)

        assert result["config"]["auth"] == "[REDACTED]"
        assert result["config"]["name"] == "nested-name"

    def test_redact_secrets_handles_lists(self) -> None:
        """Lists containing dicts should have secrets redacted."""
        from scc_cli.cli_support import redact_secrets

        data = {
            "plugins": [
                {"name": "plugin1", "token": "secret1"},
                {"name": "plugin2", "token": "secret2"},
            ]
        }
        result = redact_secrets(data)

        assert result["plugins"][0]["name"] == "plugin1"
        assert result["plugins"][0]["token"] == "[REDACTED]"
        assert result["plugins"][1]["token"] == "[REDACTED]"

    def test_redact_secrets_strips_authorization_headers(self) -> None:
        """Authorization headers should be stripped."""
        from scc_cli.cli_support import redact_secrets

        data = {
            "headers": {
                "Authorization": "Bearer secret-jwt-token",
                "Content-Type": "application/json",
            }
        }
        result = redact_secrets(data)

        assert result["headers"]["Authorization"] == "[REDACTED]"
        assert result["headers"]["Content-Type"] == "application/json"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Path Redaction (Pure Function)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPathRedaction:
    """Test path redaction in support bundles."""

    def test_redact_paths_replaces_home_directory(self) -> None:
        """Home directory paths should be redacted."""
        from scc_cli.cli_support import redact_paths

        home = str(Path.home())
        data = {"path": f"{home}/projects/my-repo"}
        result = redact_paths(data)

        assert home not in result["path"]
        assert "~" in result["path"] or "[HOME]" in result["path"]

    def test_redact_paths_handles_nested_paths(self) -> None:
        """Nested paths should be redacted."""
        from scc_cli.cli_support import redact_paths

        home = str(Path.home())
        data = {
            "workspace": {
                "path": f"{home}/dev/secret-project",
            }
        }
        result = redact_paths(data)

        assert home not in str(result)

    def test_redact_paths_preserves_relative_paths(self) -> None:
        """Relative paths should not be modified."""
        from scc_cli.cli_support import redact_paths

        data = {"path": "./relative/path"}
        result = redact_paths(data)

        assert result["path"] == "./relative/path"

    def test_redact_paths_disabled_with_flag(self) -> None:
        """Path redaction can be disabled."""
        from scc_cli.cli_support import redact_paths

        home = str(Path.home())
        data = {"path": f"{home}/projects/my-repo"}
        result = redact_paths(data, redact=False)

        assert result["path"] == f"{home}/projects/my-repo"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Bundle Data Collection (Pure Function)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBundleDataCollection:
    """Test support bundle data collection."""

    def test_build_bundle_data_includes_system_info(self) -> None:
        """Bundle data should include system info."""
        from scc_cli.cli_support import build_bundle_data

        result = build_bundle_data()

        assert "system" in result
        assert "platform" in result["system"]
        assert "python_version" in result["system"]

    def test_build_bundle_data_includes_cli_version(self) -> None:
        """Bundle data should include CLI version."""
        from scc_cli.cli_support import build_bundle_data

        result = build_bundle_data()

        assert "cli_version" in result

    def test_build_bundle_data_includes_timestamp(self) -> None:
        """Bundle data should include generation timestamp."""
        from scc_cli.cli_support import build_bundle_data

        result = build_bundle_data()

        assert "generated_at" in result

    def test_build_bundle_data_includes_config(self) -> None:
        """Bundle data should include config (redacted)."""
        from scc_cli.cli_support import build_bundle_data

        with patch(
            "scc_cli.cli_support.config.load_config", return_value={"selected_profile": "test"}
        ):
            result = build_bundle_data()

        assert "config" in result

    def test_build_bundle_data_includes_doctor_output(self) -> None:
        """Bundle data should include doctor output."""
        from scc_cli.cli_support import build_bundle_data

        with patch("scc_cli.cli_support.doctor.run_doctor") as mock_doctor:
            from scc_cli.doctor import CheckResult, DoctorResult

            mock_doctor.return_value = DoctorResult(
                checks=[
                    CheckResult(name="Docker", passed=True, message="OK"),
                ]
            )
            result = build_bundle_data()

        assert "doctor" in result


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Bundle File Creation
# ═══════════════════════════════════════════════════════════════════════════════


class TestBundleFileCreation:
    """Test support bundle file creation."""

    def test_create_bundle_creates_zip_file(self, tmp_path: Path) -> None:
        """create_bundle should create a zip file."""
        from scc_cli.cli_support import create_bundle

        output_path = tmp_path / "support-bundle.zip"

        with patch("scc_cli.cli_support.build_bundle_data", return_value={"test": "data"}):
            create_bundle(output_path)

        assert output_path.exists()
        assert zipfile.is_zipfile(output_path)

    def test_create_bundle_contains_manifest(self, tmp_path: Path) -> None:
        """Bundle zip should contain manifest.json."""
        from scc_cli.cli_support import create_bundle

        output_path = tmp_path / "support-bundle.zip"

        with patch("scc_cli.cli_support.build_bundle_data", return_value={"test": "data"}):
            create_bundle(output_path)

        with zipfile.ZipFile(output_path, "r") as zf:
            assert "manifest.json" in zf.namelist()

    def test_create_bundle_default_output_path(self) -> None:
        """create_bundle should use default path if not specified."""
        from scc_cli.cli_support import get_default_bundle_path

        result = get_default_bundle_path()

        assert "scc-support-bundle" in str(result)
        assert result.suffix == ".zip"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for JSON Manifest Output
# ═══════════════════════════════════════════════════════════════════════════════


class TestJsonManifestOutput:
    """Test --json flag for manifest-only output."""

    def test_build_bundle_json_has_correct_kind(self) -> None:
        """JSON output should have kind=SupportBundle."""
        from scc_cli.json_output import build_envelope
        from scc_cli.kinds import Kind

        data = {"system": {}, "config": {}}
        envelope = build_envelope(Kind.SUPPORT_BUNDLE, data=data)

        assert envelope["kind"] == "SupportBundle"
        assert envelope["apiVersion"] == "scc.cli/v1"

    def test_json_output_does_not_create_file(self, tmp_path: Path, capsys) -> None:
        """--json flag should output manifest, not create zip."""
        from scc_cli.cli_support import support_bundle_cmd

        with patch("scc_cli.cli_support.build_bundle_data", return_value={"test": "data"}):
            try:
                support_bundle_cmd(
                    output=None,
                    json_output=True,
                    pretty=False,
                    no_redact_paths=False,
                )
            except click.exceptions.Exit:
                pass

        captured = capsys.readouterr()
        # Should have JSON output to stdout
        output = json.loads(captured.out)
        assert output["kind"] == "SupportBundle"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Custom Output Path
# ═══════════════════════════════════════════════════════════════════════════════


class TestCustomOutputPath:
    """Test --output flag for custom bundle path."""

    def test_custom_output_path_creates_file_at_location(self, tmp_path: Path) -> None:
        """--output should create bundle at specified path."""
        from scc_cli.cli_support import support_bundle_cmd

        output_path = tmp_path / "custom-bundle.zip"

        with patch("scc_cli.cli_support.build_bundle_data", return_value={"test": "data"}):
            try:
                support_bundle_cmd(
                    output=str(output_path),
                    json_output=False,
                    pretty=False,
                    no_redact_paths=False,
                )
            except click.exceptions.Exit:
                pass

        assert output_path.exists()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for CLI Integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestSupportBundleCLI:
    """Test support bundle CLI integration."""

    def test_support_app_exists(self) -> None:
        """support_app Typer should exist."""
        from scc_cli.cli_support import support_app

        assert support_app is not None

    def test_support_bundle_command_registered(self) -> None:
        """bundle command should be registered on support_app."""
        from scc_cli.cli_support import support_app

        command_names = [cmd.name for cmd in support_app.registered_commands]
        assert "bundle" in command_names
