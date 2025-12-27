"""
Integration test fixtures for SCC marketplace federation.

Provides:
- temp_home: Isolated XDG paths for config/cache
- sample_org_config: Pre-configured OrganizationConfig
- sample_team_config: Pre-configured TeamConfig
- frozen_time: Time injection via freezegun (if available)
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

from scc_cli.marketplace.schema import (
    DefaultsConfig,
    MarketplaceSourceDirectory,
    MarketplaceSourceGitHub,
    OrganizationConfig,
    SecurityConfig,
    TeamConfig,
    TeamProfile,
    TrustGrant,
)

if TYPE_CHECKING:
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Path Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def temp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create isolated XDG paths for testing.

    Sets up:
    - XDG_CONFIG_HOME -> tmp_path/config
    - XDG_CACHE_HOME -> tmp_path/cache
    - XDG_DATA_HOME -> tmp_path/data
    - HOME -> tmp_path

    Returns:
        Path to temporary home directory
    """
    config_dir = tmp_path / "config" / "scc"
    cache_dir = tmp_path / "cache" / "scc"
    data_dir = tmp_path / "data" / "scc"

    config_dir.mkdir(parents=True)
    cache_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("HOME", str(tmp_path))

    return tmp_path


# ─────────────────────────────────────────────────────────────────────────────
# Organization Config Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_org_config() -> OrganizationConfig:
    """Create a sample organization config for testing.

    Includes:
    - Two marketplaces (internal, shared)
    - Two teams (backend, frontend)
    - Security blocked plugins
    - Default enabled plugins
    """
    return OrganizationConfig(
        name="Test Organization",
        schema_version=1,
        marketplaces={
            "internal": MarketplaceSourceGitHub(
                source="github",
                owner="test-org",
                repo="internal-plugins",
            ),
            "shared": MarketplaceSourceGitHub(
                source="github",
                owner="test-org",
                repo="shared-plugins",
            ),
        },
        defaults=DefaultsConfig(
            enabled_plugins=[
                "code-review@internal",
                "linting@shared",
            ],
            disabled_plugins=[],
            extra_marketplaces=["internal", "shared"],
        ),
        profiles={
            "backend": TeamProfile(
                name="Backend Team",
                additional_plugins=["api-tools@internal"],
                disabled_plugins=[],
            ),
            "frontend": TeamProfile(
                name="Frontend Team",
                additional_plugins=["ui-tools@shared"],
                disabled_plugins=["api-*"],
            ),
            "federated": TeamProfile(
                name="Federated Team",
                config_source={
                    "source": "github",
                    "owner": "test-team",
                    "repo": "team-config",
                },
                trust=TrustGrant(
                    inherit_org_marketplaces=True,
                    allow_additional_marketplaces=True,
                    marketplace_source_patterns=["github.com/test-*/**"],
                ),
            ),
        },
        security=SecurityConfig(
            blocked_plugins=["malicious-*", "unsafe-tool@*"],
            blocked_reason="Blocked by security policy",
        ),
    )


@pytest.fixture
def org_with_blocked_case_variations() -> OrganizationConfig:
    """Org config with blocked patterns in various cases for case-sensitivity testing."""
    return OrganizationConfig(
        name="Case Test Org",
        schema_version=1,
        marketplaces={
            "shared": MarketplaceSourceGitHub(
                source="github",
                owner="test-org",
                repo="plugins",
            ),
        },
        defaults=DefaultsConfig(
            enabled_plugins=[],
        ),
        profiles={
            "test-team": TeamProfile(
                name="Test Team",
                additional_plugins=[
                    "MALICIOUS-tool@shared",
                    "Malicious-Tool@shared",
                    "malicious-exploit@shared",
                    "safe-tool@shared",
                ],
            ),
        },
        security=SecurityConfig(
            blocked_plugins=["Malicious-*"],  # Mixed case pattern
            blocked_reason="Blocked for security",
        ),
    )


@pytest.fixture
def org_with_multiple_marketplaces() -> OrganizationConfig:
    """Org config with 2+ marketplaces for AmbiguousMarketplaceError testing."""
    return OrganizationConfig(
        name="Multi-Marketplace Org",
        schema_version=1,
        marketplaces={
            "market-a": MarketplaceSourceGitHub(
                source="github",
                owner="org",
                repo="market-a",
            ),
            "market-b": MarketplaceSourceGitHub(
                source="github",
                owner="org",
                repo="market-b",
            ),
        },
        defaults=DefaultsConfig(enabled_plugins=[]),
        profiles={
            "test-team": TeamProfile(
                name="Test Team",
                additional_plugins=["bare-plugin"],  # No @marketplace suffix
            ),
        },
        security=SecurityConfig(),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Team Config Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_team_config() -> TeamConfig:
    """Create a sample team config for federated testing."""
    return TeamConfig(
        schema_version=1,
        enabled_plugins=[
            "team-tool@team-marketplace",
            "shared-tool@shared",
        ],
        disabled_plugins=["deprecated-*"],
        marketplaces={
            "team-marketplace": MarketplaceSourceGitHub(
                source="github",
                owner="test-team",
                repo="team-plugins",
            ),
        },
    )


@pytest.fixture
def team_config_with_directory_source(tmp_path: Path) -> TeamConfig:
    """Team config with directory marketplace source for symlink testing."""
    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()

    return TeamConfig(
        schema_version=1,
        enabled_plugins=["local-tool@local"],
        marketplaces={
            "local": MarketplaceSourceDirectory(
                source="directory",
                path=str(plugins_dir),
            ),
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Trust Grant Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def restrictive_trust() -> TrustGrant:
    """Trust grant with minimal permissions."""
    return TrustGrant(
        inherit_org_marketplaces=False,
        allow_additional_marketplaces=False,
        marketplace_source_patterns=[],
    )


@pytest.fixture
def permissive_trust() -> TrustGrant:
    """Trust grant with wide permissions."""
    return TrustGrant(
        inherit_org_marketplaces=True,
        allow_additional_marketplaces=True,
        marketplace_source_patterns=["github.com/**", "gitlab.com/**"],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Time Injection Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture
def frozen_time() -> Generator[Any, None, None]:
    """Freeze time for cache TTL testing.

    Requires freezegun: pip install freezegun

    Usage:
        def test_cache_expiry(frozen_time: Any) -> None:
            # Create cache at T=0
            create_cache()

            # Move forward 24 hours
            frozen_time.move_to("2025-12-27 12:00:00")

            # Cache should be expired
            assert cache_is_expired()
    """
    try:
        import freezegun
    except ImportError:
        pytest.skip("freezegun not installed")
        return

    with freezegun.freeze_time("2025-12-26 12:00:00") as frozen:
        yield frozen


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────


def write_org_config(path: Path, config: OrganizationConfig) -> Path:
    """Write OrganizationConfig to JSON file.

    Args:
        path: Directory to write config to
        config: OrganizationConfig to serialize

    Returns:
        Path to written file
    """
    config_file = path / "org_config.json"
    config_file.write_text(config.model_dump_json(indent=2))
    return config_file


def write_team_config(path: Path, config: TeamConfig) -> Path:
    """Write TeamConfig to JSON file.

    Args:
        path: Directory to write config to
        config: TeamConfig to serialize

    Returns:
        Path to written file
    """
    config_file = path / "team_config.json"
    config_file.write_text(config.model_dump_json(indent=2))
    return config_file


def create_symlink_escape(base_dir: Path) -> tuple[Path, Path]:
    """Create a directory structure with symlink escaping base.

    Creates:
    - base_dir/plugins/ (allowed directory)
    - base_dir/evil/ (directory outside allowed)
    - base_dir/plugins/trusted-plugin -> ../evil (symlink escape)

    Args:
        base_dir: Base directory for the structure

    Returns:
        Tuple of (allowed_dir, symlink_path)
    """
    plugins_dir = base_dir / "plugins"
    evil_dir = base_dir / "evil"

    plugins_dir.mkdir(parents=True, exist_ok=True)
    evil_dir.mkdir(parents=True, exist_ok=True)

    # Create a symlink that escapes the plugins directory
    symlink_path = plugins_dir / "trusted-plugin"
    symlink_path.symlink_to(evil_dir)

    return plugins_dir, symlink_path
