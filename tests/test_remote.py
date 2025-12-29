"""Tests for remote module.

Tests HTTP fetching, auth resolution, and caching for organization configs.
Uses the `responses` library for HTTP mocking.
"""

import copy
import hashlib
import json
import os
from datetime import datetime, timezone
from unittest import mock

import pytest
import responses

from scc_cli import remote

# ═══════════════════════════════════════════════════════════════════════════════
# Test Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_org_config():
    """Create a sample organization config."""
    return {
        "schema_version": "1.0.0",
        "organization": {
            "name": "Test Organization",
            "id": "test-org",
        },
        "marketplaces": [
            {
                "name": "internal",
                "type": "gitlab",
                "host": "gitlab.example.org",
                "repo": "group/claude-marketplace",
                "auth": "env:GITLAB_TOKEN",
            }
        ],
        "profiles": {
            "platform": {
                "description": "Platform team",
                "plugin": "platform",
                "marketplace": "internal",
            }
        },
        "defaults": {"cache_ttl_hours": 24},
    }


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary cache directory."""
    cache_dir = tmp_path / ".cache" / "scc"
    cache_dir.mkdir(parents=True)
    return cache_dir


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary config directory."""
    config_dir = tmp_path / ".config" / "scc"
    config_dir.mkdir(parents=True)
    return config_dir


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for validate_org_config_url
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateOrgConfigUrl:
    """Tests for validate_org_config_url function."""

    def test_valid_https_url(self):
        """Should accept valid HTTPS URLs."""
        url = "https://gitlab.example.org/devops/scc-config.json"
        result = remote.validate_org_config_url(url)
        assert result == url

    def test_strips_whitespace(self):
        """Should strip whitespace from URL."""
        url = "  https://example.org/config.json  "
        result = remote.validate_org_config_url(url)
        assert result == "https://example.org/config.json"

    def test_rejects_http_url(self):
        """Should reject HTTP URLs for security."""
        url = "http://example.org/config.json"
        with pytest.raises(ValueError, match="HTTP not allowed"):
            remote.validate_org_config_url(url)

    def test_rejects_ssh_git_url(self):
        """Should reject git@ SSH URLs."""
        url = "git@github.com:org/repo.git"
        with pytest.raises(ValueError, match="SSH URL not supported"):
            remote.validate_org_config_url(url)

    def test_rejects_ssh_protocol_url(self):
        """Should reject ssh:// URLs."""
        url = "ssh://git@github.com/org/repo.git"
        with pytest.raises(ValueError, match="SSH URL not supported"):
            remote.validate_org_config_url(url)

    def test_rejects_file_url(self):
        """Should reject file:// URLs."""
        url = "file:///etc/passwd"
        with pytest.raises(ValueError, match="Invalid URL scheme"):
            remote.validate_org_config_url(url)

    def test_rejects_no_scheme(self):
        """Should reject URLs without scheme."""
        url = "example.org/config.json"
        with pytest.raises(ValueError, match="Invalid URL scheme"):
            remote.validate_org_config_url(url)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for resolve_auth (simple version for remote.py)
# ═══════════════════════════════════════════════════════════════════════════════


class TestResolveAuth:
    """Tests for resolve_auth function."""

    def test_resolve_env_auth(self):
        """Should resolve env:VAR_NAME auth spec."""
        with mock.patch.dict(os.environ, {"MY_TOKEN": "secret123"}):
            token = remote.resolve_auth("env:MY_TOKEN")
            assert token == "secret123"

    def test_resolve_env_auth_missing(self):
        """Should return None for missing env var."""
        with mock.patch.dict(os.environ, {}, clear=True):
            token = remote.resolve_auth("env:MISSING_VAR")
            assert token is None

    def test_resolve_env_auth_strips_whitespace(self):
        """Should strip whitespace from token."""
        with mock.patch.dict(os.environ, {"MY_TOKEN": "  secret  \n"}):
            token = remote.resolve_auth("env:MY_TOKEN")
            assert token == "secret"

    def test_resolve_command_auth(self):
        """Should resolve command:CMD auth spec."""
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "command-secret\n"

            token = remote.resolve_auth("command:echo secret")
            assert token == "command-secret"

    def test_resolve_command_auth_failure(self):
        """Should return None for failed command."""
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""

            token = remote.resolve_auth("command:failing-cmd")
            assert token is None

    def test_resolve_none_auth(self):
        """Should return None for null auth spec."""
        token = remote.resolve_auth(None)
        assert token is None

    def test_resolve_empty_auth(self):
        """Should return None for empty auth spec."""
        token = remote.resolve_auth("")
        assert token is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for fetch_org_config
# ═══════════════════════════════════════════════════════════════════════════════


class TestFetchOrgConfig:
    """Tests for fetch_org_config function with HTTP mocking."""

    @responses.activate
    def test_fetch_success(self, sample_org_config):
        """Should fetch org config successfully."""
        url = "https://example.org/config.json"
        responses.add(
            responses.GET,
            url,
            json=sample_org_config,
            status=200,
            headers={"ETag": '"abc123"'},
        )

        config, etag, status = remote.fetch_org_config(url, auth=None, etag=None)

        assert status == 200
        assert config["organization"]["name"] == "Test Organization"
        assert etag == '"abc123"'

    @responses.activate
    def test_fetch_with_auth_header(self):
        """Should include Authorization header when auth provided."""
        url = "https://example.org/config.json"
        responses.add(
            responses.GET,
            url,
            json={"organization": {"name": "Test"}},
            status=200,
        )

        remote.fetch_org_config(url, auth="my-token", etag=None)

        # Verify Authorization header was sent
        assert len(responses.calls) == 1
        assert "Authorization" in responses.calls[0].request.headers
        assert "Bearer my-token" in responses.calls[0].request.headers["Authorization"]

    @responses.activate
    def test_fetch_with_etag_sends_if_none_match(self, sample_org_config):
        """Should send If-None-Match header when etag provided."""
        url = "https://example.org/config.json"
        responses.add(
            responses.GET,
            url,
            json=sample_org_config,
            status=200,
        )

        remote.fetch_org_config(url, auth=None, etag='"cached-etag"')

        # Verify If-None-Match header was sent
        assert "If-None-Match" in responses.calls[0].request.headers
        assert responses.calls[0].request.headers["If-None-Match"] == '"cached-etag"'

    @responses.activate
    def test_fetch_304_not_modified(self):
        """Should return None config for 304 Not Modified."""
        url = "https://example.org/config.json"
        responses.add(
            responses.GET,
            url,
            status=304,
        )

        config, etag, status = remote.fetch_org_config(url, auth=None, etag='"cached-etag"')

        assert status == 304
        assert config is None  # Use cached version

    @responses.activate
    def test_fetch_401_unauthorized(self):
        """Should return auth error for 401."""
        url = "https://example.org/config.json"
        responses.add(
            responses.GET,
            url,
            status=401,
            body="Unauthorized",
        )

        config, etag, status = remote.fetch_org_config(url, auth=None, etag=None)

        assert status == 401
        assert config is None

    @responses.activate
    def test_fetch_403_forbidden(self):
        """Should return auth error for 403."""
        url = "https://example.org/config.json"
        responses.add(
            responses.GET,
            url,
            status=403,
            body="Forbidden",
        )

        config, etag, status = remote.fetch_org_config(url, auth=None, etag=None)

        assert status == 403
        assert config is None

    @responses.activate
    def test_fetch_404_not_found(self):
        """Should return error for 404."""
        url = "https://example.org/config.json"
        responses.add(
            responses.GET,
            url,
            status=404,
        )

        config, etag, status = remote.fetch_org_config(url, auth=None, etag=None)

        assert status == 404
        assert config is None

    @responses.activate
    def test_fetch_invalid_json(self):
        """Should handle invalid JSON response."""
        url = "https://example.org/config.json"
        responses.add(
            responses.GET,
            url,
            body="not valid json",
            status=200,
        )

        config, etag, status = remote.fetch_org_config(url, auth=None, etag=None)

        # Should return None for invalid JSON with special status
        assert config is None

    def test_fetch_rejects_http_url(self):
        """Should reject HTTP URLs before fetching."""
        with pytest.raises(ValueError, match="HTTP not allowed"):
            remote.fetch_org_config("http://example.org/config.json", auth=None)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for cache operations
# ═══════════════════════════════════════════════════════════════════════════════


class TestCacheOperations:
    """Tests for cache save and load operations."""

    def test_save_to_cache(self, sample_org_config, temp_cache_dir, monkeypatch):
        """Should save org config and metadata to cache."""
        monkeypatch.setattr(remote, "CACHE_DIR", temp_cache_dir)

        remote.save_to_cache(
            org_config=sample_org_config,
            source_url="https://example.org/config.json",
            etag='"abc123"',
            ttl_hours=24,
        )

        # Check org config file exists
        config_file = temp_cache_dir / "org_config.json"
        assert config_file.exists()

        # Check metadata file exists
        meta_file = temp_cache_dir / "cache_meta.json"
        assert meta_file.exists()

        # Verify metadata content
        meta = json.loads(meta_file.read_text())
        assert meta["org_config"]["source_url"] == "https://example.org/config.json"
        assert meta["org_config"]["etag"] == '"abc123"'
        assert "fetched_at" in meta["org_config"]
        assert "expires_at" in meta["org_config"]
        assert "fingerprint" in meta["org_config"]

    def test_save_to_cache_creates_directory(self, sample_org_config, tmp_path, monkeypatch):
        """Should create cache directory if it doesn't exist."""
        cache_dir = tmp_path / "new_cache" / "scc"
        monkeypatch.setattr(remote, "CACHE_DIR", cache_dir)

        remote.save_to_cache(
            org_config=sample_org_config,
            source_url="https://example.org/config.json",
            etag=None,
            ttl_hours=24,
        )

        assert cache_dir.exists()
        assert (cache_dir / "org_config.json").exists()

    def test_load_from_cache(self, sample_org_config, temp_cache_dir, monkeypatch):
        """Should load cached org config and metadata."""
        monkeypatch.setattr(remote, "CACHE_DIR", temp_cache_dir)

        # Write test files
        config_file = temp_cache_dir / "org_config.json"
        config_file.write_text(json.dumps(sample_org_config))

        meta = {
            "org_config": {
                "source_url": "https://example.org/config.json",
                "fetched_at": "2025-12-17T10:00:00Z",
                "expires_at": "2025-12-18T10:00:00Z",
                "etag": '"abc123"',
            }
        }
        meta_file = temp_cache_dir / "cache_meta.json"
        meta_file.write_text(json.dumps(meta))

        config, loaded_meta = remote.load_from_cache()

        assert config is not None
        assert config["organization"]["name"] == "Test Organization"
        assert loaded_meta["org_config"]["etag"] == '"abc123"'

    def test_load_from_cache_missing_files(self, temp_cache_dir, monkeypatch):
        """Should return None if cache files don't exist."""
        monkeypatch.setattr(remote, "CACHE_DIR", temp_cache_dir)

        config, meta = remote.load_from_cache()

        assert config is None
        assert meta is None

    def test_load_from_cache_corrupted_json(self, temp_cache_dir, monkeypatch):
        """Should return None for corrupted cache files."""
        monkeypatch.setattr(remote, "CACHE_DIR", temp_cache_dir)

        # Write corrupted files
        (temp_cache_dir / "org_config.json").write_text("not valid json")
        (temp_cache_dir / "cache_meta.json").write_text("{}")

        config, meta = remote.load_from_cache()

        assert config is None


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for is_cache_valid
# ═══════════════════════════════════════════════════════════════════════════════


class TestIsCacheValid:
    """Tests for is_cache_valid function."""

    def test_cache_valid_within_ttl(self):
        """Should return True for cache within TTL."""
        # Expires in the future
        future_time = datetime.now(timezone.utc).replace(microsecond=0)
        future_time = future_time.replace(year=future_time.year + 1)

        meta = {"org_config": {"expires_at": future_time.isoformat()}}

        assert remote.is_cache_valid(meta) is True

    def test_cache_expired(self):
        """Should return False for expired cache."""
        # Expired in the past
        past_time = datetime.now(timezone.utc).replace(microsecond=0)
        past_time = past_time.replace(year=past_time.year - 1)

        meta = {"org_config": {"expires_at": past_time.isoformat()}}

        assert remote.is_cache_valid(meta) is False

    def test_cache_valid_with_naive_datetime(self):
        """Naive datetime should be treated as UTC for cache validity."""
        future_time = datetime.now().replace(microsecond=0)
        future_time = future_time.replace(year=future_time.year + 1)

        meta = {"org_config": {"expires_at": future_time.isoformat()}}

        assert remote.is_cache_valid(meta) is True

    def test_cache_missing_expires_at(self):
        """Should return False if expires_at is missing."""
        meta = {"org_config": {}}
        assert remote.is_cache_valid(meta) is False

    def test_cache_none_meta(self):
        """Should return False for None metadata."""
        assert remote.is_cache_valid(None) is False

    def test_cache_empty_meta(self):
        """Should return False for empty metadata."""
        assert remote.is_cache_valid({}) is False


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for load_org_config (main entry point)
# ═══════════════════════════════════════════════════════════════════════════════


class TestLoadOrgConfig:
    """Tests for load_org_config main entry point."""

    def test_standalone_mode_returns_none(self):
        """Should return None in standalone mode."""
        user_config = {"standalone": True}

        config = remote.load_org_config(user_config)

        assert config is None

    def test_missing_organization_source_returns_none(self):
        """Should return None if no organization_source configured."""
        user_config = {}

        config = remote.load_org_config(user_config)

        assert config is None

    def test_fetch_failure_with_cache_warns_and_returns_cache(self, sample_org_config):
        """Fetch failure should warn and fall back to stale cache."""
        user_config = {
            "organization_source": {
                "url": "https://example.org/config.json",
                "auth": None,
            },
        }
        meta = {
            "org_config": {
                "etag": '"etag"',
                "expires_at": "2020-01-01T00:00:00+00:00",
            }
        }

        with (
            mock.patch("scc_cli.remote.load_from_cache", return_value=(sample_org_config, meta)),
            mock.patch("scc_cli.remote.is_cache_valid", return_value=False),
            mock.patch("scc_cli.remote.fetch_org_config", return_value=(None, None, -2)),
            mock.patch("scc_cli.remote.print_human") as mock_print,
        ):
            config = remote.load_org_config(user_config)

        assert config == sample_org_config
        mock_print.assert_called()

    @responses.activate
    def test_fetches_from_remote_when_cache_expired(
        self, sample_org_config, temp_cache_dir, monkeypatch
    ):
        """Should fetch from remote when cache is expired."""
        monkeypatch.setattr(remote, "CACHE_DIR", temp_cache_dir)

        url = "https://example.org/config.json"
        responses.add(
            responses.GET,
            url,
            json=sample_org_config,
            status=200,
            headers={"ETag": '"new-etag"'},
        )

        user_config = {
            "organization_source": {"url": url, "auth": None},
        }

        config = remote.load_org_config(user_config)

        assert config is not None
        assert config["organization"]["name"] == "Test Organization"
        assert len(responses.calls) == 1

    def test_uses_cache_when_valid(self, sample_org_config, temp_cache_dir, monkeypatch):
        """Should use cache when within TTL."""
        monkeypatch.setattr(remote, "CACHE_DIR", temp_cache_dir)

        # Set up valid cache
        config_file = temp_cache_dir / "org_config.json"
        config_file.write_text(json.dumps(sample_org_config))

        # Expires in the future
        future_time = datetime.now(timezone.utc).replace(microsecond=0)
        future_time = future_time.replace(year=future_time.year + 1)

        meta = {
            "org_config": {
                "source_url": "https://example.org/config.json",
                "expires_at": future_time.isoformat(),
                "etag": '"cached-etag"',
            }
        }
        (temp_cache_dir / "cache_meta.json").write_text(json.dumps(meta))

        user_config = {
            "organization_source": {
                "url": "https://example.org/config.json",
                "auth": None,
            },
        }

        config = remote.load_org_config(user_config)

        assert config is not None
        assert config["organization"]["name"] == "Test Organization"
        # No HTTP calls made - used cache

    @responses.activate
    def test_force_refresh_bypasses_cache(self, sample_org_config, temp_cache_dir, monkeypatch):
        """Should bypass cache when force_refresh=True."""
        monkeypatch.setattr(remote, "CACHE_DIR", temp_cache_dir)

        # Set up valid cache
        cached_config = {**sample_org_config, "organization": {"name": "Cached Org"}}
        config_file = temp_cache_dir / "org_config.json"
        config_file.write_text(json.dumps(cached_config))

        future_time = datetime.now(timezone.utc).replace(microsecond=0)
        future_time = future_time.replace(year=future_time.year + 1)

        meta = {
            "org_config": {
                "source_url": "https://example.org/config.json",
                "expires_at": future_time.isoformat(),
                "etag": '"cached-etag"',
            }
        }
        (temp_cache_dir / "cache_meta.json").write_text(json.dumps(meta))

        # Set up remote response with different content
        url = "https://example.org/config.json"
        responses.add(
            responses.GET,
            url,
            json=sample_org_config,
            status=200,
        )

        user_config = {
            "organization_source": {"url": url, "auth": None},
        }

        config = remote.load_org_config(user_config, force_refresh=True)

        assert config is not None
        assert config["organization"]["name"] == "Test Organization"  # Fresh content
        assert len(responses.calls) == 1

    def test_offline_mode_uses_cache_only(self, sample_org_config, temp_cache_dir, monkeypatch):
        """Should use cache only in offline mode."""
        monkeypatch.setattr(remote, "CACHE_DIR", temp_cache_dir)

        # Set up expired cache (would normally trigger fetch)
        config_file = temp_cache_dir / "org_config.json"
        config_file.write_text(json.dumps(sample_org_config))

        past_time = datetime.now(timezone.utc).replace(microsecond=0)
        past_time = past_time.replace(year=past_time.year - 1)

        meta = {
            "org_config": {
                "source_url": "https://example.org/config.json",
                "expires_at": past_time.isoformat(),  # Expired
            }
        }
        (temp_cache_dir / "cache_meta.json").write_text(json.dumps(meta))

        user_config = {
            "organization_source": {
                "url": "https://example.org/config.json",
                "auth": None,
            },
        }

        config = remote.load_org_config(user_config, offline=True)

        assert config is not None  # Uses stale cache in offline mode

    def test_offline_mode_no_cache_raises(self, temp_cache_dir, monkeypatch):
        """Should raise error in offline mode with no cache."""
        monkeypatch.setattr(remote, "CACHE_DIR", temp_cache_dir)

        user_config = {
            "organization_source": {
                "url": "https://example.org/config.json",
                "auth": None,
            },
        }

        with pytest.raises(remote.CacheNotFoundError):
            remote.load_org_config(user_config, offline=True)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for fingerprint calculation
# ═══════════════════════════════════════════════════════════════════════════════


class TestFingerprint:
    """Tests for cache fingerprint calculation."""

    def test_fingerprint_is_sha256(self, sample_org_config, temp_cache_dir, monkeypatch):
        """Fingerprint should be SHA256 hash of cached content."""
        monkeypatch.setattr(remote, "CACHE_DIR", temp_cache_dir)

        remote.save_to_cache(
            org_config=sample_org_config,
            source_url="https://example.org/config.json",
            etag=None,
            ttl_hours=24,
        )

        meta_file = temp_cache_dir / "cache_meta.json"
        meta = json.loads(meta_file.read_text())

        # Verify fingerprint is present and is a valid hex string
        fingerprint = meta["org_config"]["fingerprint"]
        assert len(fingerprint) == 64  # SHA256 produces 64 hex chars
        assert all(c in "0123456789abcdef" for c in fingerprint)

    def test_fingerprint_matches_content(self, sample_org_config, temp_cache_dir, monkeypatch):
        """Fingerprint should match SHA256 of config file content."""
        monkeypatch.setattr(remote, "CACHE_DIR", temp_cache_dir)

        remote.save_to_cache(
            org_config=sample_org_config,
            source_url="https://example.org/config.json",
            etag=None,
            ttl_hours=24,
        )

        # Read back and verify fingerprint
        config_file = temp_cache_dir / "org_config.json"
        config_content = config_file.read_bytes()
        expected_fingerprint = hashlib.sha256(config_content).hexdigest()

        meta_file = temp_cache_dir / "cache_meta.json"
        meta = json.loads(meta_file.read_text())

        assert meta["org_config"]["fingerprint"] == expected_fingerprint


# ═══════════════════════════════════════════════════════════════════════════════
# Tests for Validation Gate
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidationGate:
    """Tests for validation gate at config loading entry point.

    The validation gate validates configs both structurally (JSON Schema)
    and semantically (governance invariants) BEFORE caching.
    """

    @responses.activate
    def test_valid_config_passes_validation_gate(
        self, sample_org_config, temp_cache_dir, monkeypatch
    ):
        """Valid config should pass validation gate and be cached."""
        monkeypatch.setattr(remote, "CACHE_DIR", temp_cache_dir)

        url = "https://example.org/config.json"
        responses.add(
            responses.GET,
            url,
            json=sample_org_config,
            status=200,
            headers={"ETag": '"test-etag"'},
        )

        user_config = {"organization_source": {"url": url, "auth": None}}
        config = remote.load_org_config(user_config)

        # Config should be returned
        assert config is not None
        assert config["organization"]["name"] == "Test Organization"

        # Config should be cached
        cache_file = temp_cache_dir / "org_config.json"
        assert cache_file.exists()

    @responses.activate
    def test_incompatible_min_cli_version_raises(
        self, sample_org_config, temp_cache_dir, monkeypatch
    ):
        """Incompatible min_cli_version should raise ConfigValidationError."""
        monkeypatch.setattr(remote, "CACHE_DIR", temp_cache_dir)

        incompatible = copy.deepcopy(sample_org_config)
        incompatible["min_cli_version"] = "99.0.0"

        url = "https://example.org/config.json"
        responses.add(
            responses.GET,
            url,
            json=incompatible,
            status=200,
            headers={"ETag": '"test-etag"'},
        )

        user_config = {"organization_source": {"url": url, "auth": None}}

        with pytest.raises(remote.ConfigValidationError):
            remote.load_org_config(user_config)

        cache_file = temp_cache_dir / "org_config.json"
        assert not cache_file.exists()

    @responses.activate
    def test_schema_error_raises_config_validation_error(self, temp_cache_dir, monkeypatch):
        """Config with schema errors should raise ConfigValidationError."""
        monkeypatch.setattr(remote, "CACHE_DIR", temp_cache_dir)

        # Config missing required 'organization' field
        invalid_config = {
            "schema_version": "1.0.0",
            # Missing 'organization' - required by schema
        }

        url = "https://example.org/config.json"
        responses.add(
            responses.GET,
            url,
            json=invalid_config,
            status=200,
        )

        user_config = {"organization_source": {"url": url, "auth": None}}

        with pytest.raises(remote.ConfigValidationError) as exc_info:
            remote.load_org_config(user_config)

        # Error should mention schema validation
        assert (
            "schema" in str(exc_info.value).lower() or "organization" in str(exc_info.value).lower()
        )

        # Invalid config should NOT be cached
        cache_file = temp_cache_dir / "org_config.json"
        assert not cache_file.exists()

    @responses.activate
    def test_invariant_violation_raises_config_validation_error(self, temp_cache_dir, monkeypatch):
        """Config with invariant violations should raise ConfigValidationError."""
        monkeypatch.setattr(remote, "CACHE_DIR", temp_cache_dir)

        # Config that violates enabled ⊆ allowed invariant
        invalid_config = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test Org", "id": "test-org"},
            "defaults": {
                "enabled_plugins": ["plugin-a@marketplace"],
                "allowed_plugins": [],  # Empty = nothing allowed, but plugin-a enabled
            },
        }

        url = "https://example.org/config.json"
        responses.add(
            responses.GET,
            url,
            json=invalid_config,
            status=200,
        )

        user_config = {"organization_source": {"url": url, "auth": None}}

        with pytest.raises(remote.ConfigValidationError) as exc_info:
            remote.load_org_config(user_config)

        # Error should mention invariant violation
        assert (
            "invariant" in str(exc_info.value).lower() or "allowed" in str(exc_info.value).lower()
        )

        # Invalid config should NOT be cached
        cache_file = temp_cache_dir / "org_config.json"
        assert not cache_file.exists()

    @responses.activate
    def test_blocked_plugin_violation_raises_error(self, temp_cache_dir, monkeypatch):
        """Config with enabled plugin matching blocked pattern should raise error."""
        monkeypatch.setattr(remote, "CACHE_DIR", temp_cache_dir)

        # Config that violates enabled ∩ blocked = ∅ invariant
        invalid_config = {
            "schema_version": "1.0.0",
            "organization": {"name": "Test Org", "id": "test-org"},
            "defaults": {
                "enabled_plugins": ["malicious-plugin@marketplace"],
                # allowed_plugins missing = unrestricted
            },
            "security": {
                "blocked_plugins": ["malicious-*"],
            },
        }

        url = "https://example.org/config.json"
        responses.add(
            responses.GET,
            url,
            json=invalid_config,
            status=200,
        )

        user_config = {"organization_source": {"url": url, "auth": None}}

        with pytest.raises(remote.ConfigValidationError) as exc_info:
            remote.load_org_config(user_config)

        # Error should mention blocked plugin
        assert (
            "blocked" in str(exc_info.value).lower() or "malicious" in str(exc_info.value).lower()
        )

        # Invalid config should NOT be cached
        cache_file = temp_cache_dir / "org_config.json"
        assert not cache_file.exists()
