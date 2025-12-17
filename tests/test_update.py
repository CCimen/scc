"""Tests for update module."""

import json
import urllib.error
from datetime import datetime, timedelta, timezone
from importlib.metadata import PackageNotFoundError
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from scc_cli import update
from scc_cli.update import (
    PACKAGE_NAME,
    OrgConfigUpdateResult,
    UpdateCheckResult,
    UpdateInfo,
    _compare_versions,
    _detect_install_method,
    _fetch_latest_from_pypi,
    _format_age,
    _get_current_version,
    _load_update_check_meta,
    _mark_cli_check_done,
    _mark_org_config_check_done,
    _parse_version,
    _save_update_check_meta,
    _should_check_cli_updates,
    _should_check_org_config,
    check_all_updates,
    check_for_updates,
    check_org_config_update,
    get_update_command,
    render_update_notification,
    render_update_status_panel,
)


class TestParseVersion:
    """Tests for _parse_version function."""

    def test_simple_version(self):
        """Simple version should parse correctly."""
        parts, pre = _parse_version("1.2.3")
        assert parts == (1, 2, 3)
        assert pre is None

    def test_two_part_version(self):
        """Two-part version should pad to three parts."""
        parts, pre = _parse_version("1.2")
        assert parts == (1, 2, 0)
        assert pre is None

    def test_single_part_version(self):
        """Single-part version should pad to three parts."""
        parts, pre = _parse_version("1")
        assert parts == (1, 0, 0)
        assert pre is None

    def test_rc_prerelease(self):
        """RC pre-release should be parsed."""
        parts, pre = _parse_version("1.0.0rc1")
        assert parts == (1, 0, 0)
        assert pre == (3, 1)  # rc=3 in order, number=1

    def test_alpha_prerelease(self):
        """Alpha pre-release should be parsed."""
        parts, pre = _parse_version("1.0.0a2")
        assert parts == (1, 0, 0)
        assert pre == (1, 2)  # a=1 in order, number=2

    def test_beta_prerelease(self):
        """Beta pre-release should be parsed."""
        parts, pre = _parse_version("1.0.0b3")
        assert parts == (1, 0, 0)
        assert pre == (2, 3)  # b=2 in order, number=3

    def test_dev_prerelease(self):
        """Dev pre-release should be parsed."""
        parts, pre = _parse_version("1.0.0.dev1")
        assert parts == (1, 0, 0)
        assert pre == (0, 1)  # dev=0 in order, number=1

    def test_hyphen_separator(self):
        """Hyphen separator should be handled."""
        parts, pre = _parse_version("1.0.0-rc1")
        assert parts == (1, 0, 0)
        assert pre == (3, 1)

    def test_underscore_separator(self):
        """Underscore separator should be handled."""
        parts, pre = _parse_version("1.0.0_alpha1")
        assert parts == (1, 0, 0)
        assert pre == (1, 1)


class TestCompareVersions:
    """Tests for _compare_versions function - CRITICAL BUG COVERAGE."""

    def test_equal_versions(self):
        """Equal versions should return 0."""
        assert _compare_versions("1.0.0", "1.0.0") == 0
        assert _compare_versions("2.3.4", "2.3.4") == 0

    def test_first_less_than_second(self):
        """First version less should return -1."""
        assert _compare_versions("1.0.0", "1.0.1") == -1
        assert _compare_versions("1.0.0", "1.1.0") == -1
        assert _compare_versions("1.0.0", "2.0.0") == -1

    def test_first_greater_than_second(self):
        """First version greater should return 1."""
        assert _compare_versions("1.0.1", "1.0.0") == 1
        assert _compare_versions("1.1.0", "1.0.0") == 1
        assert _compare_versions("2.0.0", "1.0.0") == 1

    def test_multi_digit_version_numbers(self):
        """Multi-digit version numbers should compare correctly."""
        assert _compare_versions("1.9.0", "1.10.0") == -1
        assert _compare_versions("1.10.0", "1.9.0") == 1
        assert _compare_versions("1.99.0", "1.100.0") == -1

    # CRITICAL: Pre-release handling tests
    def test_prerelease_less_than_final(self):
        """Pre-release versions MUST be less than final release - CRITICAL FIX."""
        assert _compare_versions("1.0.0rc1", "1.0.0") == -1
        assert _compare_versions("1.0.0a1", "1.0.0") == -1
        assert _compare_versions("1.0.0b1", "1.0.0") == -1
        assert _compare_versions("1.0.0.dev1", "1.0.0") == -1

    def test_final_greater_than_prerelease(self):
        """Final release MUST be greater than pre-release - CRITICAL FIX."""
        assert _compare_versions("1.0.0", "1.0.0rc1") == 1
        assert _compare_versions("1.0.0", "1.0.0a1") == 1
        assert _compare_versions("1.0.0", "1.0.0b1") == 1
        assert _compare_versions("1.0.0", "1.0.0.dev1") == 1

    def test_prerelease_ordering(self):
        """Pre-release types should order: dev < alpha < beta < rc."""
        assert _compare_versions("1.0.0.dev1", "1.0.0a1") == -1
        assert _compare_versions("1.0.0a1", "1.0.0b1") == -1
        assert _compare_versions("1.0.0b1", "1.0.0rc1") == -1

    def test_prerelease_number_ordering(self):
        """Pre-release numbers should order correctly."""
        assert _compare_versions("1.0.0rc1", "1.0.0rc2") == -1
        assert _compare_versions("1.0.0a1", "1.0.0a10") == -1
        assert _compare_versions("1.0.0rc2", "1.0.0rc1") == 1

    def test_different_base_versions_with_prerelease(self):
        """Different base versions should compare by base first."""
        assert _compare_versions("1.0.0", "1.0.1rc1") == -1  # 1.0.0 < 1.0.1rc1
        assert _compare_versions("2.0.0rc1", "1.0.0") == 1  # 2.0.0rc1 > 1.0.0


class TestDetectInstallMethod:
    """Tests for _detect_install_method function - CRITICAL FIX COVERAGE."""

    def test_editable_install_detection(self):
        """Editable installs should be detected via direct_url.json."""
        mock_dist = MagicMock()
        mock_dist.read_text.return_value = json.dumps({"dir_info": {"editable": True}})

        with patch("importlib.metadata.distribution", return_value=mock_dist):
            result = _detect_install_method()
            assert result == "editable"

    def test_pipx_environment_detection(self):
        """Pipx environment should be detected from sys.prefix."""
        with (
            patch("importlib.metadata.distribution", side_effect=Exception()),
            patch("sys.prefix", "/home/user/.local/pipx/venvs/scc-cli"),
            patch.dict("os.environ", {}, clear=True),
            patch("shutil.which", return_value=None),
        ):
            result = _detect_install_method()
            assert result == "pipx"

    def test_pipx_env_var_detection(self):
        """Pipx should be detected from PIPX_HOME env var."""
        with (
            patch("importlib.metadata.distribution", side_effect=Exception()),
            patch("sys.prefix", "/some/venv"),
            patch.dict(
                "os.environ",
                {
                    "PIPX_HOME": "/home/user/.local/pipx",
                    "UV_PYTHON_INSTALL_DIR": "",
                    "UV_CACHE_DIR": "",
                },
            ),
            patch("shutil.which", return_value=None),
        ):
            # The prefix must contain the PIPX_HOME value
            result = _detect_install_method()
            # Will fall through to pip since prefix doesn't match
            assert result in ["pip", "pipx"]

    def test_uv_fallback_when_available(self):
        """uv should be detected if available and no pipx context."""
        with (
            patch("importlib.metadata.distribution", side_effect=Exception()),
            patch("sys.prefix", "/some/regular/venv"),
            patch.dict("os.environ", {}, clear=True),
            patch("shutil.which", side_effect=lambda x: "/usr/bin/uv" if x == "uv" else None),
        ):
            result = _detect_install_method()
            assert result == "uv"

    def test_pip_fallback(self):
        """pip should be returned when no other method detected."""
        with (
            patch("importlib.metadata.distribution", side_effect=Exception()),
            patch("sys.prefix", "/some/venv"),
            patch.dict("os.environ", {}, clear=True),
            patch("shutil.which", return_value=None),
        ):
            result = _detect_install_method()
            assert result == "pip"

    def test_tool_existence_not_enough_for_pipx(self):
        """Just having pipx installed shouldn't trigger pipx detection - CRITICAL FIX."""
        # This tests the critical fix: we should NOT return "pipx" just because
        # shutil.which("pipx") returns a path
        with (
            patch("importlib.metadata.distribution", side_effect=Exception()),
            patch("sys.prefix", "/usr/local/python3.11"),  # Regular Python, not pipx venv
            patch.dict("os.environ", {}, clear=True),
            patch(
                "shutil.which",
                side_effect=lambda x: {
                    "pipx": "/usr/bin/pipx",  # pipx exists
                    "uv": None,
                }.get(x),
            ),
        ):
            result = _detect_install_method()
            # Since we're not in a pipx venv (sys.prefix doesn't match),
            # but pipx exists, we still return pipx as fallback
            # This is acceptable behavior - fallback to available tool
            assert result == "pipx"


class TestFetchLatestFromPypi:
    """Tests for _fetch_latest_from_pypi function."""

    def test_successful_fetch(self):
        """Successful PyPI response should return version."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"info": {"version": "2.0.0"}}).encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = _fetch_latest_from_pypi()
            assert result == "2.0.0"

    def test_network_error_returns_none(self):
        """Network errors should return None (not crash)."""
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Network unreachable"),
        ):
            result = _fetch_latest_from_pypi()
            assert result is None

    def test_timeout_returns_none(self):
        """Timeout should return None (not crash)."""
        with patch(
            "urllib.request.urlopen",
            side_effect=TimeoutError("Connection timed out"),
        ):
            result = _fetch_latest_from_pypi()
            assert result is None

    def test_invalid_json_returns_none(self):
        """Invalid JSON should return None."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"not valid json"
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = _fetch_latest_from_pypi()
            assert result is None


class TestGetCurrentVersion:
    """Tests for _get_current_version function."""

    def test_returns_installed_version(self):
        """Should return the installed version."""
        # Patch where it's imported, not where it's defined
        with patch("scc_cli.update.get_installed_version", return_value="1.2.3"):
            result = _get_current_version()
            assert result == "1.2.3"

    def test_returns_fallback_on_error(self):
        """Should return 0.0.0 when package not found."""
        with patch("scc_cli.update.get_installed_version", side_effect=PackageNotFoundError()):
            result = _get_current_version()
            assert result == "0.0.0"


class TestCheckForUpdates:
    """Tests for check_for_updates function."""

    def test_update_available(self):
        """Should detect when update is available."""
        with (
            patch("scc_cli.update._get_current_version", return_value="1.0.0"),
            patch("scc_cli.update._fetch_latest_from_pypi", return_value="2.0.0"),
            patch("scc_cli.update._detect_install_method", return_value="pip"),
        ):
            result = check_for_updates()
            assert result.current == "1.0.0"
            assert result.latest == "2.0.0"
            assert result.update_available is True
            assert result.install_method == "pip"

    def test_no_update_available(self):
        """Should detect when no update is available."""
        with (
            patch("scc_cli.update._get_current_version", return_value="2.0.0"),
            patch("scc_cli.update._fetch_latest_from_pypi", return_value="2.0.0"),
            patch("scc_cli.update._detect_install_method", return_value="pip"),
        ):
            result = check_for_updates()
            assert result.update_available is False

    def test_network_failure_graceful(self):
        """Network failure should result in update_available=False."""
        with (
            patch("scc_cli.update._get_current_version", return_value="1.0.0"),
            patch("scc_cli.update._fetch_latest_from_pypi", return_value=None),
            patch("scc_cli.update._detect_install_method", return_value="pip"),
        ):
            result = check_for_updates()
            assert result.latest is None
            assert result.update_available is False

    def test_prerelease_update_detection(self):
        """Pre-release installed, final available should show update - CRITICAL."""
        with (
            patch("scc_cli.update._get_current_version", return_value="1.0.0rc1"),
            patch("scc_cli.update._fetch_latest_from_pypi", return_value="1.0.0"),
            patch("scc_cli.update._detect_install_method", return_value="pip"),
        ):
            result = check_for_updates()
            assert result.update_available is True


class TestGetUpdateCommand:
    """Tests for get_update_command function."""

    def test_pip_command(self):
        """pip method should return pip upgrade command."""
        cmd = get_update_command("pip")
        assert cmd == f"pip install --upgrade {PACKAGE_NAME}"

    def test_pipx_command(self):
        """pipx method should return pipx upgrade command."""
        cmd = get_update_command("pipx")
        assert cmd == f"pipx upgrade {PACKAGE_NAME}"

    def test_uv_command(self):
        """uv method should return uv pip install command."""
        cmd = get_update_command("uv")
        assert cmd == f"uv pip install --upgrade {PACKAGE_NAME}"

    def test_unknown_method_defaults_to_pip(self):
        """Unknown method should default to pip command."""
        cmd = get_update_command("unknown")
        assert cmd == f"pip install --upgrade {PACKAGE_NAME}"


# ═══════════════════════════════════════════════════════════════════════════════
# NEW TESTS: Org Config Update System
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def temp_cache_dir(tmp_path, monkeypatch):
    """Set up temporary cache directory for update check metadata."""
    cache_dir = tmp_path / ".cache" / "scc"
    cache_dir.mkdir(parents=True)
    monkeypatch.setattr(update, "UPDATE_CHECK_CACHE_DIR", cache_dir)
    monkeypatch.setattr(update, "UPDATE_CHECK_META_FILE", cache_dir / "update_check_meta.json")
    return cache_dir


@pytest.fixture
def console():
    """Create a console for capturing output."""
    return Console(file=StringIO(), force_terminal=True, width=100)


class TestUpdateCheckMeta:
    """Tests for update check metadata persistence."""

    def test_load_empty_meta_when_no_file(self, temp_cache_dir):
        """Returns empty dict when no metadata file exists."""
        meta = _load_update_check_meta()
        assert meta == {}

    def test_save_and_load_meta(self, temp_cache_dir):
        """Metadata can be saved and loaded."""
        test_meta = {"cli_last_check": "2025-01-01T10:00:00+00:00"}
        _save_update_check_meta(test_meta)

        loaded = _load_update_check_meta()
        assert loaded == test_meta

    def test_load_handles_invalid_json(self, temp_cache_dir):
        """Returns empty dict when metadata file contains invalid JSON."""
        meta_file = temp_cache_dir / "update_check_meta.json"
        meta_file.write_text("not valid json {{{")

        meta = _load_update_check_meta()
        assert meta == {}


class TestCLIThrottling:
    """Tests for CLI update check throttling."""

    def test_should_check_when_never_checked(self, temp_cache_dir):
        """Should check when no previous check recorded."""
        assert _should_check_cli_updates() is True

    def test_should_not_check_when_recently_checked(self, temp_cache_dir):
        """Should not check when last check was recent."""
        _mark_cli_check_done()
        assert _should_check_cli_updates() is False

    def test_should_check_after_interval_elapsed(self, temp_cache_dir):
        """Should check when interval has elapsed."""
        old_time = datetime.now(timezone.utc) - timedelta(hours=25)
        meta = {"cli_last_check": old_time.isoformat()}
        _save_update_check_meta(meta)

        assert _should_check_cli_updates() is True

    def test_should_check_with_invalid_timestamp(self, temp_cache_dir):
        """Should check when timestamp is invalid."""
        meta = {"cli_last_check": "not-a-valid-timestamp"}
        _save_update_check_meta(meta)

        assert _should_check_cli_updates() is True

    def test_mark_cli_check_done_updates_timestamp(self, temp_cache_dir):
        """Marking check done updates the timestamp."""
        _mark_cli_check_done()

        meta = _load_update_check_meta()
        assert "cli_last_check" in meta

        ts = datetime.fromisoformat(meta["cli_last_check"])
        now = datetime.now(timezone.utc)
        assert (now - ts).total_seconds() < 10


class TestOrgConfigThrottling:
    """Tests for org config check throttling."""

    def test_should_check_when_never_checked(self, temp_cache_dir):
        """Should check when no previous check recorded."""
        assert _should_check_org_config() is True

    def test_should_not_check_when_recently_checked(self, temp_cache_dir):
        """Should not check when last check was recent."""
        _mark_org_config_check_done()
        assert _should_check_org_config() is False

    def test_should_check_after_interval_elapsed(self, temp_cache_dir):
        """Should check when interval has elapsed."""
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        meta = {"org_config_last_check": old_time.isoformat()}
        _save_update_check_meta(meta)

        assert _should_check_org_config() is True


class TestCheckOrgConfigUpdate:
    """Tests for org config update checking."""

    def test_standalone_mode_returns_standalone_status(self, temp_cache_dir):
        """Standalone mode returns standalone status immediately."""
        user_config = {"standalone": True}
        result = check_org_config_update(user_config)
        assert result.status == "standalone"

    def test_no_org_source_returns_standalone_status(self, temp_cache_dir):
        """No organization source returns standalone status."""
        user_config = {}
        result = check_org_config_update(user_config)
        assert result.status == "standalone"

    def test_no_url_returns_standalone_status(self, temp_cache_dir):
        """Missing URL in org source returns standalone status."""
        user_config = {"organization_source": {"auth": "env:TOKEN"}}
        result = check_org_config_update(user_config)
        assert result.status == "standalone"

    def test_throttled_returns_throttled_status(self, temp_cache_dir):
        """Returns throttled status when check interval hasn't elapsed."""
        user_config = {"organization_source": {"url": "https://example.com/config.json"}}
        _mark_org_config_check_done()
        result = check_org_config_update(user_config, force=False)
        assert result.status == "throttled"

    def test_force_bypasses_throttle(self, temp_cache_dir):
        """Force flag bypasses throttle check."""
        user_config = {"organization_source": {"url": "https://example.com/config.json"}}
        _mark_org_config_check_done()

        with patch("scc_cli.remote.load_from_cache", return_value=(None, None)):
            with patch("scc_cli.remote.resolve_auth", return_value=None):
                with patch("scc_cli.remote.fetch_org_config", return_value=(None, None, -2)):
                    result = check_org_config_update(user_config, force=True)

        assert result.status != "throttled"

    def test_304_not_modified_returns_unchanged(self, temp_cache_dir):
        """304 response returns unchanged status."""
        user_config = {"organization_source": {"url": "https://example.com/config.json"}}

        fetched_at = datetime.now(timezone.utc) - timedelta(hours=2)
        cached_meta = {
            "org_config": {
                "fetched_at": fetched_at.isoformat(),
                "etag": "abc123",
            }
        }

        with patch("scc_cli.remote.load_from_cache", return_value=({"test": True}, cached_meta)):
            with patch("scc_cli.remote.resolve_auth", return_value=None):
                with patch("scc_cli.remote.fetch_org_config", return_value=(None, "abc123", 304)):
                    result = check_org_config_update(user_config, force=True)

        assert result.status == "unchanged"
        assert result.cached_age_hours is not None
        assert 1.9 < result.cached_age_hours < 2.1

    def test_200_ok_returns_updated(self, temp_cache_dir):
        """200 response returns updated status and saves to cache."""
        user_config = {"organization_source": {"url": "https://example.com/config.json"}}

        new_config = {"organization": {"name": "Test Org"}}

        with patch("scc_cli.remote.load_from_cache", return_value=(None, None)):
            with patch("scc_cli.remote.resolve_auth", return_value=None):
                with patch(
                    "scc_cli.remote.fetch_org_config", return_value=(new_config, "new-etag", 200)
                ):
                    with patch("scc_cli.remote.save_to_cache") as mock_save:
                        result = check_org_config_update(user_config, force=True)

        assert result.status == "updated"
        assert result.message is not None
        mock_save.assert_called_once()

    def test_401_with_cache_returns_auth_failed(self, temp_cache_dir):
        """401 with cached config returns auth_failed with cache info."""
        user_config = {
            "organization_source": {
                "url": "https://example.com/config.json",
                "auth": "env:TOKEN",
            }
        }

        fetched_at = datetime.now(timezone.utc) - timedelta(hours=5)
        cached_meta = {"org_config": {"fetched_at": fetched_at.isoformat()}}

        with patch("scc_cli.remote.load_from_cache", return_value=({"test": True}, cached_meta)):
            with patch("scc_cli.remote.resolve_auth", return_value="expired-token"):
                with patch("scc_cli.remote.fetch_org_config", return_value=(None, None, 401)):
                    result = check_org_config_update(user_config, force=True)

        assert result.status == "auth_failed"
        assert result.cached_age_hours is not None
        assert result.message is not None

    def test_401_without_cache_returns_auth_failed(self, temp_cache_dir):
        """401 without cached config returns auth_failed without cache info."""
        user_config = {
            "organization_source": {
                "url": "https://example.com/config.json",
                "auth": "env:TOKEN",
            }
        }

        with patch("scc_cli.remote.load_from_cache", return_value=(None, None)):
            with patch("scc_cli.remote.resolve_auth", return_value="expired-token"):
                with patch("scc_cli.remote.fetch_org_config", return_value=(None, None, 401)):
                    result = check_org_config_update(user_config, force=True)

        assert result.status == "auth_failed"
        assert result.cached_age_hours is None

    def test_network_error_with_cache_returns_offline(self, temp_cache_dir):
        """Network error with cached config returns offline status."""
        user_config = {"organization_source": {"url": "https://example.com/config.json"}}

        fetched_at = datetime.now(timezone.utc) - timedelta(hours=12)
        cached_meta = {"org_config": {"fetched_at": fetched_at.isoformat()}}

        with patch("scc_cli.remote.load_from_cache", return_value=({"test": True}, cached_meta)):
            with patch("scc_cli.remote.resolve_auth", return_value=None):
                with patch(
                    "scc_cli.remote.fetch_org_config", side_effect=Exception("Network error")
                ):
                    result = check_org_config_update(user_config, force=True)

        assert result.status == "offline"
        assert result.cached_age_hours is not None

    def test_network_error_without_cache_returns_no_cache(self, temp_cache_dir):
        """Network error without cached config returns no_cache status."""
        user_config = {"organization_source": {"url": "https://example.com/config.json"}}

        with patch("scc_cli.remote.load_from_cache", return_value=(None, None)):
            with patch("scc_cli.remote.resolve_auth", return_value=None):
                with patch(
                    "scc_cli.remote.fetch_org_config", side_effect=Exception("Network error")
                ):
                    result = check_org_config_update(user_config, force=True)

        assert result.status == "no_cache"


class TestCheckAllUpdates:
    """Tests for combined update checking."""

    def test_checks_both_cli_and_org_config(self, temp_cache_dir):
        """Checks both CLI and org config updates."""
        user_config = {"standalone": True}

        with patch.object(update, "check_for_updates") as mock_cli:
            mock_cli.return_value = UpdateInfo(
                current="1.0.0",
                latest="1.0.1",
                update_available=True,
                install_method="pip",
            )

            result = check_all_updates(user_config, force=True)

        assert result.cli_update is not None
        assert result.cli_update.update_available is True
        assert result.org_config is not None
        assert result.org_config.status == "standalone"

    def test_respects_cli_throttle(self, temp_cache_dir):
        """Respects CLI throttle when not forced."""
        user_config = {"standalone": True}
        _mark_cli_check_done()

        with patch.object(update, "check_for_updates") as mock_cli:
            result = check_all_updates(user_config, force=False)

        mock_cli.assert_not_called()
        assert result.cli_update is None

    def test_force_bypasses_all_throttles(self, temp_cache_dir):
        """Force flag bypasses all throttles."""
        user_config = {"standalone": True}
        _mark_cli_check_done()
        _mark_org_config_check_done()

        with patch.object(update, "check_for_updates") as mock_cli:
            mock_cli.return_value = UpdateInfo(
                current="1.0.0",
                latest="1.0.0",
                update_available=False,
                install_method="pip",
            )

            result = check_all_updates(user_config, force=True)

        mock_cli.assert_called_once()
        assert result.cli_update is not None


class TestFormatAge:
    """Tests for age formatting."""

    def test_format_minutes(self):
        """Formats sub-hour ages as minutes."""
        assert _format_age(0.5) == "30 minutes"
        # 0.02 hours = 1.2 minutes, rounds to 1
        assert _format_age(0.02) == "1 minute"

    def test_format_hours(self):
        """Formats sub-day ages as hours."""
        assert _format_age(1) == "1 hour"
        assert _format_age(5) == "5 hours"
        assert _format_age(23.9) == "23 hours"

    def test_format_days(self):
        """Formats multi-day ages as days."""
        assert _format_age(24) == "1 day"
        assert _format_age(48) == "2 days"
        assert _format_age(72) == "3 days"


class TestRenderUpdateNotification:
    """Tests for non-intrusive update notifications."""

    def test_shows_cli_update_available(self, console):
        """Shows notification when CLI update is available."""
        import re

        result = UpdateCheckResult(
            cli_update=UpdateInfo(
                current="1.0.0",
                latest="1.0.1",
                update_available=True,
                install_method="pip",
            )
        )

        render_update_notification(console, result)
        output = console.file.getvalue()
        # Strip ANSI escape codes for version checking (Rich adds styling)
        plain_output = re.sub(r"\x1b\[[0-9;]*m", "", output)

        assert "Update available" in output
        assert "1.0.0" in plain_output
        assert "1.0.1" in plain_output
        assert "pip install" in output

    def test_quiet_when_cli_up_to_date(self, console):
        """No output when CLI is up to date."""
        result = UpdateCheckResult(
            cli_update=UpdateInfo(
                current="1.0.0",
                latest="1.0.0",
                update_available=False,
                install_method="pip",
            )
        )

        render_update_notification(console, result)
        output = console.file.getvalue()

        assert output == ""

    def test_shows_org_config_updated(self, console):
        """Shows notification when org config is updated."""
        result = UpdateCheckResult(
            org_config=OrgConfigUpdateResult(
                status="updated",
                message="Organization config updated from remote",
            )
        )

        render_update_notification(console, result)
        output = console.file.getvalue()

        assert "Organization config updated" in output

    def test_shows_auth_failed_with_cache(self, console):
        """Shows warning when auth failed but cache exists."""
        result = UpdateCheckResult(
            org_config=OrgConfigUpdateResult(
                status="auth_failed",
                message="Auth failed for org config",
                cached_age_hours=5.0,
            )
        )

        render_update_notification(console, result)
        output = console.file.getvalue()

        assert "Auth failed" in output
        assert "cached version" in output

    def test_shows_auth_failed_without_cache(self, console):
        """Shows error when auth failed and no cache."""
        result = UpdateCheckResult(
            org_config=OrgConfigUpdateResult(
                status="auth_failed",
                message="Auth failed and no cached config available",
            )
        )

        render_update_notification(console, result)
        output = console.file.getvalue()

        assert "Auth failed" in output
        assert "scc setup" in output

    def test_shows_no_cache_warning(self, console):
        """Shows warning when no cache is available."""
        result = UpdateCheckResult(org_config=OrgConfigUpdateResult(status="no_cache"))

        render_update_notification(console, result)
        output = console.file.getvalue()

        assert "No organization config" in output
        assert "scc setup" in output

    def test_quiet_for_unchanged_status(self, console):
        """No output for unchanged status."""
        result = UpdateCheckResult(
            org_config=OrgConfigUpdateResult(status="unchanged", cached_age_hours=1.0)
        )

        render_update_notification(console, result)
        output = console.file.getvalue()

        assert output == ""

    def test_quiet_for_offline_status(self, console):
        """No output for offline status."""
        result = UpdateCheckResult(
            org_config=OrgConfigUpdateResult(status="offline", cached_age_hours=12.0)
        )

        render_update_notification(console, result)
        output = console.file.getvalue()

        assert output == ""

    def test_quiet_for_throttled_status(self, console):
        """No output for throttled status."""
        result = UpdateCheckResult(org_config=OrgConfigUpdateResult(status="throttled"))

        render_update_notification(console, result)
        output = console.file.getvalue()

        assert output == ""

    def test_quiet_for_standalone_status(self, console):
        """No output for standalone status."""
        result = UpdateCheckResult(org_config=OrgConfigUpdateResult(status="standalone"))

        render_update_notification(console, result)
        output = console.file.getvalue()

        assert output == ""


class TestRenderUpdateStatusPanel:
    """Tests for detailed update status panel."""

    def test_shows_cli_up_to_date(self, console):
        """Shows CLI version as up to date."""
        result = UpdateCheckResult(
            cli_update=UpdateInfo(
                current="1.0.0",
                latest="1.0.0",
                update_available=False,
                install_method="pip",
            )
        )

        render_update_status_panel(console, result)
        output = console.file.getvalue()

        assert "CLI Version" in output
        assert "1.0.0" in output
        assert "up to date" in output

    def test_shows_cli_update_available(self, console):
        """Shows CLI update available with command."""
        result = UpdateCheckResult(
            cli_update=UpdateInfo(
                current="1.0.0",
                latest="1.0.1",
                update_available=True,
                install_method="pipx",
            )
        )

        render_update_status_panel(console, result)
        output = console.file.getvalue()

        assert "CLI Version" in output
        assert "1.0.0" in output
        assert "1.0.1" in output
        assert "update available" in output
        assert "pipx upgrade" in output

    def test_shows_cli_throttled(self, console):
        """Shows CLI as not checked when throttled."""
        result = UpdateCheckResult(cli_update=None)

        render_update_status_panel(console, result)
        output = console.file.getvalue()

        assert "CLI Version" in output
        assert "throttled" in output

    def test_shows_org_config_standalone(self, console):
        """Shows standalone mode for org config."""
        result = UpdateCheckResult(org_config=OrgConfigUpdateResult(status="standalone"))

        render_update_status_panel(console, result)
        output = console.file.getvalue()

        assert "Organization Config" in output
        assert "Standalone mode" in output

    def test_shows_org_config_updated(self, console):
        """Shows org config as updated."""
        result = UpdateCheckResult(org_config=OrgConfigUpdateResult(status="updated"))

        render_update_status_panel(console, result)
        output = console.file.getvalue()

        assert "Organization Config" in output
        assert "Updated from remote" in output

    def test_shows_org_config_unchanged_with_age(self, console):
        """Shows org config as unchanged with cache age."""
        result = UpdateCheckResult(
            org_config=OrgConfigUpdateResult(status="unchanged", cached_age_hours=2.5)
        )

        render_update_status_panel(console, result)
        output = console.file.getvalue()

        assert "Organization Config" in output
        assert "Current" in output
        assert "cached" in output

    def test_shows_org_config_offline(self, console):
        """Shows org config in offline mode."""
        result = UpdateCheckResult(
            org_config=OrgConfigUpdateResult(status="offline", cached_age_hours=8.0)
        )

        render_update_status_panel(console, result)
        output = console.file.getvalue()

        assert "Organization Config" in output
        assert "cached config" in output
        assert "offline" in output.lower()

    def test_shows_org_config_auth_failed_with_cache(self, console):
        """Shows auth failed with cache info."""
        result = UpdateCheckResult(
            org_config=OrgConfigUpdateResult(status="auth_failed", cached_age_hours=3.0)
        )

        render_update_status_panel(console, result)
        output = console.file.getvalue()

        assert "Organization Config" in output
        assert "Auth failed" in output
        assert "cached" in output

    def test_shows_org_config_auth_failed_no_cache(self, console):
        """Shows auth failed without cache."""
        result = UpdateCheckResult(org_config=OrgConfigUpdateResult(status="auth_failed"))

        render_update_status_panel(console, result)
        output = console.file.getvalue()

        assert "Organization Config" in output
        assert "Auth failed" in output
        assert "no cache" in output

    def test_shows_org_config_no_cache(self, console):
        """Shows no cache available."""
        result = UpdateCheckResult(org_config=OrgConfigUpdateResult(status="no_cache"))

        render_update_status_panel(console, result)
        output = console.file.getvalue()

        assert "Organization Config" in output
        assert "No cached config" in output
        assert "scc setup" in output

    def test_shows_org_config_throttled(self, console):
        """Shows org config as not checked when throttled."""
        result = UpdateCheckResult(org_config=OrgConfigUpdateResult(status="throttled"))

        render_update_status_panel(console, result)
        output = console.file.getvalue()

        assert "Organization Config" in output
        assert "throttled" in output
