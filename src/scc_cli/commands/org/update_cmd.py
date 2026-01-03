"""Org update command for refreshing organization and team configs."""

from __future__ import annotations

from typing import Any

import typer

from ...cli_common import console, handle_errors
from ...config import load_user_config
from ...core.exit_codes import EXIT_CONFIG
from ...json_output import build_envelope
from ...kinds import Kind
from ...marketplace.team_fetch import fetch_team_config
from ...output_mode import json_output_mode, print_json, set_pretty_mode
from ...panels import create_error_panel, create_success_panel, create_warning_panel
from ...remote import load_org_config
from ._builders import _parse_config_source, build_update_data


@handle_errors
def org_update_cmd(
    team: str | None = typer.Option(
        None, "--team", "-t", help="Refresh a specific federated team's config"
    ),
    all_teams: bool = typer.Option(
        False, "--all-teams", "-a", help="Refresh all federated team configs"
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON (implies --json)"),
) -> None:
    """Refresh organization config and optionally team configs.

    By default, refreshes the organization config from its remote source.
    With --team or --all-teams, also refreshes federated team configurations.

    Examples:
        scc org update              # Refresh org config only
        scc org update --team dev   # Also refresh 'dev' team config
        scc org update --all-teams  # Refresh all federated team configs
    """
    # --pretty implies --json
    if pretty:
        json_output = True
        set_pretty_mode(True)

    # Load user config
    user_config = load_user_config()

    # Check for standalone mode
    is_standalone = user_config.get("standalone", False)
    if is_standalone:
        if json_output:
            with json_output_mode():
                envelope = build_envelope(
                    Kind.ORG_UPDATE,
                    data={"error": "Cannot update in standalone mode"},
                    ok=False,
                    errors=["CLI is running in standalone mode"],
                )
                print_json(envelope)
            raise typer.Exit(EXIT_CONFIG)
        console.print(
            create_error_panel(
                "Standalone Mode",
                "Cannot update organization config in standalone mode.",
                hint="Use 'scc setup' to connect to an organization.",
            )
        )
        raise typer.Exit(EXIT_CONFIG)

    # Check for organization source
    org_source = user_config.get("organization_source")
    if not org_source:
        if json_output:
            with json_output_mode():
                envelope = build_envelope(
                    Kind.ORG_UPDATE,
                    data={"error": "No organization source configured"},
                    ok=False,
                    errors=["No organization source configured"],
                )
                print_json(envelope)
            raise typer.Exit(EXIT_CONFIG)
        console.print(
            create_error_panel(
                "No Organization",
                "No organization source is configured.",
                hint="Use 'scc setup' to connect to an organization.",
            )
        )
        raise typer.Exit(EXIT_CONFIG)

    # Force refresh org config
    org_config = load_org_config(user_config, force_refresh=True)
    if org_config is None:
        if json_output:
            with json_output_mode():
                envelope = build_envelope(
                    Kind.ORG_UPDATE,
                    data=build_update_data(None),
                    ok=False,
                    errors=["Failed to fetch organization config"],
                )
                print_json(envelope)
            raise typer.Exit(EXIT_CONFIG)
        console.print(
            create_error_panel(
                "Update Failed",
                "Failed to fetch organization config from remote.",
                hint="Check network connection and organization URL.",
            )
        )
        raise typer.Exit(EXIT_CONFIG)

    # Get profiles from org config
    profiles = org_config.get("profiles", {})

    # Handle --team option (single team update)
    team_results: list[dict[str, Any]] | None = None
    if team is not None:
        # Validate team exists
        if team not in profiles:
            if json_output:
                with json_output_mode():
                    envelope = build_envelope(
                        Kind.ORG_UPDATE,
                        data=build_update_data(org_config),
                        ok=False,
                        errors=[f"Team '{team}' not found in organization config"],
                    )
                    print_json(envelope)
                raise typer.Exit(EXIT_CONFIG)
            console.print(
                create_error_panel(
                    "Team Not Found",
                    f"Team '{team}' not found in organization config.",
                    hint=f"Available teams: {', '.join(profiles.keys())}",
                )
            )
            raise typer.Exit(EXIT_CONFIG)

        profile = profiles[team]
        config_source_dict = profile.get("config_source")

        # Check if team is federated
        if config_source_dict is None:
            team_results = [{"team": team, "success": True, "inline": True}]
            if json_output:
                with json_output_mode():
                    data = build_update_data(org_config, team_results)
                    envelope = build_envelope(Kind.ORG_UPDATE, data=data)
                    print_json(envelope)
                raise typer.Exit(0)
            console.print(
                create_warning_panel(
                    "Inline Team",
                    f"Team '{team}' is not federated (inline config).",
                    hint="Inline teams don't have external configs to refresh.",
                )
            )
            raise typer.Exit(0)

        # Fetch team config
        try:
            config_source = _parse_config_source(config_source_dict)
            result = fetch_team_config(config_source, team)
            if result.success:
                team_results = [
                    {
                        "team": team,
                        "success": True,
                        "commit_sha": result.commit_sha,
                    }
                ]
            else:
                team_results = [
                    {
                        "team": team,
                        "success": False,
                        "error": result.error,
                    }
                ]
                if json_output:
                    with json_output_mode():
                        data = build_update_data(org_config, team_results)
                        envelope = build_envelope(
                            Kind.ORG_UPDATE,
                            data=data,
                            ok=False,
                            errors=[f"Failed to fetch team config: {result.error}"],
                        )
                        print_json(envelope)
                    raise typer.Exit(EXIT_CONFIG)
                console.print(
                    create_error_panel(
                        "Team Update Failed",
                        f"Failed to fetch config for team '{team}'.",
                        hint=str(result.error),
                    )
                )
                raise typer.Exit(EXIT_CONFIG)
        except Exception as e:
            if json_output:
                with json_output_mode():
                    envelope = build_envelope(
                        Kind.ORG_UPDATE,
                        data=build_update_data(org_config),
                        ok=False,
                        errors=[f"Error parsing config source: {e}"],
                    )
                    print_json(envelope)
                raise typer.Exit(EXIT_CONFIG)
            console.print(create_error_panel("Config Error", f"Error parsing config source: {e}"))
            raise typer.Exit(EXIT_CONFIG)

    # Handle --all-teams option
    elif all_teams:
        team_results = []
        federated_teams = [
            (name, profile)
            for name, profile in profiles.items()
            if profile.get("config_source") is not None
        ]

        if not federated_teams:
            team_results = []
            if json_output:
                with json_output_mode():
                    data = build_update_data(org_config, team_results)
                    envelope = build_envelope(Kind.ORG_UPDATE, data=data)
                    print_json(envelope)
                raise typer.Exit(0)
            console.print(
                create_warning_panel(
                    "No Federated Teams",
                    "No federated teams found in organization config.",
                    hint="All teams use inline configuration.",
                )
            )
            raise typer.Exit(0)

        # Fetch all federated team configs
        for team_name, profile in federated_teams:
            config_source_dict = profile["config_source"]
            try:
                config_source = _parse_config_source(config_source_dict)
                result = fetch_team_config(config_source, team_name)
                if result.success:
                    team_results.append(
                        {
                            "team": team_name,
                            "success": True,
                            "commit_sha": result.commit_sha,
                        }
                    )
                else:
                    team_results.append(
                        {
                            "team": team_name,
                            "success": False,
                            "error": result.error,
                        }
                    )
            except Exception as e:
                team_results.append(
                    {
                        "team": team_name,
                        "success": False,
                        "error": str(e),
                    }
                )

    # Build output data
    data = build_update_data(org_config, team_results)

    # JSON output
    if json_output:
        with json_output_mode():
            # Determine overall success
            has_team_failures = team_results is not None and any(
                not t.get("success") for t in team_results
            )
            envelope = build_envelope(
                Kind.ORG_UPDATE,
                data=data,
                ok=not has_team_failures,
            )
            print_json(envelope)
        raise typer.Exit(0)

    # Human-readable output
    org_data = org_config.get("organization", {})
    org_name = org_data.get("name", "Unknown")

    if team_results is None:
        # Org-only update
        console.print(
            create_success_panel(
                "Organization Updated",
                {
                    "Organization": org_name,
                    "Status": "Refreshed from remote",
                },
            )
        )
    else:
        # Team updates included
        success_count = sum(1 for t in team_results if t.get("success"))
        failed_count = len(team_results) - success_count

        if failed_count == 0:
            console.print(
                create_success_panel(
                    "Update Complete",
                    {
                        "Organization": org_name,
                        "Teams Updated": str(success_count),
                    },
                )
            )
        else:
            console.print(
                create_warning_panel(
                    "Partial Update",
                    f"Organization updated. {success_count} team(s) succeeded, {failed_count} failed.",
                )
            )

    raise typer.Exit(0)
