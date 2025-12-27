"""Tests for stats integration with launch flow.

TDD tests for Task 2.4 - Launch Integration.

Tests verify that:
- record_session_start() is called before docker run
- Stats config (enabled, user_identity_mode) is respected
- Session ID and project name are passed correctly
"""

from __future__ import annotations

import pytest

# ═══════════════════════════════════════════════════════════════════════════════
# Test fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def minimal_org_config_v2():
    """Minimal v2 org config for testing."""
    return {
        "schema_version": "2.0",
        "organization": {"name": "Test Org", "id": "test-org"},
        "defaults": {
            "allowed_plugins": ["test-plugin"],
        },
        "profiles": {
            "dev": {
                "description": "Development team",
            }
        },
    }


@pytest.fixture
def org_config_with_stats():
    """Org config with stats configuration."""
    return {
        "schema_version": "2.0",
        "organization": {"name": "Test Org", "id": "test-org"},
        "defaults": {
            "allowed_plugins": ["test-plugin"],
        },
        "profiles": {
            "dev": {
                "description": "Development team",
            }
        },
        "stats": {
            "enabled": True,
            "user_identity_mode": "hash",
        },
    }


@pytest.fixture
def org_config_stats_disabled():
    """Org config with stats disabled."""
    return {
        "schema_version": "2.0",
        "organization": {"name": "Test Org", "id": "test-org"},
        "defaults": {
            "allowed_plugins": ["test-plugin"],
        },
        "profiles": {
            "dev": {
                "description": "Development team",
            }
        },
        "stats": {
            "enabled": False,
        },
    }


@pytest.fixture
def org_config_stats_anonymous():
    """Org config with anonymous stats (no user identity)."""
    return {
        "schema_version": "2.0",
        "organization": {"name": "Test Org", "id": "test-org"},
        "defaults": {
            "allowed_plugins": ["test-plugin"],
        },
        "profiles": {
            "dev": {
                "description": "Development team",
            }
        },
        "stats": {
            "enabled": True,
            "user_identity_mode": "none",
        },
    }


@pytest.fixture
def mock_workspace(tmp_path):
    """Create a mock workspace directory."""
    workspace = tmp_path / "my-project"
    workspace.mkdir()
    return workspace
