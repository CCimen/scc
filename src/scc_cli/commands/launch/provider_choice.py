"""Policy helpers for choosing a provider at launch time."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rich.panel import Panel
from rich.table import Table

from scc_cli.application.provider_selection import resolve_provider_preference
from scc_cli.cli_common import console
from scc_cli.commands.launch.dependencies import get_agent_provider
from scc_cli.core.contracts import AuthReadiness
from scc_cli.core.errors import ProviderNotReadyError
from scc_cli.core.provider_resolution import KNOWN_PROVIDERS, get_provider_display_name
from scc_cli.ui.chrome import print_with_layout
from scc_cli.ui.prompts import prompt_with_layout


def choose_start_provider(
    *,
    cli_flag: str | None,
    resume_provider: str | None,
    workspace_last_used: str | None,
    config_provider: str | None,
    connected_provider_ids: tuple[str, ...],
    allowed_providers: tuple[str, ...],
    non_interactive: bool,
    prompt_choice: Callable[[tuple[str, ...], tuple[str, ...], str | None], str | None] | None,
) -> str | None:
    """Choose the provider for a start request using stable precedence."""
    resolved = resolve_provider_preference(
        cli_flag=cli_flag,
        resume_provider=resume_provider,
        workspace_last_used=workspace_last_used,
        global_preferred=config_provider,
        allowed_providers=allowed_providers,
    )
    if resolved is not None:
        return resolved.provider_id

    candidates = allowed_providers or KNOWN_PROVIDERS
    connected_allowed = tuple(pid for pid in connected_provider_ids if pid in candidates)

    if len(connected_allowed) == 1:
        return connected_allowed[0]
    if len(candidates) == 1:
        return candidates[0]

    if non_interactive:
        raise ProviderNotReadyError(
            user_message="Multiple providers are available but no provider was selected.",
            suggested_action=(
                "Pass '--provider claude' or '--provider codex', or set a global "
                "preference with 'scc provider set <provider>'."
            ),
        )

    if prompt_choice is None:
        raise ProviderNotReadyError(
            user_message="Provider selection requires an interactive prompt.",
            suggested_action="Re-run this start in an interactive terminal.",
        )

    return prompt_choice(
        candidates,
        connected_allowed,
        _resolve_prompt_default(
            candidates=candidates,
            connected_allowed=connected_allowed,
            workspace_last_used=workspace_last_used,
            config_provider=config_provider,
        ),
    )


def collect_provider_readiness(
    adapters: Any,
    *,
    allowed_providers: tuple[str, ...] = (),
) -> dict[str, AuthReadiness]:
    """Return provider auth readiness for all allowed providers."""
    candidates = allowed_providers or KNOWN_PROVIDERS
    result: dict[str, AuthReadiness] = {}
    for provider_id in candidates:
        adapter = get_agent_provider(adapters, provider_id)
        if adapter is None:
            continue
        result[provider_id] = adapter.auth_check()
    return result


def connected_provider_ids(
    adapters: Any,
    *,
    allowed_providers: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Return the allowed providers whose auth cache is already present."""
    readiness = collect_provider_readiness(adapters, allowed_providers=allowed_providers)
    return tuple(
        provider_id for provider_id, state in readiness.items() if state.status == "present"
    )


def prompt_for_provider_choice(
    allowed_provider_ids: tuple[str, ...],
    connected_provider_ids: tuple[str, ...],
    default_provider_id: str | None,
) -> str | None:
    """Prompt the operator to choose a provider for this start."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="yellow", no_wrap=True)
    table.add_column(style="white", no_wrap=True)
    table.add_column(style="dim")

    default_choice = "1"
    for index, provider_id in enumerate(allowed_provider_ids, start=1):
        if default_provider_id == provider_id:
            default_choice = str(index)
        elif provider_id in connected_provider_ids and default_choice == "1":
            default_choice = str(index)
        status = "auth cache present" if provider_id in connected_provider_ids else "sign-in needed"
        table.add_row(
            f"[{index}]",
            get_provider_display_name(provider_id),
            status,
        )
    table.add_row("[0]", "Cancel", "Exit without starting")

    subtitle = (
        "No provider preference was resolved automatically. "
        "Choose which coding agent to launch for this workspace."
    )
    console.print()
    print_with_layout(
        console,
        Panel(
            table,
            title="[bold cyan]Choose Provider[/bold cyan]",
            subtitle=subtitle,
            border_style="bright_black",
            padding=(0, 1),
        ),
        constrain=True,
    )
    console.print()

    choice = prompt_with_layout(
        console,
        "[cyan]Select provider[/cyan]",
        choices=["0", *[str(i) for i in range(1, len(allowed_provider_ids) + 1)]],
        default=default_choice,
    )
    if choice == "0":
        return None
    return allowed_provider_ids[int(choice) - 1]


def _resolve_prompt_default(
    *,
    candidates: tuple[str, ...],
    connected_allowed: tuple[str, ...],
    workspace_last_used: str | None,
    config_provider: str | None,
) -> str | None:
    """Return the best default selection for an interactive provider chooser."""
    if workspace_last_used in connected_allowed and workspace_last_used in candidates:
        return workspace_last_used
    if config_provider in connected_allowed and config_provider in candidates:
        return config_provider
    return None
