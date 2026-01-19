"""Team configuration checks for launch flows."""

from __future__ import annotations

import typer
from rich.status import Status

from ... import config, teams
from ...cli_common import console
from ...core.exit_codes import EXIT_CONFIG
from ...panels import create_warning_panel
from ...theme import Spinners
from ...ui.chrome import print_with_layout
from .flow_types import UserConfig


def _configure_team_settings(team: str | None, cfg: UserConfig) -> None:
    """Validate team profile exists.

    NOTE: Plugin settings are now sourced ONLY from workspace settings.local.json
    (via start session preparation). Docker volume injection has been removed
    to prevent plugin mixing across teams.

    IMPORTANT: This function must remain cache-only (no network calls).
    It's called in offline mode where only cached org config is available.
    If you need to add network operations, gate them with an offline check
    or move them to start session preparation which is already offline-aware.

    Raises:
        typer.Exit: If team profile is not found.
    """
    if not team:
        return

    with Status(
        f"[cyan]Validating {team} profile...[/cyan]", console=console, spinner=Spinners.SETUP
    ):
        # load_cached_org_config() reads from local cache only - safe for offline mode
        org_config = config.load_cached_org_config()

        validation = teams.validate_team_profile(team, org_config)
        if not validation["valid"]:
            print_with_layout(
                console,
                create_warning_panel(
                    "Team Not Found",
                    f"No team profile named '{team}'.",
                    "Run 'scc team list' to see available profiles",
                ),
                constrain=True,
            )
            raise typer.Exit(EXIT_CONFIG)

        # NOTE: docker.inject_team_settings() removed - workspace settings.local.json
        # is now the single source of truth for plugins (prevents cross-team mixing)
