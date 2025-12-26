"""Tests for team config caching module (Phase 2: Federation).

Covers:
- TeamCacheMeta dataclass serialization/deserialization
- Team config fetching from various sources
- Cache file management and TTL handling
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# TeamCacheMeta Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestTeamCacheMeta:
    """Tests for TeamCacheMeta dataclass."""

    def test_has_required_fields(self) -> None:
        """TeamCacheMeta has all required fields."""
        from scc_cli.marketplace.team_cache import TeamCacheMeta

        meta = TeamCacheMeta(
            team_name="backend",
            source_type="github",
            source_url="github.com/sundsvall/backend-config",
            fetched_at=datetime.now(timezone.utc),
        )
        assert meta.team_name == "backend"
        assert meta.source_type == "github"
        assert meta.source_url == "github.com/sundsvall/backend-config"
        assert meta.fetched_at is not None

    def test_optional_commit_sha_for_git_sources(self) -> None:
        """Git sources can include commit SHA for version tracking."""
        from scc_cli.marketplace.team_cache import TeamCacheMeta

        meta = TeamCacheMeta(
            team_name="backend",
            source_type="github",
            source_url="github.com/sundsvall/backend-config",
            fetched_at=datetime.now(timezone.utc),
            commit_sha="abc123def456",
        )
        assert meta.commit_sha == "abc123def456"

    def test_optional_etag_for_url_sources(self) -> None:
        """URL sources can include ETag for cache validation."""
        from scc_cli.marketplace.team_cache import TeamCacheMeta

        meta = TeamCacheMeta(
            team_name="backend",
            source_type="url",
            source_url="https://config.sundsvall.se/backend.json",
            fetched_at=datetime.now(timezone.utc),
            etag='"abcdef123456"',
        )
        assert meta.etag == '"abcdef123456"'

    def test_optional_branch_for_git_sources(self) -> None:
        """Git sources can include branch name."""
        from scc_cli.marketplace.team_cache import TeamCacheMeta

        meta = TeamCacheMeta(
            team_name="backend",
            source_type="git",
            source_url="https://gitlab.sundsvall.se/team/config.git",
            fetched_at=datetime.now(timezone.utc),
            branch="develop",
        )
        assert meta.branch == "develop"

    def test_defaults_for_optional_fields(self) -> None:
        """Optional fields default to None."""
        from scc_cli.marketplace.team_cache import TeamCacheMeta

        meta = TeamCacheMeta(
            team_name="backend",
            source_type="url",
            source_url="https://example.com/config.json",
            fetched_at=datetime.now(timezone.utc),
        )
        assert meta.commit_sha is None
        assert meta.etag is None
        assert meta.branch is None

    def test_to_dict_serialization(self) -> None:
        """TeamCacheMeta can be serialized to dict for JSON storage."""
        from scc_cli.marketplace.team_cache import TeamCacheMeta

        now = datetime.now(timezone.utc)
        meta = TeamCacheMeta(
            team_name="backend",
            source_type="github",
            source_url="github.com/sundsvall/backend-config",
            fetched_at=now,
            commit_sha="abc123",
            branch="main",
        )
        data = meta.to_dict()

        assert data["team_name"] == "backend"
        assert data["source_type"] == "github"
        assert data["source_url"] == "github.com/sundsvall/backend-config"
        assert data["fetched_at"] == now.isoformat()
        assert data["commit_sha"] == "abc123"
        assert data["branch"] == "main"

    def test_from_dict_deserialization(self) -> None:
        """TeamCacheMeta can be deserialized from dict."""
        from scc_cli.marketplace.team_cache import TeamCacheMeta

        now = datetime.now(timezone.utc)
        data = {
            "team_name": "frontend",
            "source_type": "url",
            "source_url": "https://config.example.com/frontend.json",
            "fetched_at": now.isoformat(),
            "etag": '"xyz789"',
        }
        meta = TeamCacheMeta.from_dict(data)

        assert meta.team_name == "frontend"
        assert meta.source_type == "url"
        assert meta.source_url == "https://config.example.com/frontend.json"
        assert meta.fetched_at == now
        assert meta.etag == '"xyz789"'
        assert meta.commit_sha is None

    def test_from_dict_handles_missing_optional_fields(self) -> None:
        """Deserialization handles missing optional fields gracefully."""
        from scc_cli.marketplace.team_cache import TeamCacheMeta

        data = {
            "team_name": "backend",
            "source_type": "github",
            "source_url": "github.com/org/repo",
            "fetched_at": "2025-12-25T10:00:00+00:00",
        }
        meta = TeamCacheMeta.from_dict(data)

        assert meta.commit_sha is None
        assert meta.etag is None
        assert meta.branch is None

    def test_roundtrip_serialization(self) -> None:
        """to_dict and from_dict preserve all data."""
        from scc_cli.marketplace.team_cache import TeamCacheMeta

        original = TeamCacheMeta(
            team_name="infra",
            source_type="git",
            source_url="git@gitlab.sundsvall.se:infra/config.git",
            fetched_at=datetime(2025, 12, 25, 10, 0, 0, tzinfo=timezone.utc),
            commit_sha="deadbeef",
            branch="production",
        )
        data = original.to_dict()
        restored = TeamCacheMeta.from_dict(data)

        assert restored.team_name == original.team_name
        assert restored.source_type == original.source_type
        assert restored.source_url == original.source_url
        assert restored.fetched_at == original.fetched_at
        assert restored.commit_sha == original.commit_sha
        assert restored.branch == original.branch


class TestTeamCacheMetaAge:
    """Tests for cache age and staleness calculations."""

    def test_age_property(self) -> None:
        """age returns timedelta since fetched_at."""
        from scc_cli.marketplace.team_cache import TeamCacheMeta

        fetched = datetime.now(timezone.utc) - timedelta(hours=2)
        meta = TeamCacheMeta(
            team_name="backend",
            source_type="url",
            source_url="https://example.com/config.json",
            fetched_at=fetched,
        )
        age = meta.age
        # Allow 1 second tolerance for test execution time
        assert timedelta(hours=1, minutes=59) < age < timedelta(hours=2, seconds=5)

    def test_is_fresh_within_ttl(self) -> None:
        """is_fresh returns True when age < ttl."""
        from scc_cli.marketplace.team_cache import DEFAULT_TTL, TeamCacheMeta

        fetched = datetime.now(timezone.utc) - timedelta(hours=1)
        meta = TeamCacheMeta(
            team_name="backend",
            source_type="url",
            source_url="https://example.com/config.json",
            fetched_at=fetched,
        )
        # Default TTL is 24 hours, so 1 hour old cache is fresh
        assert meta.is_fresh(DEFAULT_TTL) is True

    def test_is_fresh_expired(self) -> None:
        """is_fresh returns False when age >= ttl."""
        from scc_cli.marketplace.team_cache import DEFAULT_TTL, TeamCacheMeta

        fetched = datetime.now(timezone.utc) - timedelta(hours=25)
        meta = TeamCacheMeta(
            team_name="backend",
            source_type="url",
            source_url="https://example.com/config.json",
            fetched_at=fetched,
        )
        # Default TTL is 24 hours, so 25 hour old cache is stale
        assert meta.is_fresh(DEFAULT_TTL) is False

    def test_is_within_max_stale_age(self) -> None:
        """is_within_max_stale_age for fallback decisions."""
        from scc_cli.marketplace.team_cache import MAX_STALE_AGE, TeamCacheMeta

        # 5 days old - within MAX_STALE_AGE (7 days)
        fetched = datetime.now(timezone.utc) - timedelta(days=5)
        meta = TeamCacheMeta(
            team_name="backend",
            source_type="url",
            source_url="https://example.com/config.json",
            fetched_at=fetched,
        )
        assert meta.is_within_max_stale_age(MAX_STALE_AGE) is True

    def test_is_beyond_max_stale_age(self) -> None:
        """Caches beyond MAX_STALE_AGE should not be used as fallback."""
        from scc_cli.marketplace.team_cache import MAX_STALE_AGE, TeamCacheMeta

        # 10 days old - beyond MAX_STALE_AGE (7 days)
        fetched = datetime.now(timezone.utc) - timedelta(days=10)
        meta = TeamCacheMeta(
            team_name="backend",
            source_type="url",
            source_url="https://example.com/config.json",
            fetched_at=fetched,
        )
        assert meta.is_within_max_stale_age(MAX_STALE_AGE) is False


class TestCacheConstants:
    """Tests for cache configuration constants."""

    def test_default_ttl_is_24_hours(self) -> None:
        """DEFAULT_TTL should be 24 hours as per spec."""
        from scc_cli.marketplace.team_cache import DEFAULT_TTL

        assert DEFAULT_TTL == timedelta(hours=24)

    def test_max_stale_age_is_7_days(self) -> None:
        """MAX_STALE_AGE should be 7 days as per spec."""
        from scc_cli.marketplace.team_cache import MAX_STALE_AGE

        assert MAX_STALE_AGE == timedelta(days=7)


# ─────────────────────────────────────────────────────────────────────────────
# Cache Path Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestCachePaths:
    """Tests for cache path management."""

    def test_get_team_cache_dir(self, tmp_path: pytest.TempPathFactory) -> None:
        """get_team_cache_dir returns correct path under cache root."""
        from scc_cli.marketplace.team_cache import get_team_cache_dir

        cache_dir = get_team_cache_dir(cache_root=tmp_path)
        assert cache_dir == tmp_path / "team_configs"

    def test_get_team_config_cache_path(self, tmp_path: pytest.TempPathFactory) -> None:
        """get_team_config_cache_path returns path for specific team."""
        from scc_cli.marketplace.team_cache import get_team_config_cache_path

        path = get_team_config_cache_path("backend", cache_root=tmp_path)
        assert path == tmp_path / "team_configs" / "backend.json"

    def test_get_team_meta_cache_path(self, tmp_path: pytest.TempPathFactory) -> None:
        """get_team_meta_cache_path returns path for team metadata."""
        from scc_cli.marketplace.team_cache import get_team_meta_cache_path

        path = get_team_meta_cache_path("backend", cache_root=tmp_path)
        assert path == tmp_path / "team_configs" / "backend.meta.json"
