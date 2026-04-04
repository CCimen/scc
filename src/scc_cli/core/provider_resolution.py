"""Pure-logic provider resolution.

Resolves which agent provider to use based on precedence:
  CLI flag > user config > default ('claude')

Policy validation checks the resolved provider against
the team's allowed_providers list.
"""

from __future__ import annotations

KNOWN_PROVIDERS: tuple[str, ...] = ("claude", "codex")

_DEFAULT_PROVIDER: str = "claude"


def resolve_active_provider(
    cli_flag: str | None,
    config_provider: str | None,
    allowed_providers: tuple[str, ...] = (),
) -> str:
    """Resolve the active provider from multiple sources.

    Precedence: cli_flag > config_provider > default ('claude').

    Args:
        cli_flag: Provider specified via --provider on the CLI.
        config_provider: Provider persisted in user config.
        allowed_providers: Tuple of allowed provider IDs from team policy.
            Empty tuple means all known providers are allowed.

    Returns:
        The resolved provider ID string.

    Raises:
        ValueError: If the resolved provider is not in KNOWN_PROVIDERS.
        ProviderNotAllowedError: If the resolved provider is blocked
            by the team's allowed_providers policy.
    """
    from scc_cli.core.errors import ProviderNotAllowedError

    provider = cli_flag or config_provider or _DEFAULT_PROVIDER

    if provider not in KNOWN_PROVIDERS:
        raise ValueError(
            f"Unknown provider '{provider}'. Known providers: {', '.join(KNOWN_PROVIDERS)}"
        )

    if allowed_providers and provider not in allowed_providers:
        raise ProviderNotAllowedError(
            provider_id=provider,
            allowed_providers=allowed_providers,
        )

    return provider
