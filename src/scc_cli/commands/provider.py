"""Provider management commands for SCC CLI."""

from __future__ import annotations

import typer

from .. import config
from ..cli_common import console, handle_errors
from ..core.provider_resolution import KNOWN_PROVIDERS

provider_app = typer.Typer(
    name="provider",
    help="Manage agent provider selection.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


@provider_app.command("show")
@handle_errors
def show() -> None:
    """Show the currently selected agent provider."""
    provider = config.get_selected_provider() or "ask"
    console.print(provider)


@provider_app.command("set")
@handle_errors
def set_provider(
    provider: str = typer.Argument(..., help="Provider to set (claude, codex, or ask)"),
) -> None:
    """Set the global provider preference."""
    if provider == "ask":
        config.set_selected_provider("ask")
        console.print("Provider preference set to [bold]ask[/bold]")
        return

    if provider not in KNOWN_PROVIDERS:
        console.print(
            f"[red]Error:[/red] Unknown provider '{provider}'. "
            f"Known providers: {', '.join(KNOWN_PROVIDERS)}, ask",
            highlight=False,
        )
        raise typer.Exit(2)
    config.set_selected_provider(provider)
    console.print(f"Provider preference set to [bold]{provider}[/bold]")
