"""Characterization tests for marketplace/materialize.py.

Lock current behavior of name validation, dataclass serialization,
manifest I/O, and cache freshness before S02 surgery.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scc_cli.marketplace.materialize import (
    CloneResult,
    DiscoveryResult,
    DownloadResult,
    InvalidMarketplaceError,
    MaterializationError,
    MaterializedMarketplace,
    _validate_marketplace_name,
    is_cache_fresh,
    load_manifest,
    save_manifest,
)

# ═══════════════════════════════════════════════════════════════════════════════
# _validate_marketplace_name
# ═══════════════════════════════════════════════════════════════════════════════


class TestValidateMarketplaceName:
    """Marketplace name filesystem-safety validation."""

    def test_valid_name(self) -> None:
        _validate_marketplace_name("my-marketplace")  # should not raise

    def test_empty_name_raises(self) -> None:
        with pytest.raises(InvalidMarketplaceError):
            _validate_marketplace_name("")

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(InvalidMarketplaceError):
            _validate_marketplace_name("   ")

    def test_dot_raises(self) -> None:
        with pytest.raises(InvalidMarketplaceError):
            _validate_marketplace_name(".")

    def test_dotdot_raises(self) -> None:
        with pytest.raises(InvalidMarketplaceError):
            _validate_marketplace_name("..")

    def test_slash_raises(self) -> None:
        with pytest.raises(InvalidMarketplaceError):
            _validate_marketplace_name("path/traversal")

    def test_backslash_raises(self) -> None:
        with pytest.raises(InvalidMarketplaceError):
            _validate_marketplace_name("path\\traversal")

    def test_null_byte_raises(self) -> None:
        with pytest.raises(InvalidMarketplaceError):
            _validate_marketplace_name("name\x00evil")


# ═══════════════════════════════════════════════════════════════════════════════
# MaterializedMarketplace serialization
# ═══════════════════════════════════════════════════════════════════════════════


class TestMaterializedMarketplaceSerialization:
    """Round-trip to_dict / from_dict."""

    def _make_marketplace(self) -> MaterializedMarketplace:
        return MaterializedMarketplace(
            name="test-mp",
            canonical_name="Test Marketplace",
            relative_path=".claude/.scc-marketplaces/test-mp",
            source_type="github",
            source_url="https://github.com/org/marketplace",
            source_ref="main",
            materialization_mode="full",
            materialized_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            commit_sha="abc123",
            etag=None,
            plugins_available=["plugin-a", "plugin-b"],
        )

    def test_to_dict_keys(self) -> None:
        mp = self._make_marketplace()
        d = mp.to_dict()
        expected_keys = {
            "name",
            "canonical_name",
            "relative_path",
            "source_type",
            "source_url",
            "source_ref",
            "materialization_mode",
            "materialized_at",
            "commit_sha",
            "etag",
            "plugins_available",
        }
        assert set(d.keys()) == expected_keys

    def test_roundtrip(self) -> None:
        mp = self._make_marketplace()
        d = mp.to_dict()
        restored = MaterializedMarketplace.from_dict(d)
        assert restored.name == mp.name
        assert restored.canonical_name == mp.canonical_name
        assert restored.source_type == mp.source_type
        assert restored.plugins_available == mp.plugins_available
        assert restored.commit_sha == mp.commit_sha

    def test_from_dict_backward_compat_no_canonical_name(self) -> None:
        """Old manifests without canonical_name should use name as fallback."""
        d = {
            "name": "old-mp",
            "relative_path": ".claude/.scc-marketplaces/old-mp",
            "source_type": "github",
            "source_url": "https://github.com/org/mp",
            "source_ref": "main",
        }
        mp = MaterializedMarketplace.from_dict(d)
        assert mp.canonical_name == "old-mp"  # fallback to name

    def test_from_dict_missing_mode_defaults_to_full(self) -> None:
        d = {
            "name": "mp",
            "relative_path": ".",
            "source_type": "git",
            "source_url": "https://example.com",
        }
        mp = MaterializedMarketplace.from_dict(d)
        assert mp.materialization_mode == "full"

    def test_from_dict_empty_plugins_default(self) -> None:
        d = {
            "name": "mp",
            "relative_path": ".",
            "source_type": "git",
            "source_url": "https://example.com",
        }
        mp = MaterializedMarketplace.from_dict(d)
        assert mp.plugins_available == []


# ═══════════════════════════════════════════════════════════════════════════════
# Manifest I/O
# ═══════════════════════════════════════════════════════════════════════════════


class TestManifestIO:
    """Manifest save/load round-trip."""

    def _make_marketplace(self, name: str) -> MaterializedMarketplace:
        return MaterializedMarketplace(
            name=name,
            canonical_name=name.title(),
            relative_path=f".claude/.scc-marketplaces/{name}",
            source_type="github",
            source_url=f"https://github.com/org/{name}",
            source_ref="main",
            materialization_mode="full",
            materialized_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
            commit_sha="abc123",
            etag=None,
            plugins_available=["plugin-a"],
        )

    def test_save_and_load(self, tmp_path: Path) -> None:
        marketplaces = {
            "mp1": self._make_marketplace("mp1"),
            "mp2": self._make_marketplace("mp2"),
        }
        save_manifest(tmp_path, marketplaces)
        loaded = load_manifest(tmp_path)
        assert set(loaded.keys()) == {"mp1", "mp2"}
        assert loaded["mp1"].canonical_name == "Mp1"

    def test_load_nonexistent_returns_empty(self, tmp_path: Path) -> None:
        loaded = load_manifest(tmp_path)
        assert loaded == {}

    def test_load_corrupt_json_returns_empty(self, tmp_path: Path) -> None:
        from scc_cli.marketplace.constants import MANIFEST_FILE, MARKETPLACE_CACHE_DIR

        manifest_dir = tmp_path / ".claude" / MARKETPLACE_CACHE_DIR
        manifest_dir.mkdir(parents=True)
        (manifest_dir / MANIFEST_FILE).write_text("{invalid json")
        loaded = load_manifest(tmp_path)
        assert loaded == {}


# ═══════════════════════════════════════════════════════════════════════════════
# is_cache_fresh
# ═══════════════════════════════════════════════════════════════════════════════


class TestIsCacheFresh:
    """Cache freshness checks based on TTL."""

    def test_fresh_cache(self) -> None:
        mp = MaterializedMarketplace(
            name="mp",
            canonical_name="Mp",
            relative_path=".",
            source_type="github",
            source_url="https://example.com",
            source_ref=None,
            materialization_mode="full",
            materialized_at=datetime.now(timezone.utc) - timedelta(seconds=10),
            commit_sha=None,
            etag=None,
        )
        assert is_cache_fresh(mp, ttl_seconds=3600) is True

    def test_stale_cache(self) -> None:
        mp = MaterializedMarketplace(
            name="mp",
            canonical_name="Mp",
            relative_path=".",
            source_type="github",
            source_url="https://example.com",
            source_ref=None,
            materialization_mode="full",
            materialized_at=datetime.now(timezone.utc) - timedelta(hours=2),
            commit_sha=None,
            etag=None,
        )
        assert is_cache_fresh(mp, ttl_seconds=3600) is False


# ═══════════════════════════════════════════════════════════════════════════════
# Result dataclass construction
# ═══════════════════════════════════════════════════════════════════════════════


class TestResultDataclasses:
    """CloneResult, DownloadResult, DiscoveryResult construction."""

    def test_clone_result_success(self) -> None:
        r = CloneResult(success=True, commit_sha="abc123", plugins=["p1"])
        assert r.success is True
        assert r.error is None

    def test_clone_result_failure(self) -> None:
        r = CloneResult(success=False, error="git clone failed")
        assert r.success is False
        assert r.error == "git clone failed"

    def test_download_result_with_etag(self) -> None:
        r = DownloadResult(success=True, etag='W/"abc"', plugins=["p1"])
        assert r.etag == 'W/"abc"'

    def test_discovery_result(self) -> None:
        r = DiscoveryResult(plugins=["p1", "p2"], canonical_name="My Marketplace")
        assert len(r.plugins) == 2
        assert r.canonical_name == "My Marketplace"


# ═══════════════════════════════════════════════════════════════════════════════
# Exception hierarchy
# ═══════════════════════════════════════════════════════════════════════════════


class TestExceptions:
    """Exception classes carry metadata."""

    def test_materialization_error_base(self) -> None:
        err = MaterializationError("something broke", marketplace_name="mp1")
        assert err.marketplace_name == "mp1"
        assert "something broke" in str(err)

    def test_invalid_marketplace_error(self) -> None:
        err = InvalidMarketplaceError("mp1", "missing marketplace.json")
        assert err.marketplace_name == "mp1"
        assert "marketplace.json" in str(err)
