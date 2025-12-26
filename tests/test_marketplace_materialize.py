"""
Tests for marketplace materialization.

TDD: Tests written before implementation.
Tests cover: GitHub, Git, Directory, URL materialization handlers,
manifest management, cache reuse, and path validation.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Create a project directory with .claude/ subdirectory."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    return tmp_path


@pytest.fixture
def marketplace_cache_dir(project_dir: Path) -> Path:
    """Create the .scc-marketplaces cache directory."""
    cache_dir = project_dir / ".claude" / ".scc-marketplaces"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def valid_marketplace_json() -> dict:
    """Valid marketplace.json content that passes validation."""
    return {
        "name": "test-marketplace",
        "description": "Test marketplace for unit tests",
        "plugins": [
            {"name": "code-review", "version": "1.0.0"},
            {"name": "linter", "version": "2.0.0"},
        ],
    }


@pytest.fixture
def github_source() -> dict:
    """GitHub marketplace source configuration."""
    return {
        "source": "github",
        "owner": "sundsvall",
        "repo": "claude-plugins",
        "branch": "main",
        "path": "/",
    }


@pytest.fixture
def git_source() -> dict:
    """Generic git marketplace source configuration."""
    return {
        "source": "git",
        "url": "https://gitlab.example.se/ai/plugins.git",
        "branch": "main",
        "path": "/",
    }


@pytest.fixture
def directory_source(tmp_path: Path, valid_marketplace_json: dict) -> dict:
    """Local directory marketplace source with valid structure."""
    local_marketplace = tmp_path / "local-marketplace"
    plugin_dir = local_marketplace / ".claude-plugin"
    plugin_dir.mkdir(parents=True)

    # Create valid marketplace.json
    manifest_path = plugin_dir / "marketplace.json"
    manifest_path.write_text(json.dumps(valid_marketplace_json))

    return {
        "source": "directory",
        "path": str(local_marketplace),
    }


@pytest.fixture
def url_source() -> dict:
    """URL marketplace source configuration."""
    return {
        "source": "url",
        "url": "https://plugins.sundsvall.se/marketplace.tar.gz",
        "materialization_mode": "self_contained",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MaterializedMarketplace Dataclass Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestMaterializedMarketplace:
    """Test the MaterializedMarketplace dataclass."""

    def test_create_with_all_fields(self) -> None:
        """Should create dataclass with all required fields."""
        from scc_cli.marketplace.materialize import MaterializedMarketplace

        now = datetime.now(timezone.utc)
        marketplace = MaterializedMarketplace(
            name="internal",
            relative_path=".claude/.scc-marketplaces/internal",
            source_type="github",
            source_url="https://github.com/sundsvall/claude-plugins",
            source_ref="main",
            materialization_mode="full",
            materialized_at=now,
            commit_sha="abc123def456",
            etag=None,
            plugins_available=["code-review", "linter"],
        )

        assert marketplace.name == "internal"
        assert marketplace.relative_path == ".claude/.scc-marketplaces/internal"
        assert marketplace.source_type == "github"
        assert marketplace.commit_sha == "abc123def456"
        assert "code-review" in marketplace.plugins_available

    def test_relative_path_required(self) -> None:
        """Should require relative path (not absolute)."""
        from scc_cli.marketplace.materialize import MaterializedMarketplace

        # Valid relative path should work
        marketplace = MaterializedMarketplace(
            name="test",
            relative_path=".claude/.scc-marketplaces/test",
            source_type="directory",
            source_url="/local/path",
            source_ref=None,
            materialization_mode="full",
            materialized_at=datetime.now(timezone.utc),
            commit_sha=None,
            etag=None,
            plugins_available=[],
        )
        assert marketplace.relative_path.startswith(".")

    def test_to_dict_serialization(self) -> None:
        """Should serialize to dict for JSON storage."""
        from scc_cli.marketplace.materialize import MaterializedMarketplace

        now = datetime.now(timezone.utc)
        marketplace = MaterializedMarketplace(
            name="internal",
            relative_path=".claude/.scc-marketplaces/internal",
            source_type="github",
            source_url="https://github.com/sundsvall/claude-plugins",
            source_ref="main",
            materialization_mode="full",
            materialized_at=now,
            commit_sha="abc123",
            etag=None,
            plugins_available=["tool"],
        )

        data = marketplace.to_dict()
        assert data["name"] == "internal"
        assert data["source_type"] == "github"
        assert "materialized_at" in data

    def test_from_dict_deserialization(self) -> None:
        """Should deserialize from dict loaded from JSON."""
        from scc_cli.marketplace.materialize import MaterializedMarketplace

        data = {
            "name": "internal",
            "relative_path": ".claude/.scc-marketplaces/internal",
            "source_type": "github",
            "source_url": "https://github.com/sundsvall/claude-plugins",
            "source_ref": "main",
            "materialization_mode": "full",
            "materialized_at": "2025-01-01T00:00:00+00:00",
            "commit_sha": "abc123",
            "etag": None,
            "plugins_available": ["tool"],
        }

        marketplace = MaterializedMarketplace.from_dict(data)
        assert marketplace.name == "internal"
        assert marketplace.commit_sha == "abc123"


# ═══════════════════════════════════════════════════════════════════════════════
# Manifest Management Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestManifestManagement:
    """Test manifest loading and saving."""

    def test_load_manifest_empty_when_missing(self, project_dir: Path) -> None:
        """Should return empty dict when manifest doesn't exist."""
        from scc_cli.marketplace.materialize import load_manifest

        manifest = load_manifest(project_dir)
        assert manifest == {}

    def test_load_manifest_parses_json(
        self, marketplace_cache_dir: Path, project_dir: Path
    ) -> None:
        """Should parse existing manifest.json."""
        from scc_cli.marketplace.materialize import load_manifest

        # Create manifest file
        manifest_data = {
            "internal": {
                "name": "internal",
                "relative_path": ".claude/.scc-marketplaces/internal",
                "source_type": "github",
                "source_url": "https://github.com/sundsvall/claude-plugins",
                "source_ref": "main",
                "materialization_mode": "full",
                "materialized_at": "2025-01-01T00:00:00+00:00",
                "commit_sha": "abc123",
                "etag": None,
                "plugins_available": ["tool"],
            }
        }
        manifest_path = marketplace_cache_dir / ".manifest.json"
        manifest_path.write_text(json.dumps(manifest_data))

        manifest = load_manifest(project_dir)
        assert "internal" in manifest
        assert manifest["internal"].name == "internal"

    def test_save_manifest_creates_file(
        self, marketplace_cache_dir: Path, project_dir: Path
    ) -> None:
        """Should create manifest.json with serialized data."""
        from scc_cli.marketplace.materialize import (
            MaterializedMarketplace,
            save_manifest,
        )

        marketplace = MaterializedMarketplace(
            name="internal",
            relative_path=".claude/.scc-marketplaces/internal",
            source_type="github",
            source_url="https://github.com/sundsvall/claude-plugins",
            source_ref="main",
            materialization_mode="full",
            materialized_at=datetime.now(timezone.utc),
            commit_sha="abc123",
            etag=None,
            plugins_available=["tool"],
        )

        save_manifest(project_dir, {"internal": marketplace})

        manifest_path = marketplace_cache_dir / ".manifest.json"
        assert manifest_path.exists()

        loaded = json.loads(manifest_path.read_text())
        assert "internal" in loaded
        assert loaded["internal"]["source_type"] == "github"

    def test_save_manifest_overwrites_existing(
        self, marketplace_cache_dir: Path, project_dir: Path
    ) -> None:
        """Should overwrite existing manifest.json."""
        from scc_cli.marketplace.materialize import (
            MaterializedMarketplace,
            save_manifest,
        )

        # Create initial manifest
        manifest_path = marketplace_cache_dir / ".manifest.json"
        manifest_path.write_text('{"old": {}}')

        # Save new manifest
        marketplace = MaterializedMarketplace(
            name="new",
            relative_path=".claude/.scc-marketplaces/new",
            source_type="directory",
            source_url="/local",
            source_ref=None,
            materialization_mode="full",
            materialized_at=datetime.now(timezone.utc),
            commit_sha=None,
            etag=None,
            plugins_available=[],
        )
        save_manifest(project_dir, {"new": marketplace})

        loaded = json.loads(manifest_path.read_text())
        assert "new" in loaded
        assert "old" not in loaded


# ═══════════════════════════════════════════════════════════════════════════════
# GitHub Materialization Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestMaterializeGitHub:
    """Test GitHub marketplace materialization."""

    def test_clones_repository_shallow(self, project_dir: Path, github_source: dict) -> None:
        """Should clone repository with depth=1 for efficiency."""
        from scc_cli.marketplace.materialize import materialize_github

        with patch("scc_cli.marketplace.materialize.run_git_clone") as mock_clone:
            mock_clone.return_value = MagicMock(success=True, commit_sha="abc123", plugins=["tool"])

            materialize_github(
                name="internal",
                source=github_source,
                project_dir=project_dir,
            )

            mock_clone.assert_called_once()
            call_args = mock_clone.call_args
            assert "--depth" in str(call_args) or call_args[1].get("depth") == 1

    def test_creates_relative_path(self, project_dir: Path, github_source: dict) -> None:
        """Should create marketplace under .claude/.scc-marketplaces/."""
        from scc_cli.marketplace.materialize import materialize_github

        with patch("scc_cli.marketplace.materialize.run_git_clone") as mock_clone:
            mock_clone.return_value = MagicMock(success=True, commit_sha="abc123", plugins=["tool"])

            result = materialize_github(
                name="internal",
                source=github_source,
                project_dir=project_dir,
            )

            assert result.relative_path == ".claude/.scc-marketplaces/internal"

    def test_returns_materialized_marketplace(self, project_dir: Path, github_source: dict) -> None:
        """Should return MaterializedMarketplace with correct fields."""
        from scc_cli.marketplace.materialize import materialize_github

        with patch("scc_cli.marketplace.materialize.run_git_clone") as mock_clone:
            mock_clone.return_value = MagicMock(
                success=True, commit_sha="abc123", plugins=["code-review", "linter"]
            )

            result = materialize_github(
                name="internal",
                source=github_source,
                project_dir=project_dir,
            )

            assert result.name == "internal"
            assert result.source_type == "github"
            assert result.commit_sha == "abc123"
            assert "code-review" in result.plugins_available

    def test_handles_auth_headers(self, project_dir: Path, github_source: dict) -> None:
        """Should pass authentication headers for private repos."""
        from scc_cli.marketplace.materialize import materialize_github

        github_source["headers"] = {"Authorization": "token ${GITHUB_TOKEN}"}

        with patch("scc_cli.marketplace.materialize.run_git_clone") as mock_clone:
            mock_clone.return_value = MagicMock(success=True, commit_sha="abc123", plugins=[])

            materialize_github(
                name="internal",
                source=github_source,
                project_dir=project_dir,
            )

            # Verify headers were considered (actual implementation will expand ${VAR})
            mock_clone.assert_called_once()

    def test_raises_on_clone_failure(self, project_dir: Path, github_source: dict) -> None:
        """Should raise MaterializationError on clone failure."""
        from scc_cli.marketplace.materialize import (
            MaterializationError,
            materialize_github,
        )

        with patch("scc_cli.marketplace.materialize.run_git_clone") as mock_clone:
            mock_clone.return_value = MagicMock(success=False, error="Repository not found")

            with pytest.raises(MaterializationError) as exc_info:
                materialize_github(
                    name="internal",
                    source=github_source,
                    project_dir=project_dir,
                )

            assert "Repository not found" in str(exc_info.value)


# ═══════════════════════════════════════════════════════════════════════════════
# Git Materialization Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestMaterializeGit:
    """Test generic git marketplace materialization."""

    def test_clones_generic_git_url(self, project_dir: Path, git_source: dict) -> None:
        """Should clone from generic git URL (GitLab, self-hosted, etc)."""
        from scc_cli.marketplace.materialize import materialize_git

        with patch("scc_cli.marketplace.materialize.run_git_clone") as mock_clone:
            mock_clone.return_value = MagicMock(
                success=True, commit_sha="def456", plugins=["api-tool"]
            )

            result = materialize_git(
                name="gitlab-plugins",
                source=git_source,
                project_dir=project_dir,
            )

            assert result.source_type == "git"
            assert result.source_url == git_source["url"]

    def test_supports_ssh_url(self, project_dir: Path) -> None:
        """Should support SSH git URLs."""
        from scc_cli.marketplace.materialize import materialize_git

        ssh_source = {
            "source": "git",
            "url": "git@gitlab.example.se:ai/plugins.git",
            "branch": "main",
            "path": "/",
        }

        with patch("scc_cli.marketplace.materialize.run_git_clone") as mock_clone:
            mock_clone.return_value = MagicMock(success=True, commit_sha="ssh123", plugins=[])

            result = materialize_git(
                name="ssh-plugins",
                source=ssh_source,
                project_dir=project_dir,
            )

            assert result.source_url == "git@gitlab.example.se:ai/plugins.git"


# ═══════════════════════════════════════════════════════════════════════════════
# Directory Materialization Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestMaterializeDirectory:
    """Test local directory marketplace materialization."""

    def test_creates_symlink_to_local_dir(self, project_dir: Path, directory_source: dict) -> None:
        """Should create symlink to local directory."""
        from scc_cli.marketplace.materialize import materialize_directory

        materialize_directory(
            name="local",
            source=directory_source,
            project_dir=project_dir,
        )

        # Check symlink was created
        marketplace_dir = project_dir / ".claude" / ".scc-marketplaces" / "local"
        assert marketplace_dir.exists() or marketplace_dir.is_symlink()

    def test_validates_marketplace_json_exists(self, project_dir: Path, tmp_path: Path) -> None:
        """Should fail if .claude-plugin/marketplace.json is missing."""
        from scc_cli.marketplace.materialize import (
            InvalidMarketplaceError,
            materialize_directory,
        )

        # Create directory without marketplace.json
        empty_dir = tmp_path / "empty-marketplace"
        empty_dir.mkdir()

        source = {
            "source": "directory",
            "path": str(empty_dir),
        }

        with pytest.raises(InvalidMarketplaceError) as exc_info:
            materialize_directory(
                name="invalid",
                source=source,
                project_dir=project_dir,
            )

        assert "marketplace.json" in str(exc_info.value)

    def test_returns_relative_path(self, project_dir: Path, directory_source: dict) -> None:
        """Should return relative path for Docker compatibility."""
        from scc_cli.marketplace.materialize import materialize_directory

        result = materialize_directory(
            name="local",
            source=directory_source,
            project_dir=project_dir,
        )

        # Path must be relative (not start with /)
        assert not result.relative_path.startswith("/")
        assert result.relative_path.startswith(".")

    def test_discovers_available_plugins(self, project_dir: Path, directory_source: dict) -> None:
        """Should discover plugins from marketplace.json."""
        from scc_cli.marketplace.materialize import materialize_directory

        result = materialize_directory(
            name="local",
            source=directory_source,
            project_dir=project_dir,
        )

        assert "code-review" in result.plugins_available
        assert "linter" in result.plugins_available


# ═══════════════════════════════════════════════════════════════════════════════
# URL Materialization Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestMaterializeUrl:
    """Test URL marketplace materialization."""

    def test_downloads_and_extracts_archive(self, project_dir: Path, url_source: dict) -> None:
        """Should download and extract marketplace archive."""
        from scc_cli.marketplace.materialize import materialize_url

        with patch("scc_cli.marketplace.materialize.download_and_extract") as mock_dl:
            mock_dl.return_value = MagicMock(success=True, etag='"abc123"', plugins=["web-tool"])

            result = materialize_url(
                name="remote",
                source=url_source,
                project_dir=project_dir,
            )

            assert result.source_type == "url"
            assert result.etag == '"abc123"'

    def test_respects_materialization_mode(self, project_dir: Path, url_source: dict) -> None:
        """Should handle different materialization modes."""
        from scc_cli.marketplace.materialize import materialize_url

        url_source["materialization_mode"] = "metadata_only"

        with patch("scc_cli.marketplace.materialize.download_and_extract") as mock_dl:
            mock_dl.return_value = MagicMock(success=True, etag=None, plugins=["meta-tool"])

            result = materialize_url(
                name="metadata",
                source=url_source,
                project_dir=project_dir,
            )

            assert result.materialization_mode == "metadata_only"

    def test_requires_https(self, project_dir: Path) -> None:
        """Should reject HTTP URLs (security requirement)."""
        from scc_cli.marketplace.materialize import (
            MaterializationError,
            materialize_url,
        )

        http_source = {
            "source": "url",
            "url": "http://insecure.example.com/marketplace.tar.gz",  # HTTP!
            "materialization_mode": "self_contained",
        }

        with pytest.raises(MaterializationError) as exc_info:
            materialize_url(
                name="insecure",
                source=http_source,
                project_dir=project_dir,
            )

        assert "HTTPS" in str(exc_info.value) or "http" in str(exc_info.value).lower()


# ═══════════════════════════════════════════════════════════════════════════════
# Dispatcher Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestMaterializeMarketplace:
    """Test the materialize_marketplace() dispatcher."""

    def test_dispatches_to_github_handler(self, project_dir: Path, github_source: dict) -> None:
        """Should route GitHub sources to materialize_github()."""
        from scc_cli.marketplace.materialize import (
            MaterializedMarketplace,
            materialize_marketplace,
        )
        from scc_cli.marketplace.schema import MarketplaceSourceGitHub

        source = MarketplaceSourceGitHub.model_validate(github_source)

        mock_result = MaterializedMarketplace(
            name="internal",
            relative_path=".claude/.scc-marketplaces/internal",
            source_type="github",
            source_url="https://github.com/sundsvall/claude-plugins",
            source_ref="main",
            materialization_mode="metadata_only",
            materialized_at=datetime.now(UTC),
            commit_sha="abc123",
            etag=None,
            plugins_available=["test-plugin"],
        )

        with (
            patch("scc_cli.marketplace.materialize.materialize_github") as mock_github,
            patch("scc_cli.marketplace.materialize.load_manifest", return_value={}),
            patch("scc_cli.marketplace.materialize.save_manifest"),
        ):
            mock_github.return_value = mock_result

            materialize_marketplace(
                name="internal",
                source=source,
                project_dir=project_dir,
            )

            mock_github.assert_called_once()

    def test_dispatches_to_git_handler(self, project_dir: Path, git_source: dict) -> None:
        """Should route git sources to materialize_git()."""
        from scc_cli.marketplace.materialize import (
            MaterializedMarketplace,
            materialize_marketplace,
        )
        from scc_cli.marketplace.schema import MarketplaceSourceGit

        source = MarketplaceSourceGit.model_validate(git_source)

        mock_result = MaterializedMarketplace(
            name="gitlab",
            relative_path=".claude/.scc-marketplaces/gitlab",
            source_type="git",
            source_url="https://gitlab.example.se/ai/plugins.git",
            source_ref="main",
            materialization_mode="metadata_only",
            materialized_at=datetime.now(UTC),
            commit_sha="abc123",
            etag=None,
            plugins_available=["test-plugin"],
        )

        with (
            patch("scc_cli.marketplace.materialize.materialize_git") as mock_git,
            patch("scc_cli.marketplace.materialize.load_manifest", return_value={}),
            patch("scc_cli.marketplace.materialize.save_manifest"),
        ):
            mock_git.return_value = mock_result

            materialize_marketplace(
                name="gitlab",
                source=source,
                project_dir=project_dir,
            )

            mock_git.assert_called_once()

    def test_dispatches_to_directory_handler(
        self, project_dir: Path, directory_source: dict
    ) -> None:
        """Should route directory sources to materialize_directory()."""
        from scc_cli.marketplace.materialize import (
            MaterializedMarketplace,
            materialize_marketplace,
        )
        from scc_cli.marketplace.schema import MarketplaceSourceDirectory

        source = MarketplaceSourceDirectory.model_validate(directory_source)

        mock_result = MaterializedMarketplace(
            name="local",
            relative_path=".claude/.scc-marketplaces/local",
            source_type="directory",
            source_url="/path/to/local/plugins",
            source_ref=None,
            materialization_mode="metadata_only",
            materialized_at=datetime.now(UTC),
            commit_sha=None,
            etag=None,
            plugins_available=["test-plugin"],
        )

        with (
            patch("scc_cli.marketplace.materialize.materialize_directory") as mock_dir,
            patch("scc_cli.marketplace.materialize.load_manifest", return_value={}),
            patch("scc_cli.marketplace.materialize.save_manifest"),
        ):
            mock_dir.return_value = mock_result

            materialize_marketplace(
                name="local",
                source=source,
                project_dir=project_dir,
            )

            mock_dir.assert_called_once()

    def test_dispatches_to_url_handler(self, project_dir: Path, url_source: dict) -> None:
        """Should route URL sources to materialize_url()."""
        from scc_cli.marketplace.materialize import (
            MaterializedMarketplace,
            materialize_marketplace,
        )
        from scc_cli.marketplace.schema import MarketplaceSourceURL

        source = MarketplaceSourceURL.model_validate(url_source)

        mock_result = MaterializedMarketplace(
            name="remote",
            relative_path=".claude/.scc-marketplaces/remote",
            source_type="url",
            source_url="https://plugins.example.se/marketplace.tar.gz",
            source_ref=None,
            materialization_mode="self_contained",
            materialized_at=datetime.now(UTC),
            commit_sha=None,
            etag="abc123",
            plugins_available=["test-plugin"],
        )

        with (
            patch("scc_cli.marketplace.materialize.materialize_url") as mock_url,
            patch("scc_cli.marketplace.materialize.load_manifest", return_value={}),
            patch("scc_cli.marketplace.materialize.save_manifest"),
        ):
            mock_url.return_value = mock_result

            materialize_marketplace(
                name="remote",
                source=source,
                project_dir=project_dir,
            )

            mock_url.assert_called_once()


# ═══════════════════════════════════════════════════════════════════════════════
# Cache Reuse Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestCacheReuse:
    """Test materialization cache reuse logic."""

    def test_skips_clone_when_cached_and_fresh(
        self, project_dir: Path, github_source: dict
    ) -> None:
        """Should skip git clone when marketplace already materialized and fresh."""
        from scc_cli.marketplace.materialize import (
            MaterializedMarketplace,
            materialize_marketplace,
            save_manifest,
        )
        from scc_cli.marketplace.schema import MarketplaceSourceGitHub

        # Pre-populate cache
        existing = MaterializedMarketplace(
            name="internal",
            relative_path=".claude/.scc-marketplaces/internal",
            source_type="github",
            source_url="https://github.com/sundsvall/claude-plugins",
            source_ref="main",
            materialization_mode="full",
            materialized_at=datetime.now(timezone.utc),
            commit_sha="current123",
            etag=None,
            plugins_available=["tool"],
        )

        # Create cache directory
        cache_dir = project_dir / ".claude" / ".scc-marketplaces"
        cache_dir.mkdir(parents=True)
        (cache_dir / "internal").mkdir()
        save_manifest(project_dir, {"internal": existing})

        source = MarketplaceSourceGitHub.model_validate(github_source)

        with (
            patch("scc_cli.marketplace.materialize.run_git_clone") as mock_clone,
            patch("scc_cli.marketplace.materialize.is_cache_fresh", return_value=True),
        ):
            result = materialize_marketplace(
                name="internal",
                source=source,
                project_dir=project_dir,
            )

            # Clone should NOT be called when cache is fresh
            mock_clone.assert_not_called()
            assert result.name == "internal"

    def test_reclones_when_cache_stale(self, project_dir: Path, github_source: dict) -> None:
        """Should re-clone when cached marketplace is stale."""
        from scc_cli.marketplace.materialize import (
            MaterializedMarketplace,
            materialize_marketplace,
            save_manifest,
        )
        from scc_cli.marketplace.schema import MarketplaceSourceGitHub

        # Pre-populate stale cache
        existing = MaterializedMarketplace(
            name="internal",
            relative_path=".claude/.scc-marketplaces/internal",
            source_type="github",
            source_url="https://github.com/sundsvall/claude-plugins",
            source_ref="main",
            materialization_mode="full",
            materialized_at=datetime(2020, 1, 1, tzinfo=timezone.utc),  # Old
            commit_sha="old123",
            etag=None,
            plugins_available=["old-tool"],
        )

        cache_dir = project_dir / ".claude" / ".scc-marketplaces"
        cache_dir.mkdir(parents=True)
        (cache_dir / "internal").mkdir()
        save_manifest(project_dir, {"internal": existing})

        source = MarketplaceSourceGitHub.model_validate(github_source)

        with (
            patch("scc_cli.marketplace.materialize.run_git_clone") as mock_clone,
            patch("scc_cli.marketplace.materialize.is_cache_fresh", return_value=False),
        ):
            mock_clone.return_value = MagicMock(
                success=True, commit_sha="new456", plugins=["new-tool"]
            )

            result = materialize_marketplace(
                name="internal",
                source=source,
                project_dir=project_dir,
            )

            # Should re-clone when stale
            mock_clone.assert_called_once()
            assert result.commit_sha == "new456"

    def test_force_refresh_ignores_cache(self, project_dir: Path, github_source: dict) -> None:
        """Should ignore cache when force_refresh=True."""
        from scc_cli.marketplace.materialize import (
            MaterializedMarketplace,
            materialize_marketplace,
            save_manifest,
        )
        from scc_cli.marketplace.schema import MarketplaceSourceGitHub

        # Pre-populate fresh cache
        existing = MaterializedMarketplace(
            name="internal",
            relative_path=".claude/.scc-marketplaces/internal",
            source_type="github",
            source_url="https://github.com/sundsvall/claude-plugins",
            source_ref="main",
            materialization_mode="full",
            materialized_at=datetime.now(timezone.utc),
            commit_sha="current123",
            etag=None,
            plugins_available=["tool"],
        )

        cache_dir = project_dir / ".claude" / ".scc-marketplaces"
        cache_dir.mkdir(parents=True)
        (cache_dir / "internal").mkdir()
        save_manifest(project_dir, {"internal": existing})

        source = MarketplaceSourceGitHub.model_validate(github_source)

        with patch("scc_cli.marketplace.materialize.run_git_clone") as mock_clone:
            mock_clone.return_value = MagicMock(
                success=True, commit_sha="forced789", plugins=["tool"]
            )

            result = materialize_marketplace(
                name="internal",
                source=source,
                project_dir=project_dir,
                force_refresh=True,
            )

            # Should clone even when fresh because force_refresh=True
            mock_clone.assert_called_once()
            assert result.commit_sha == "forced789"


# ═══════════════════════════════════════════════════════════════════════════════
# Path Validation Tests (Docker Sandbox - RQ-11)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPathValidation:
    """Test path validation for Docker sandbox compatibility."""

    def test_all_paths_are_relative(self, project_dir: Path, github_source: dict) -> None:
        """All returned paths should be relative (not absolute)."""
        from scc_cli.marketplace.materialize import materialize_github

        with patch("scc_cli.marketplace.materialize.run_git_clone") as mock_clone:
            mock_clone.return_value = MagicMock(success=True, commit_sha="abc123", plugins=[])

            result = materialize_github(
                name="internal",
                source=github_source,
                project_dir=project_dir,
            )

            # Validate relative path
            assert not result.relative_path.startswith("/")
            assert result.relative_path.startswith(".")

    def test_manifest_stores_relative_paths(
        self, marketplace_cache_dir: Path, project_dir: Path
    ) -> None:
        """Manifest should only store relative paths."""
        from scc_cli.marketplace.materialize import (
            MaterializedMarketplace,
            load_manifest,
            save_manifest,
        )

        marketplace = MaterializedMarketplace(
            name="test",
            relative_path=".claude/.scc-marketplaces/test",
            source_type="directory",
            source_url="/absolute/path/to/source",  # Source URL can be absolute
            source_ref=None,
            materialization_mode="full",
            materialized_at=datetime.now(timezone.utc),
            commit_sha=None,
            etag=None,
            plugins_available=[],
        )

        save_manifest(project_dir, {"test": marketplace})
        loaded = load_manifest(project_dir)

        # relative_path in manifest must be relative
        assert not loaded["test"].relative_path.startswith("/")


# ═══════════════════════════════════════════════════════════════════════════════
# Error Handling Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestMaterializationErrors:
    """Test error handling in materialization."""

    def test_git_not_installed_error(self, project_dir: Path, github_source: dict) -> None:
        """Should raise clear error when git is not installed."""
        from scc_cli.marketplace.materialize import (
            GitNotAvailableError,
            materialize_github,
        )

        with patch(
            "scc_cli.marketplace.materialize.run_git_clone",
            side_effect=FileNotFoundError("git not found"),
        ):
            with pytest.raises(GitNotAvailableError) as exc_info:
                materialize_github(
                    name="internal",
                    source=github_source,
                    project_dir=project_dir,
                )

            assert "git" in str(exc_info.value).lower()

    def test_network_error_during_clone(self, project_dir: Path, github_source: dict) -> None:
        """Should wrap network errors with helpful message."""
        from scc_cli.marketplace.materialize import (
            MaterializationError,
            materialize_github,
        )

        with patch("scc_cli.marketplace.materialize.run_git_clone") as mock_clone:
            mock_clone.return_value = MagicMock(success=False, error="Could not resolve host")

            with pytest.raises(MaterializationError) as exc_info:
                materialize_github(
                    name="internal",
                    source=github_source,
                    project_dir=project_dir,
                )

            assert "resolve" in str(exc_info.value).lower() or "host" in str(exc_info.value).lower()

    def test_invalid_marketplace_structure(self, project_dir: Path) -> None:
        """Should fail when marketplace structure is invalid."""
        from scc_cli.marketplace.materialize import (
            InvalidMarketplaceError,
            materialize_github,
        )

        github_source = {
            "source": "github",
            "owner": "test",
            "repo": "invalid-repo",
            "branch": "main",
            "path": "/",
        }

        with patch("scc_cli.marketplace.materialize.run_git_clone") as mock_clone:
            # Clone succeeds but marketplace structure is invalid
            mock_clone.return_value = MagicMock(
                success=False,  # run_git_clone returns False when structure is invalid
                commit_sha="abc123",
                plugins=None,
                error="Missing .claude-plugin/marketplace.json",
            )

            with pytest.raises(InvalidMarketplaceError) as exc_info:
                materialize_github(
                    name="invalid",
                    source=github_source,
                    project_dir=project_dir,
                )

            assert "marketplace.json" in str(exc_info.value)
