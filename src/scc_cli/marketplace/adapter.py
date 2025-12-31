"""
Adapter for translating external org config format to internal Pydantic format.

This module implements the Anti-Corruption Layer pattern between:
- External format (JSON Schema): Human-readable, semver strings, nested organization
- Internal format (Pydantic): Python-native types, integer versioning, flat structure

The translation happens AFTER JSON Schema validation (Validation Gate) but
BEFORE Pydantic model_validate() to ensure proper type conversion.
"""

from __future__ import annotations

import copy
from typing import Any


def translate_org_config(external: dict[str, Any]) -> dict[str, Any]:
    """Translate external JSON format to internal Pydantic format.

    External format (from org config JSON):
      - organization.name, organization.id (nested)
      - schema_version: "1.0.0" (semver string)

    Internal format (for Pydantic):
      - name (flat at root level)
      - schema_version: 1 (integer, major version only)

    Uses deepcopy to prevent side-effects on cached external configuration.

    Args:
        external: External org config dict (from cache or remote fetch)

    Returns:
        Internal format dict ready for Pydantic model_validate()

    Examples:
        >>> external = {
        ...     "schema_version": "1.0.0",
        ...     "organization": {"name": "Acme Corp", "id": "acme"},
        ...     "profiles": {}
        ... }
        >>> internal = translate_org_config(external)
        >>> internal["name"]
        'Acme Corp'
        >>> internal["schema_version"]
        1
    """
    # Use deepcopy to prevent cache poisoning via shallow copy mutations
    internal = copy.deepcopy(external)

    # ── Flatten organization object ───────────────────────────────────────────
    # Pop the nested organization structure, default to empty dict if missing
    org_data = internal.pop("organization", {})

    # Only map 'name' if it wasn't already at the top level (precedence rule)
    # This handles the case where config is already in internal format
    if "name" not in internal and "name" in org_data:
        internal["name"] = org_data["name"]

    # ── Convert semver string to integer ──────────────────────────────────────
    raw_version = internal.get("schema_version")
    if isinstance(raw_version, str):
        # Remove common 'v' prefix if present (e.g., "v1.0.0" -> "1.0.0")
        clean_version = raw_version.lstrip("vV")
        try:
            # Handle both "1.0.0" -> 1 and "1" -> 1
            internal["schema_version"] = int(clean_version.split(".")[0])
        except ValueError:
            # If parsing fails, leave as-is; Pydantic will catch the type error
            # and provide better error context than a generic ValueError
            pass

    return internal
