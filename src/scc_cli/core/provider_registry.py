"""Canonical provider runtime registry.

Single source of truth for provider-specific runtime constants
(image ref, config directory, settings path, data volume).  Replaces
the scattered ``_PROVIDER_*`` dicts that lived in start_session and
dependencies modules.

This module sits at the composition layer — it imports from ``core``
only.  Do NOT import from ``adapters``, ``commands``, or ``application``.
"""

from __future__ import annotations

from scc_cli.core.contracts import ProviderRuntimeSpec
from scc_cli.core.errors import InvalidProviderError
from scc_cli.core.image_contracts import SCC_CLAUDE_IMAGE_REF, SCC_CODEX_IMAGE_REF

PROVIDER_REGISTRY: dict[str, ProviderRuntimeSpec] = {
    "claude": ProviderRuntimeSpec(
        provider_id="claude",
        display_name="Claude Code",
        image_ref=SCC_CLAUDE_IMAGE_REF,
        config_dir=".claude",
        settings_path=".claude/settings.json",
        data_volume="docker-claude-sandbox-data",
    ),
    "codex": ProviderRuntimeSpec(
        provider_id="codex",
        display_name="Codex",
        image_ref=SCC_CODEX_IMAGE_REF,
        config_dir=".codex",
        settings_path=".codex/config.toml",
        data_volume="docker-codex-sandbox-data",
    ),
}


def get_runtime_spec(provider_id: str) -> ProviderRuntimeSpec:
    """Look up runtime constants for a provider.  Fail-closed on unknown IDs.

    Args:
        provider_id: The provider identifier (e.g. ``"claude"``, ``"codex"``).

    Returns:
        The frozen runtime spec for the provider.

    Raises:
        InvalidProviderError: If *provider_id* is not in the registry.
    """
    try:
        return PROVIDER_REGISTRY[provider_id]
    except KeyError:
        raise InvalidProviderError(
            provider_id=provider_id,
            known_providers=tuple(PROVIDER_REGISTRY.keys()),
        )
