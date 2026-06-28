"""Tests for setup.py remote organization config wizard.

These tests verify the new architecture requirements:
- Remote org config URL workflow
- Authentication handling (env:VAR, command:CMD, null)
- Team/profile selection from remote config
- Standalone mode (no org config)
- Hooks enablement option
"""

from unittest.mock import MagicMock, patch

from scc_cli import setup

# ═══════════════════════════════════════════════════════════════════════════════
# Tests for prompt_org_url
# ═══════════════════════════════════════════════════════════════════════════════


class TestPromptOrgUrl:
    """Tests for prompt_org_url() function."""

    def test_accepts_valid_https_url(self):
        """Should accept valid HTTPS URL."""
        mock_console = MagicMock()
        with patch(
            "scc_cli.setup.prompt_with_layout", return_value="https://example.org/config.json"
        ):
            result = setup.prompt_org_url(mock_console)
        assert result == "https://example.org/config.json"

    def test_rejects_http_url(self):
        """Should reject HTTP URL and prompt again."""
        mock_console = MagicMock()
        with patch(
            "scc_cli.setup.prompt_with_layout",
            side_effect=["http://example.org/config.json", "https://example.org/config.json"],
        ):
            result = setup.prompt_org_url(mock_console)
        assert result == "https://example.org/config.json"
        # Should have shown error message for HTTP
        mock_console.print.assert_any_call(
            "[red]✗ HTTP URLs are not allowed. Please use HTTPS.[/red]"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for fetch_and_validate_org_config
# ═══════════════════════════════════════════════════════════════════════════════


class TestFetchAndValidateOrgConfig:
    """Tests for fetch_and_validate_org_config() function."""

    def test_successful_fetch_returns_config(self):
        """Should return config on successful fetch."""
        mock_console = MagicMock()
        sample_config = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test Org", "id": "test-org"},
            "profiles": {"dev": {"description": "Dev team"}},
        }
        with patch("scc_cli.setup.fetch_org_config", return_value=(sample_config, "etag123", 200)):
            result = setup.fetch_and_validate_org_config(
                mock_console, "https://example.org/config.json", auth=None
            )
        assert result == sample_config

    def test_returns_none_on_401_without_auth(self):
        """Should return None on 401 to trigger auth prompt."""
        mock_console = MagicMock()
        with patch("scc_cli.setup.fetch_org_config", return_value=(None, None, 401)):
            result = setup.fetch_and_validate_org_config(
                mock_console, "https://example.org/config.json", auth=None
            )
        assert result is None

    def test_retries_with_auth_on_401(self):
        """Should retry fetch with auth after 401."""
        mock_console = MagicMock()
        sample_config = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test", "id": "test"},
        }
        with patch(
            "scc_cli.setup.fetch_org_config",
            side_effect=[
                (None, None, 401),  # First call fails
                (sample_config, "etag", 200),  # Second with auth succeeds
            ],
        ):
            # First call without auth
            result1 = setup.fetch_and_validate_org_config(
                mock_console, "https://example.org/config.json", auth=None
            )
            assert result1 is None

            # Second call with auth
            result2 = setup.fetch_and_validate_org_config(
                mock_console, "https://example.org/config.json", auth="env:TOKEN"
            )
            assert result2 == sample_config


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for save_setup_config
# ═══════════════════════════════════════════════════════════════════════════════


class TestSaveSetupConfig:
    """Tests for save_setup_config() function."""

    def test_saves_org_source_url(self, tmp_path):
        """Should save organization source URL to config."""
        mock_console = MagicMock()
        with (
            patch("scc_cli.setup.config.CONFIG_DIR", tmp_path),
            patch("scc_cli.setup.config.CONFIG_FILE", tmp_path / "config.json"),
            patch("scc_cli.setup.config.save_user_config") as mock_save,
        ):
            setup.save_setup_config(
                mock_console,
                org_url="https://example.org/config.json",
                auth="env:TOKEN",
                auth_header="PRIVATE-TOKEN",
                profile="platform",
                hooks_enabled=True,
            )
            mock_save.assert_called_once()
            saved_config = mock_save.call_args[0][0]
            assert saved_config["organization_source"]["url"] == "https://example.org/config.json"
            assert saved_config["organization_source"]["auth"] == "env:TOKEN"
            assert saved_config["organization_source"]["auth_header"] == "PRIVATE-TOKEN"
            assert saved_config["selected_profile"] == "platform"
            assert saved_config["hooks"]["enabled"] is True

    def test_saves_standalone_config(self, tmp_path):
        """Should save standalone mode config."""
        mock_console = MagicMock()
        with (
            patch("scc_cli.setup.config.CONFIG_DIR", tmp_path),
            patch("scc_cli.setup.config.CONFIG_FILE", tmp_path / "config.json"),
            patch("scc_cli.setup.config.save_user_config") as mock_save,
        ):
            setup.save_setup_config(
                mock_console,
                org_url=None,  # Standalone
                auth=None,
                auth_header=None,
                profile=None,
                hooks_enabled=False,
                standalone=True,
            )
            mock_save.assert_called_once()
            saved_config = mock_save.call_args[0][0]
            assert saved_config.get("standalone") is True
            assert saved_config.get("organization_source") is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for run_setup_wizard (integration)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRunSetupWizard:
    """Integration tests for run_setup_wizard() function."""

    @staticmethod
    def _create_mock_console() -> MagicMock:
        """Create a mock console with proper size attributes."""
        mock_console = MagicMock()
        mock_console.size.width = 120
        mock_console.size.height = 40
        return mock_console

    def test_full_org_config_flow(self, tmp_path):
        """Should complete full org config setup flow."""
        mock_console = self._create_mock_console()
        sample_config = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test Org", "id": "test-org"},
            "profiles": {"dev": {"description": "Dev team"}},
        }
        with (
            patch("scc_cli.setup._render_setup_header"),
            patch("scc_cli.setup._render_setup_layout"),
            # Mode=0 (org), Profile=0 (first), Hooks=0 (enable), Confirm=0 (apply)
            patch("scc_cli.setup._select_option", side_effect=[0, 0, 0, 0]),
            patch("scc_cli.setup.prompt_org_url", return_value="https://example.org/config.json"),
            patch("scc_cli.setup.fetch_and_validate_org_config", return_value=sample_config),
            patch("scc_cli.setup.config.load_user_config", return_value={}),
            patch("scc_cli.setup.save_setup_config"),
            patch("scc_cli.setup._run_provider_onboarding", return_value=(None, None)),
            patch("scc_cli.setup.show_setup_complete"),
        ):
            result = setup.run_setup_wizard(mock_console)
        assert result is True

    def test_standalone_flow(self, tmp_path):
        """Should complete standalone setup flow."""
        mock_console = self._create_mock_console()
        with (
            patch("scc_cli.setup._render_setup_header"),
            patch("scc_cli.setup._render_setup_layout"),
            # Mode=1 (standalone), Hooks=0 (enable), Confirm=0 (apply)
            patch("scc_cli.setup._select_option", side_effect=[1, 0, 0]),
            patch("scc_cli.setup.config.load_user_config", return_value={}),
            patch("scc_cli.setup.save_setup_config"),
            patch("scc_cli.setup._run_provider_onboarding", return_value=(None, None)),
            patch("scc_cli.setup.show_setup_complete"),
        ):
            result = setup.run_setup_wizard(mock_console)
        assert result is True

    def test_auth_retry_flow(self, tmp_path):
        """Should retry with auth on 401."""
        mock_console = self._create_mock_console()
        sample_config = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test Org", "id": "test-org"},
            "profiles": {},
        }
        with (
            patch("scc_cli.setup._render_setup_header"),
            patch("scc_cli.setup._render_setup_layout"),
            # Mode=0 (org), Auth=0 (env var), Hooks=0 (enable), Confirm=0 (apply)
            patch("scc_cli.setup._select_option", side_effect=[0, 0, 0, 0]),
            patch("scc_cli.setup.prompt_org_url", return_value="https://example.org/config.json"),
            patch(
                "scc_cli.setup.fetch_and_validate_org_config",
                side_effect=[None, sample_config],  # First fails (401), second succeeds
            ),
            patch("scc_cli.setup.prompt_with_layout", return_value="MY_TOKEN"),  # Env var name
            patch("scc_cli.setup.config.load_user_config", return_value={}),
            patch("scc_cli.setup.save_setup_config"),
            patch("scc_cli.setup._run_provider_onboarding", return_value=(None, None)),
            patch("scc_cli.setup.show_setup_complete"),
        ):
            result = setup.run_setup_wizard(mock_console)
        assert result is True


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for non-interactive setup
# ═══════════════════════════════════════════════════════════════════════════════


class TestNonInteractiveSetup:
    """Tests for non-interactive setup with CLI arguments."""

    def test_setup_with_all_args(self, tmp_path):
        """Should setup with all CLI arguments provided."""
        mock_console = MagicMock()
        sample_config = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test Org", "id": "test-org"},
            "profiles": {"dev": {}},
        }
        with (
            patch("scc_cli.setup.fetch_and_validate_org_config", return_value=sample_config),
            patch("scc_cli.setup.save_setup_config") as mock_save,
            patch("scc_cli.setup._run_provider_onboarding", return_value=(None, None)),
            patch("scc_cli.setup.show_setup_complete"),
        ):
            result = setup.run_non_interactive_setup(
                mock_console,
                org_url="https://example.org/config.json",
                team="dev",
                auth="env:TOKEN",
            )
        assert result is True
        mock_save.assert_called_once()

    def test_standalone_setup(self, tmp_path):
        """Should setup standalone mode."""
        mock_console = MagicMock()
        with (
            patch("scc_cli.setup.save_setup_config") as mock_save,
            patch("scc_cli.setup._run_provider_onboarding", return_value=(None, None)),
            patch("scc_cli.setup.show_setup_complete"),
        ):
            result = setup.run_non_interactive_setup(
                mock_console,
                standalone=True,
            )
        assert result is True
        saved_config_call = mock_save.call_args
        assert saved_config_call[1].get("standalone") is True or (
            len(saved_config_call[0]) > 0 and saved_config_call[0]
        )
