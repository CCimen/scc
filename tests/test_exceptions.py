"""Tests for the exception system data models (Phase 2.1).

TDD approach: Write tests first, implement to make them pass.

Tests cover:
- BlockReason enum (SECURITY vs DELEGATION)
- AllowTargets dataclass (plugins, mcp_servers, base_images)
- Exception dataclass with all fields
- ExceptionFile envelope with schema versioning
- JSON serialization/deserialization with stable ordering
- Forward compatibility (_extra dict preservation)
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

# Will import from scc_cli.models.exceptions once implemented
# For now, these imports will fail until we implement the models

if TYPE_CHECKING:
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# BlockReason Enum Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestBlockReason:
    """Tests for the BlockReason enum."""

    def test_security_value(self):
        """BlockReason.SECURITY has correct string value."""
        from scc_cli.models.exceptions import BlockReason

        assert BlockReason.SECURITY.value == "security"

    def test_delegation_value(self):
        """BlockReason.DELEGATION has correct string value."""
        from scc_cli.models.exceptions import BlockReason

        assert BlockReason.DELEGATION.value == "delegation"

    def test_only_two_values(self):
        """BlockReason only has SECURITY and DELEGATION values."""
        from scc_cli.models.exceptions import BlockReason

        assert len(BlockReason) == 2
        assert set(br.value for br in BlockReason) == {"security", "delegation"}

    def test_can_create_from_string(self):
        """BlockReason can be created from string value."""
        from scc_cli.models.exceptions import BlockReason

        assert BlockReason("security") == BlockReason.SECURITY
        assert BlockReason("delegation") == BlockReason.DELEGATION

    def test_invalid_string_raises(self):
        """Creating BlockReason from invalid string raises ValueError."""
        from scc_cli.models.exceptions import BlockReason

        with pytest.raises(ValueError):
            BlockReason("invalid")


# ═══════════════════════════════════════════════════════════════════════════════
# AllowTargets Dataclass Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAllowTargets:
    """Tests for the AllowTargets dataclass."""

    def test_empty_targets(self):
        """AllowTargets can be created with empty lists."""
        from scc_cli.models.exceptions import AllowTargets

        targets = AllowTargets()
        assert targets.plugins == []
        assert targets.mcp_servers == []
        assert targets.base_images == []

    def test_with_plugins(self):
        """AllowTargets stores plugin IDs."""
        from scc_cli.models.exceptions import AllowTargets

        targets = AllowTargets(plugins=["plugin-a", "plugin-b"])
        assert targets.plugins == ["plugin-a", "plugin-b"]
        assert targets.mcp_servers == []
        assert targets.base_images == []

    def test_with_mcp_servers(self):
        """AllowTargets stores MCP server names."""
        from scc_cli.models.exceptions import AllowTargets

        targets = AllowTargets(mcp_servers=["jira-api", "confluence"])
        assert targets.mcp_servers == ["jira-api", "confluence"]

    def test_with_base_images(self):
        """AllowTargets stores base image refs/patterns."""
        from scc_cli.models.exceptions import AllowTargets

        targets = AllowTargets(base_images=["nginx:*", "python:3.11"])
        assert targets.base_images == ["nginx:*", "python:3.11"]

    def test_with_all_targets(self):
        """AllowTargets stores all target types."""
        from scc_cli.models.exceptions import AllowTargets

        targets = AllowTargets(
            plugins=["plugin-a"],
            mcp_servers=["jira-api"],
            base_images=["nginx:1.25"],
        )
        assert targets.plugins == ["plugin-a"]
        assert targets.mcp_servers == ["jira-api"]
        assert targets.base_images == ["nginx:1.25"]

    def test_is_empty_true(self):
        """is_empty returns True for empty targets."""
        from scc_cli.models.exceptions import AllowTargets

        targets = AllowTargets()
        assert targets.is_empty() is True

    def test_is_empty_false(self):
        """is_empty returns False for non-empty targets."""
        from scc_cli.models.exceptions import AllowTargets

        targets = AllowTargets(plugins=["plugin-a"])
        assert targets.is_empty() is False

    def test_to_dict(self):
        """AllowTargets serializes to dict."""
        from scc_cli.models.exceptions import AllowTargets

        targets = AllowTargets(plugins=["a"], mcp_servers=["b"], base_images=["c"])
        d = targets.to_dict()
        assert d == {"plugins": ["a"], "mcp_servers": ["b"], "base_images": ["c"]}

    def test_from_dict(self):
        """AllowTargets deserializes from dict."""
        from scc_cli.models.exceptions import AllowTargets

        d = {"plugins": ["a"], "mcp_servers": ["b"], "base_images": ["c"]}
        targets = AllowTargets.from_dict(d)
        assert targets.plugins == ["a"]
        assert targets.mcp_servers == ["b"]
        assert targets.base_images == ["c"]

    def test_from_dict_missing_keys(self):
        """AllowTargets handles missing keys gracefully."""
        from scc_cli.models.exceptions import AllowTargets

        d = {"plugins": ["a"]}  # Missing mcp_servers and base_images
        targets = AllowTargets.from_dict(d)
        assert targets.plugins == ["a"]
        assert targets.mcp_servers == []
        assert targets.base_images == []


# ═══════════════════════════════════════════════════════════════════════════════
# Exception Dataclass Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestException:
    """Tests for the Exception dataclass."""

    def test_required_fields(self):
        """Exception requires id, created_at, expires_at, reason, scope, allow."""
        from scc_cli.models.exceptions import AllowTargets, Exception

        exc = Exception(
            id="local-20251221-a3f2",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2025-12-21T18:00:00Z",
            reason="Testing",
            scope="local",
            allow=AllowTargets(mcp_servers=["jira-api"]),
        )
        assert exc.id == "local-20251221-a3f2"
        assert exc.reason == "Testing"
        assert exc.scope == "local"

    def test_optional_metadata_defaults(self):
        """Exception has optional metadata fields with None defaults."""
        from scc_cli.models.exceptions import AllowTargets, Exception

        exc = Exception(
            id="local-20251221-a3f2",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2025-12-21T18:00:00Z",
            reason="Testing",
            scope="local",
            allow=AllowTargets(),
        )
        assert exc.created_by is None
        assert exc.created_on is None
        assert exc.source is None

    def test_optional_metadata_provided(self):
        """Exception stores optional metadata when provided."""
        from scc_cli.models.exceptions import AllowTargets, Exception

        exc = Exception(
            id="local-20251221-a3f2",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2025-12-21T18:00:00Z",
            reason="Testing",
            scope="local",
            allow=AllowTargets(),
            created_by="dev@example.com",
            created_on="workstation-1",
            source="user",
        )
        assert exc.created_by == "dev@example.com"
        assert exc.created_on == "workstation-1"
        assert exc.source == "user"

    def test_extra_dict_default(self):
        """Exception has _extra dict for forward compatibility."""
        from scc_cli.models.exceptions import AllowTargets, Exception

        exc = Exception(
            id="local-20251221-a3f2",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2025-12-21T18:00:00Z",
            reason="Testing",
            scope="local",
            allow=AllowTargets(),
        )
        assert exc._extra == {}

    def test_scope_must_be_policy_or_local(self):
        """Exception scope must be 'policy' or 'local'."""
        from scc_cli.models.exceptions import AllowTargets, Exception

        # Valid scopes
        exc1 = Exception(
            id="1",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2025-12-21T18:00:00Z",
            reason="Test",
            scope="local",
            allow=AllowTargets(),
        )
        assert exc1.scope == "local"

        exc2 = Exception(
            id="2",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2025-12-21T18:00:00Z",
            reason="Test",
            scope="policy",
            allow=AllowTargets(),
        )
        assert exc2.scope == "policy"

    def test_is_expired_true(self):
        """is_expired returns True for expired exception."""
        from scc_cli.models.exceptions import AllowTargets, Exception

        exc = Exception(
            id="1",
            created_at="2025-01-01T10:00:00Z",
            expires_at="2025-01-01T18:00:00Z",  # Past date
            reason="Test",
            scope="local",
            allow=AllowTargets(),
        )
        assert exc.is_expired() is True

    def test_is_expired_false(self):
        """is_expired returns False for active exception."""
        from scc_cli.models.exceptions import AllowTargets, Exception

        # Far future date
        exc = Exception(
            id="1",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2099-12-31T23:59:59Z",
            reason="Test",
            scope="local",
            allow=AllowTargets(),
        )
        assert exc.is_expired() is False

    def test_to_dict(self):
        """Exception serializes to dict."""
        from scc_cli.models.exceptions import AllowTargets, Exception

        exc = Exception(
            id="local-20251221-a3f2",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2025-12-21T18:00:00Z",
            reason="Testing",
            scope="local",
            allow=AllowTargets(mcp_servers=["jira-api"]),
            created_by="dev@example.com",
        )
        d = exc.to_dict()
        assert d["id"] == "local-20251221-a3f2"
        assert d["reason"] == "Testing"
        assert d["scope"] == "local"
        assert d["allow"] == {"plugins": [], "mcp_servers": ["jira-api"], "base_images": []}
        assert d["created_by"] == "dev@example.com"

    def test_from_dict(self):
        """Exception deserializes from dict."""
        from scc_cli.models.exceptions import Exception

        d = {
            "id": "local-20251221-a3f2",
            "created_at": "2025-12-21T10:00:00Z",
            "expires_at": "2025-12-21T18:00:00Z",
            "reason": "Testing",
            "scope": "local",
            "allow": {"mcp_servers": ["jira-api"]},
        }
        exc = Exception.from_dict(d)
        assert exc.id == "local-20251221-a3f2"
        assert exc.allow.mcp_servers == ["jira-api"]

    def test_from_dict_preserves_extra_fields(self):
        """Exception.from_dict preserves unknown fields in _extra."""
        from scc_cli.models.exceptions import Exception

        d = {
            "id": "local-20251221-a3f2",
            "created_at": "2025-12-21T10:00:00Z",
            "expires_at": "2025-12-21T18:00:00Z",
            "reason": "Testing",
            "scope": "local",
            "allow": {},
            "future_field": "value",  # Unknown field
            "another_field": 42,
        }
        exc = Exception.from_dict(d)
        assert exc._extra == {"future_field": "value", "another_field": 42}

    def test_to_dict_includes_extra_fields(self):
        """Exception.to_dict includes _extra fields in output."""
        from scc_cli.models.exceptions import AllowTargets, Exception

        exc = Exception(
            id="1",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2025-12-21T18:00:00Z",
            reason="Test",
            scope="local",
            allow=AllowTargets(),
            _extra={"future_field": "value"},
        )
        d = exc.to_dict()
        assert d["future_field"] == "value"


# ═══════════════════════════════════════════════════════════════════════════════
# ExceptionFile Envelope Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestExceptionFile:
    """Tests for the ExceptionFile envelope dataclass."""

    def test_default_schema_version(self):
        """ExceptionFile defaults to schema_version=1."""
        from scc_cli.models.exceptions import ExceptionFile

        ef = ExceptionFile()
        assert ef.schema_version == 1

    def test_default_exceptions_empty(self):
        """ExceptionFile defaults to empty exceptions list."""
        from scc_cli.models.exceptions import ExceptionFile

        ef = ExceptionFile()
        assert ef.exceptions == []

    def test_optional_metadata_defaults(self):
        """ExceptionFile has optional metadata with None defaults."""
        from scc_cli.models.exceptions import ExceptionFile

        ef = ExceptionFile()
        assert ef.tool_version is None
        assert ef.min_scc_version is None

    def test_with_tool_version(self):
        """ExceptionFile stores tool_version when provided."""
        from scc_cli.models.exceptions import ExceptionFile

        ef = ExceptionFile(tool_version="2.1.0")
        assert ef.tool_version == "2.1.0"

    def test_with_min_scc_version(self):
        """ExceptionFile stores min_scc_version when provided."""
        from scc_cli.models.exceptions import ExceptionFile

        ef = ExceptionFile(min_scc_version="2.0.0")
        assert ef.min_scc_version == "2.0.0"

    def test_extra_dict_default(self):
        """ExceptionFile has _extra dict for forward compatibility."""
        from scc_cli.models.exceptions import ExceptionFile

        ef = ExceptionFile()
        assert ef._extra == {}

    def test_with_exceptions(self):
        """ExceptionFile stores exceptions list."""
        from scc_cli.models.exceptions import AllowTargets, Exception, ExceptionFile

        exc = Exception(
            id="1",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2025-12-21T18:00:00Z",
            reason="Test",
            scope="local",
            allow=AllowTargets(),
        )
        ef = ExceptionFile(exceptions=[exc])
        assert len(ef.exceptions) == 1
        assert ef.exceptions[0].id == "1"

    def test_to_dict(self):
        """ExceptionFile serializes to dict."""
        from scc_cli.models.exceptions import ExceptionFile

        ef = ExceptionFile(schema_version=1, tool_version="2.1.0")
        d = ef.to_dict()
        assert d["schema_version"] == 1
        assert d["tool_version"] == "2.1.0"
        assert d["exceptions"] == []

    def test_from_dict(self):
        """ExceptionFile deserializes from dict."""
        from scc_cli.models.exceptions import ExceptionFile

        d = {
            "schema_version": 1,
            "tool_version": "2.1.0",
            "exceptions": [],
        }
        ef = ExceptionFile.from_dict(d)
        assert ef.schema_version == 1
        assert ef.tool_version == "2.1.0"

    def test_from_dict_preserves_extra_fields(self):
        """ExceptionFile.from_dict preserves unknown fields in _extra."""
        from scc_cli.models.exceptions import ExceptionFile

        d = {
            "schema_version": 1,
            "exceptions": [],
            "future_flag": True,
        }
        ef = ExceptionFile.from_dict(d)
        assert ef._extra == {"future_flag": True}

    def test_to_dict_includes_extra_fields(self):
        """ExceptionFile.to_dict includes _extra fields in output."""
        from scc_cli.models.exceptions import ExceptionFile

        ef = ExceptionFile(_extra={"future_flag": True})
        d = ef.to_dict()
        assert d["future_flag"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# JSON Serialization Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestJsonSerialization:
    """Tests for JSON serialization with stable ordering."""

    def test_to_json_sorted_keys(self):
        """to_json outputs sorted keys for git-friendliness."""
        from scc_cli.models.exceptions import ExceptionFile

        ef = ExceptionFile(schema_version=1, tool_version="2.1.0")
        json_str = ef.to_json()
        parsed = json.loads(json_str)
        # Keys should be in alphabetical order
        keys = list(parsed.keys())
        assert keys == sorted(keys)

    def test_to_json_two_space_indent(self):
        """to_json uses 2-space indentation."""
        from scc_cli.models.exceptions import ExceptionFile

        ef = ExceptionFile(schema_version=1)
        json_str = ef.to_json()
        # Check for 2-space indentation pattern
        assert '  "' in json_str

    def test_exceptions_sorted_by_created_at_then_id(self):
        """Exceptions list is sorted by created_at, then id."""
        from scc_cli.models.exceptions import AllowTargets, Exception, ExceptionFile

        exc_c = Exception(
            id="c",
            created_at="2025-12-21T12:00:00Z",
            expires_at="2025-12-21T20:00:00Z",
            reason="Third by time",
            scope="local",
            allow=AllowTargets(),
        )
        exc_a = Exception(
            id="a",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2025-12-21T18:00:00Z",
            reason="First by time",
            scope="local",
            allow=AllowTargets(),
        )
        exc_b = Exception(
            id="b",
            created_at="2025-12-21T10:00:00Z",  # Same time as 'a'
            expires_at="2025-12-21T18:00:00Z",
            reason="Second by id",
            scope="local",
            allow=AllowTargets(),
        )
        # Add in wrong order
        ef = ExceptionFile(exceptions=[exc_c, exc_b, exc_a])
        d = ef.to_dict()
        # Should be sorted: a (first time, first id), b (same time, second id), c (later time)
        assert d["exceptions"][0]["id"] == "a"
        assert d["exceptions"][1]["id"] == "b"
        assert d["exceptions"][2]["id"] == "c"

    def test_from_json(self):
        """from_json parses JSON string."""
        from scc_cli.models.exceptions import ExceptionFile

        json_str = '{"schema_version": 1, "exceptions": [], "tool_version": "2.1.0"}'
        ef = ExceptionFile.from_json(json_str)
        assert ef.schema_version == 1
        assert ef.tool_version == "2.1.0"

    def test_roundtrip_preserves_data(self):
        """JSON roundtrip preserves all data including _extra."""
        from scc_cli.models.exceptions import AllowTargets, Exception, ExceptionFile

        exc = Exception(
            id="local-20251221-a3f2",
            created_at="2025-12-21T10:00:00Z",
            expires_at="2025-12-21T18:00:00Z",
            reason="Testing roundtrip",
            scope="local",
            allow=AllowTargets(mcp_servers=["jira-api"]),
            created_by="dev@example.com",
            _extra={"future_field": "preserved"},
        )
        ef = ExceptionFile(
            schema_version=1,
            tool_version="2.1.0",
            exceptions=[exc],
            _extra={"file_level_extra": True},
        )

        # Roundtrip
        json_str = ef.to_json()
        ef2 = ExceptionFile.from_json(json_str)

        # All data preserved
        assert ef2.schema_version == ef.schema_version
        assert ef2.tool_version == ef.tool_version
        assert ef2._extra == ef._extra
        assert len(ef2.exceptions) == 1
        assert ef2.exceptions[0].id == exc.id
        assert ef2.exceptions[0]._extra == exc._extra


# ═══════════════════════════════════════════════════════════════════════════════
# ID Generation Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestIdGeneration:
    """Tests for exception ID generation."""

    def test_generate_local_id_format(self):
        """generate_local_id returns format: local-YYYYMMDD-XXXX."""
        from scc_cli.models.exceptions import generate_local_id

        id = generate_local_id()
        # Format: local-YYYYMMDD-XXXX (4 random hex chars)
        assert id.startswith("local-")
        parts = id.split("-")
        assert len(parts) == 3
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 4  # 4 hex chars
        # Verify hex
        int(parts[2], 16)  # Should not raise

    def test_generate_local_id_unique(self):
        """generate_local_id returns unique IDs."""
        from scc_cli.models.exceptions import generate_local_id

        # Using 10 iterations to minimize birthday paradox collision risk
        # (4 hex chars = 65536 possibilities, 10 samples ≈ 0.07% collision chance)
        ids = [generate_local_id() for _ in range(10)]
        assert len(set(ids)) == 10  # All unique
