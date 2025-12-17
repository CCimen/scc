"""Tests for doctor.py new marketplace/auth checks.

These tests verify the new architecture requirements:
- Organization config reachability checks
- Schema validation checks
- Marketplace auth availability checks
- Credential injection verification
- Cache status checks
- Migration status checks
"""

import os
from unittest.mock import patch

from scc_cli import doctor

# ═══════════════════════════════════════════════════════════════════════════════
# Tests for check_org_config_reachable
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckOrgConfigReachable:
    """Tests for check_org_config_reachable() function."""

    def test_returns_ok_when_org_config_fetchable(self):
        """Should return OK when org config is reachable."""
        user_config = {
            "organization_source": {
                "url": "https://example.org/config.json",
                "auth": None,
            }
        }
        with (
            patch("scc_cli.doctor.config.load_user_config", return_value=user_config),
            patch("scc_cli.doctor.fetch_org_config", return_value=({"org": "test"}, "etag", 200)),
        ):
            result = doctor.check_org_config_reachable()

        assert result is not None
        assert result.passed is True

    def test_returns_error_when_fetch_fails(self):
        """Should return error when org config cannot be fetched."""
        user_config = {
            "organization_source": {
                "url": "https://example.org/config.json",
                "auth": None,
            }
        }
        with (
            patch("scc_cli.doctor.config.load_user_config", return_value=user_config),
            patch("scc_cli.doctor.fetch_org_config", return_value=(None, None, 500)),
        ):
            result = doctor.check_org_config_reachable()

        assert result is not None
        assert result.passed is False
        assert result.severity == "error"

    def test_returns_warning_when_401_without_auth(self):
        """Should return warning when auth required but not configured."""
        user_config = {
            "organization_source": {
                "url": "https://example.org/config.json",
                "auth": None,
            }
        }
        with (
            patch("scc_cli.doctor.config.load_user_config", return_value=user_config),
            patch("scc_cli.doctor.fetch_org_config", return_value=(None, None, 401)),
        ):
            result = doctor.check_org_config_reachable()

        assert result is not None
        assert result.passed is False
        assert "auth" in result.message.lower() or "401" in result.message

    def test_returns_none_for_standalone_mode(self):
        """Should return None when in standalone mode (no org config)."""
        user_config = {"standalone": True, "organization_source": None}
        with patch("scc_cli.doctor.config.load_user_config", return_value=user_config):
            result = doctor.check_org_config_reachable()

        assert result is None

    def test_returns_none_when_no_org_source(self):
        """Should return None when organization_source is not configured."""
        user_config = {}
        with patch("scc_cli.doctor.config.load_user_config", return_value=user_config):
            result = doctor.check_org_config_reachable()

        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for check_marketplace_auth_available
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckMarketplaceAuthAvailable:
    """Tests for check_marketplace_auth_available() function."""

    def test_returns_ok_for_public_marketplace(self):
        """Should return OK for public marketplace (no auth needed)."""
        org_config = {
            "profiles": {"dev": {"marketplace": "public"}},
            "marketplaces": [{"name": "public", "auth": None}],
        }
        user_config = {"selected_profile": "dev"}
        with (
            patch("scc_cli.doctor.config.load_user_config", return_value=user_config),
            patch("scc_cli.doctor.load_cached_org_config", return_value=org_config),
        ):
            result = doctor.check_marketplace_auth_available()

        assert result is not None
        assert result.passed is True
        assert "public" in result.message.lower() or "no auth" in result.message.lower()

    def test_returns_ok_when_env_var_is_set(self):
        """Should return OK when env var auth is configured and set."""
        org_config = {
            "profiles": {"dev": {"marketplace": "internal"}},
            "marketplaces": [{"name": "internal", "auth": "env:GITLAB_TOKEN"}],
        }
        user_config = {"selected_profile": "dev"}
        with (
            patch("scc_cli.doctor.config.load_user_config", return_value=user_config),
            patch("scc_cli.doctor.load_cached_org_config", return_value=org_config),
            patch.dict(os.environ, {"GITLAB_TOKEN": "secret-token"}),
        ):
            result = doctor.check_marketplace_auth_available()

        assert result is not None
        assert result.passed is True

    def test_returns_error_when_env_var_not_set(self):
        """Should return error when env var auth is configured but not set."""
        org_config = {
            "profiles": {"dev": {"marketplace": "internal"}},
            "marketplaces": [{"name": "internal", "auth": "env:GITLAB_TOKEN"}],
        }
        user_config = {"selected_profile": "dev"}
        # Create a clean environment without GITLAB_TOKEN
        clean_env = {k: v for k, v in os.environ.items() if k != "GITLAB_TOKEN"}
        with (
            patch("scc_cli.doctor.config.load_user_config", return_value=user_config),
            patch("scc_cli.doctor.load_cached_org_config", return_value=org_config),
            patch.dict(os.environ, clean_env, clear=True),
        ):
            result = doctor.check_marketplace_auth_available()

        assert result is not None
        assert result.passed is False
        assert result.severity == "error"

    def test_returns_none_when_no_profile_selected(self):
        """Should return None when no profile is selected."""
        user_config = {"selected_profile": None}
        with (
            patch("scc_cli.doctor.config.load_user_config", return_value=user_config),
            patch("scc_cli.doctor.load_cached_org_config", return_value=None),
        ):
            result = doctor.check_marketplace_auth_available()

        assert result is None

    def test_returns_none_when_no_org_config(self):
        """Should return None when no org config is cached."""
        user_config = {"selected_profile": "dev"}
        with (
            patch("scc_cli.doctor.config.load_user_config", return_value=user_config),
            patch("scc_cli.doctor.load_cached_org_config", return_value=None),
        ):
            result = doctor.check_marketplace_auth_available()

        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for check_credential_injection
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckCredentialInjection:
    """Tests for check_credential_injection() function."""

    def test_returns_ok_with_env_vars_to_inject(self):
        """Should return OK listing env vars that will be injected."""
        org_config = {
            "profiles": {"dev": {"marketplace": "internal"}},
            "marketplaces": [{"name": "internal", "type": "gitlab", "auth": "env:GITLAB_TOKEN"}],
        }
        user_config = {"selected_profile": "dev"}
        with (
            patch("scc_cli.doctor.config.load_user_config", return_value=user_config),
            patch("scc_cli.doctor.load_cached_org_config", return_value=org_config),
            patch.dict(os.environ, {"GITLAB_TOKEN": "secret"}),
        ):
            result = doctor.check_credential_injection()

        assert result is not None
        assert result.passed is True
        assert "GITLAB_TOKEN" in result.message

    def test_returns_ok_no_credentials_for_public(self):
        """Should return OK with 'no credentials needed' for public marketplace."""
        org_config = {
            "profiles": {"dev": {"marketplace": "public"}},
            "marketplaces": [{"name": "public", "auth": None}],
        }
        user_config = {"selected_profile": "dev"}
        with (
            patch("scc_cli.doctor.config.load_user_config", return_value=user_config),
            patch("scc_cli.doctor.load_cached_org_config", return_value=org_config),
        ):
            result = doctor.check_credential_injection()

        assert result is not None
        assert result.passed is True
        assert "no credentials" in result.message.lower() or "public" in result.message.lower()

    def test_returns_none_when_no_profile(self):
        """Should return None when no profile is selected."""
        user_config = {}
        with (
            patch("scc_cli.doctor.config.load_user_config", return_value=user_config),
            patch("scc_cli.doctor.load_cached_org_config", return_value=None),
        ):
            result = doctor.check_credential_injection()

        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for check_cache_readable
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckCacheReadable:
    """Tests for check_cache_readable() function."""

    def test_returns_ok_when_cache_valid(self, tmp_path):
        """Should return OK when cache exists and is valid JSON."""
        cache_file = tmp_path / "org_config.json"
        cache_file.write_text('{"organization": {"name": "Test"}}')

        with patch("scc_cli.doctor.config.CACHE_DIR", tmp_path):
            result = doctor.check_cache_readable()

        assert result is not None
        assert result.passed is True

    def test_returns_warning_when_no_cache(self, tmp_path):
        """Should return warning or info when no cache exists."""
        with patch("scc_cli.doctor.config.CACHE_DIR", tmp_path):
            result = doctor.check_cache_readable()

        assert result is not None
        # OK/info if no org configured, warning if expected
        assert result.severity in ["warning", "info"]

    def test_returns_error_when_cache_corrupted(self, tmp_path):
        """Should return error when cache is corrupted JSON."""
        cache_file = tmp_path / "org_config.json"
        cache_file.write_text("not valid json {{{")

        with patch("scc_cli.doctor.config.CACHE_DIR", tmp_path):
            result = doctor.check_cache_readable()

        assert result is not None
        assert result.passed is False
        assert result.severity == "error"


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for check_cache_ttl_status
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckCacheTtlStatus:
    """Tests for check_cache_ttl_status() function."""

    def test_returns_ok_when_cache_fresh(self, tmp_path):
        """Should return OK when cache is within TTL."""
        import json
        from datetime import datetime, timedelta, timezone

        cache_meta = tmp_path / "cache_meta.json"
        expires = datetime.now(timezone.utc) + timedelta(hours=12)
        cache_meta.write_text(
            json.dumps(
                {
                    "org_config": {
                        "fetched_at": datetime.now(timezone.utc).isoformat(),
                        "expires_at": expires.isoformat(),
                    }
                }
            )
        )

        with patch("scc_cli.doctor.config.CACHE_DIR", tmp_path):
            result = doctor.check_cache_ttl_status()

        assert result is not None
        assert result.passed is True

    def test_returns_warning_when_cache_expired(self, tmp_path):
        """Should return warning when cache is expired."""
        import json
        from datetime import datetime, timedelta, timezone

        cache_meta = tmp_path / "cache_meta.json"
        expired = datetime.now(timezone.utc) - timedelta(hours=1)
        cache_meta.write_text(
            json.dumps(
                {
                    "org_config": {
                        "fetched_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),
                        "expires_at": expired.isoformat(),
                    }
                }
            )
        )

        with patch("scc_cli.doctor.config.CACHE_DIR", tmp_path):
            result = doctor.check_cache_ttl_status()

        assert result is not None
        assert result.passed is False
        assert result.severity == "warning"

    def test_returns_none_when_no_cache_meta(self, tmp_path):
        """Should return None when no cache metadata exists."""
        with patch("scc_cli.doctor.config.CACHE_DIR", tmp_path):
            result = doctor.check_cache_ttl_status()

        # Should be None or info/warning (no cache to report on)
        assert result is None or result.severity in ["warning", "info"]


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for check_migration_status
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckMigrationStatus:
    """Tests for check_migration_status() function."""

    def test_returns_ok_when_no_legacy_config(self, tmp_path):
        """Should return OK when no legacy config exists."""
        legacy_dir = tmp_path / "scc-cli"
        new_dir = tmp_path / "scc"
        new_dir.mkdir()

        with (
            patch("scc_cli.doctor.config.LEGACY_CONFIG_DIR", legacy_dir),
            patch("scc_cli.doctor.config.CONFIG_DIR", new_dir),
        ):
            result = doctor.check_migration_status()

        assert result is not None
        assert result.passed is True

    def test_returns_warning_when_legacy_config_exists(self, tmp_path):
        """Should return warning when legacy config still exists."""
        legacy_dir = tmp_path / "scc-cli"
        legacy_dir.mkdir()
        (legacy_dir / "config.json").write_text("{}")
        new_dir = tmp_path / "scc"
        new_dir.mkdir()

        with (
            patch("scc_cli.doctor.config.LEGACY_CONFIG_DIR", legacy_dir),
            patch("scc_cli.doctor.config.CONFIG_DIR", new_dir),
        ):
            result = doctor.check_migration_status()

        assert result is not None
        assert result.passed is False
        assert result.severity == "warning"
        assert "legacy" in result.message.lower() or "old" in result.message.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for load_cached_org_config helper
# ═══════════════════════════════════════════════════════════════════════════════


class TestLoadCachedOrgConfig:
    """Tests for load_cached_org_config() helper function."""

    def test_returns_config_when_cache_exists(self, tmp_path):
        """Should return cached config when file exists."""
        cache_file = tmp_path / "org_config.json"
        cache_file.write_text('{"organization": {"name": "Test Org"}}')

        with patch("scc_cli.doctor.config.CACHE_DIR", tmp_path):
            result = doctor.load_cached_org_config()

        assert result is not None
        assert result["organization"]["name"] == "Test Org"

    def test_returns_none_when_no_cache(self, tmp_path):
        """Should return None when no cache exists."""
        with patch("scc_cli.doctor.config.CACHE_DIR", tmp_path):
            result = doctor.load_cached_org_config()

        assert result is None

    def test_returns_none_when_cache_invalid(self, tmp_path):
        """Should return None when cache is invalid JSON."""
        cache_file = tmp_path / "org_config.json"
        cache_file.write_text("not valid json")

        with patch("scc_cli.doctor.config.CACHE_DIR", tmp_path):
            result = doctor.load_cached_org_config()

        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for run_all_checks integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestRunAllChecks:
    """Tests for run_all_checks() integration."""

    def test_includes_new_checks_in_results(self):
        """Should include new org/marketplace checks in results."""
        # Create mock CheckResult objects with correct signature
        mock_git = doctor.CheckResult(name="Git", passed=True, message="available")
        mock_docker = doctor.CheckResult(name="Docker", passed=True, message="available")
        mock_sandbox = doctor.CheckResult(name="Sandbox", passed=True, message="available")
        mock_daemon = doctor.CheckResult(name="Docker Daemon", passed=True, message="running")
        mock_wsl2 = doctor.CheckResult(
            name="WSL2", passed=True, message="not WSL2", severity="info"
        )
        mock_config = doctor.CheckResult(name="Config", passed=True, message="exists")
        mock_org = doctor.CheckResult(name="Org Config", passed=True, message="reachable")
        mock_auth = doctor.CheckResult(name="Auth", passed=True, message="ok")
        mock_injection = doctor.CheckResult(name="Injection", passed=True, message="ok")
        mock_cache = doctor.CheckResult(name="Cache", passed=True, message="ok")
        mock_ttl = doctor.CheckResult(name="TTL", passed=True, message="ok")
        mock_migration = doctor.CheckResult(name="Migration", passed=True, message="ok")

        with (
            patch("scc_cli.doctor.check_git", return_value=mock_git),
            patch("scc_cli.doctor.check_docker", return_value=mock_docker),
            patch("scc_cli.doctor.check_docker_sandbox", return_value=mock_sandbox),
            patch("scc_cli.doctor.check_docker_running", return_value=mock_daemon),
            patch("scc_cli.doctor.check_wsl2", return_value=(mock_wsl2, False)),
            patch("scc_cli.doctor.check_config_directory", return_value=mock_config),
            patch("scc_cli.doctor.check_org_config_reachable", return_value=mock_org),
            patch("scc_cli.doctor.check_marketplace_auth_available", return_value=mock_auth),
            patch("scc_cli.doctor.check_credential_injection", return_value=mock_injection),
            patch("scc_cli.doctor.check_cache_readable", return_value=mock_cache),
            patch("scc_cli.doctor.check_cache_ttl_status", return_value=mock_ttl),
            patch("scc_cli.doctor.check_migration_status", return_value=mock_migration),
        ):
            results = doctor.run_all_checks()

        # Should have multiple checks
        assert len(results) >= 6

        # Should include new check categories
        check_names = [r.name for r in results]
        assert "Org Config" in check_names or any("org" in n.lower() for n in check_names)
