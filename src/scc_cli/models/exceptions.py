"""Define exception system data models for SCC Phase 2.1.

Provide the core data structures for the time-bounded exception system
that lets developers unblock themselves from delegation failures while
preserving security boundaries.

Key concepts:
- BlockReason: Distinguishes SECURITY (policy-only override) from
  DELEGATION (local override allowed)
- AllowTargets: Specifies plugins, mcp_servers, base_images to allow
- Exception: A single time-bounded exception with metadata
- ExceptionFile: Envelope with schema versioning for forward compatibility
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal


class BlockReason(Enum):
    """Classifies why something was blocked.

    SECURITY: Blocked by org security policy. Only policy exceptions
              (PR-approved) can override.
    DELEGATION: Denied because team not delegated for additions.
                Local overrides (self-serve) can unblock.
    """

    SECURITY = "security"
    DELEGATION = "delegation"


@dataclass
class AllowTargets:
    """Specifies what an exception allows.

    SCC-shaped targets only:
    - plugins: Plugin IDs/names to allow
    - mcp_servers: SCC-managed MCP server names to allow
    - base_images: Docker image refs/patterns to allow
    """

    plugins: list[str] = field(default_factory=list)
    mcp_servers: list[str] = field(default_factory=list)
    base_images: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        """Return True if no targets are specified."""
        return not self.plugins and not self.mcp_servers and not self.base_images

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "plugins": self.plugins,
            "mcp_servers": self.mcp_servers,
            "base_images": self.base_images,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> AllowTargets:
        """Deserialize from dictionary, handling missing keys gracefully."""
        return cls(
            plugins=d.get("plugins", []),
            mcp_servers=d.get("mcp_servers", []),
            base_images=d.get("base_images", []),
        )


@dataclass
class Exception:
    """A time-bounded exception that allows specific resources.

    Required fields:
    - id: Unique identifier (local-YYYYMMDD-XXXX for local, user-provided for policy)
    - created_at: RFC3339 timestamp in UTC
    - expires_at: RFC3339 timestamp in UTC
    - reason: Required non-empty explanation
    - scope: "policy" or "local"
    - allow: AllowTargets specifying what to allow

    Optional metadata:
    - created_by: Username/email of creator
    - created_on: Hostname where created
    - source: Derived at runtime (org|team|project|repo|user)

    Forward compatibility:
    - _extra: Dict preserving unknown fields from newer schema versions
    """

    id: str
    created_at: str
    expires_at: str
    reason: str
    scope: Literal["policy", "local"]
    allow: AllowTargets

    # Optional metadata
    created_by: str | None = None
    created_on: str | None = None
    source: str | None = None

    # Forward compatibility
    _extra: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Return True if exception has expired."""
        now = datetime.now(timezone.utc)
        # Parse expires_at as RFC3339
        expires = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
        return now > expires

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary, including _extra fields."""
        result: dict[str, Any] = {
            "id": self.id,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "reason": self.reason,
            "scope": self.scope,
            "allow": self.allow.to_dict(),
        }

        # Add optional metadata if present
        if self.created_by is not None:
            result["created_by"] = self.created_by
        if self.created_on is not None:
            result["created_on"] = self.created_on
        if self.source is not None:
            result["source"] = self.source

        # Include _extra fields at top level for roundtrip
        result.update(self._extra)

        return result

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Exception:
        """Deserialize from dictionary, preserving unknown fields in _extra."""
        known_keys = {
            "id",
            "created_at",
            "expires_at",
            "reason",
            "scope",
            "allow",
            "created_by",
            "created_on",
            "source",
        }

        # Extract _extra fields
        extra = {k: v for k, v in d.items() if k not in known_keys}

        return cls(
            id=d["id"],
            created_at=d["created_at"],
            expires_at=d["expires_at"],
            reason=d["reason"],
            scope=d["scope"],
            allow=AllowTargets.from_dict(d.get("allow", {})),
            created_by=d.get("created_by"),
            created_on=d.get("created_on"),
            source=d.get("source"),
            _extra=extra,
        )


@dataclass
class ExceptionFile:
    """Envelope for exception storage with schema versioning.

    Provides forward compatibility through:
    - schema_version: Current schema version (1)
    - tool_version: SCC version that wrote the file
    - min_scc_version: Minimum SCC version required to parse
    - _extra: Preserves unknown fields for roundtrip

    When reading files:
    - Local stores with newer schema: warn + ignore (fail-open)
    - Policy exceptions with newer schema: warn + ignore entirely (fail-closed)
    """

    schema_version: int = 1
    tool_version: str | None = None
    min_scc_version: str | None = None
    exceptions: list[Exception] = field(default_factory=list)
    _extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary with stable exception ordering."""
        # Sort exceptions by created_at, then by id for stable ordering
        sorted_exceptions = sorted(
            self.exceptions,
            key=lambda e: (e.created_at, e.id),
        )

        result: dict[str, Any] = {
            "schema_version": self.schema_version,
            "exceptions": [e.to_dict() for e in sorted_exceptions],
        }

        # Add optional metadata if present
        if self.tool_version is not None:
            result["tool_version"] = self.tool_version
        if self.min_scc_version is not None:
            result["min_scc_version"] = self.min_scc_version

        # Include _extra fields at top level
        result.update(self._extra)

        return result

    def to_json(self) -> str:
        """Serialize to JSON with sorted keys and 2-space indentation."""
        return json.dumps(self.to_dict(), sort_keys=True, indent=2)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ExceptionFile:
        """Deserialize from dictionary, preserving unknown fields."""
        known_keys = {
            "schema_version",
            "tool_version",
            "min_scc_version",
            "exceptions",
        }

        # Extract _extra fields
        extra = {k: v for k, v in d.items() if k not in known_keys}

        # Parse exceptions list
        exceptions = [Exception.from_dict(e) for e in d.get("exceptions", [])]

        return cls(
            schema_version=d.get("schema_version", 1),
            tool_version=d.get("tool_version"),
            min_scc_version=d.get("min_scc_version"),
            exceptions=exceptions,
            _extra=extra,
        )

    @classmethod
    def from_json(cls, json_str: str) -> ExceptionFile:
        """Parse JSON string into ExceptionFile."""
        return cls.from_dict(json.loads(json_str))


def generate_local_id() -> str:
    """Generate a unique local exception ID.

    Format: local-YYYYMMDD-XXXX
    Where XXXX is 4 random hex characters.

    Example: local-20251221-a3f2
    """
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    random_hex = secrets.token_hex(2)  # 2 bytes = 4 hex chars
    return f"local-{today}-{random_hex}"


# Convenience functions for JSON operations
def exception_file_to_json(ef: ExceptionFile) -> str:
    """Serialize ExceptionFile to JSON string."""
    return ef.to_json()


def exception_file_from_json(json_str: str) -> ExceptionFile:
    """Parse JSON string into ExceptionFile."""
    return ExceptionFile.from_json(json_str)
