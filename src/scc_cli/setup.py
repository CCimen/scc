"""
Setup wizard for SCC - Sandboxed Claude CLI.

Remote organization config workflow:
- Prompt for org config URL (or standalone mode)
- Handle authentication (env:VAR, command:CMD)
- Team/profile selection from remote config
- Git hooks enablement option

Philosophy: "Get started in under 60 seconds"
- Minimal questions
- Smart defaults
- Clear guidance
"""

from typing import Any, cast

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from . import config
from .remote import fetch_org_config

# ═══════════════════════════════════════════════════════════════════════════════
# Welcome Screen
# ═══════════════════════════════════════════════════════════════════════════════


WELCOME_BANNER = """
[cyan]╔═══════════════════════════════════════════════════════════╗[/cyan]
[cyan]║[/cyan]                                                           [cyan]║[/cyan]
[cyan]║[/cyan]   [bold white]Welcome to SCC - Sandboxed Claude CLI[/bold white]                [cyan]║[/cyan]
[cyan]║[/cyan]                                                           [cyan]║[/cyan]
[cyan]║[/cyan]   [dim]Safe development environment for AI-assisted coding[/dim]   [cyan]║[/cyan]
[cyan]║[/cyan]                                                           [cyan]║[/cyan]
[cyan]╚═══════════════════════════════════════════════════════════╝[/cyan]
"""


def show_welcome(console: Console) -> None:
    """Display the welcome banner on the console."""
    console.print()
    console.print(WELCOME_BANNER)


# ═══════════════════════════════════════════════════════════════════════════════
# Organization Config URL
# ═══════════════════════════════════════════════════════════════════════════════


def prompt_has_org_config(console: Console) -> bool:
    """Prompt the user to confirm if they have an organization config URL.

    Returns:
        True if user has org config URL, False for standalone mode.
    """
    console.print()
    return Confirm.ask(
        "[cyan]Do you have an organization config URL?[/cyan]",
        default=True,
    )


def prompt_org_url(console: Console) -> str:
    """Prompt the user to enter the organization config URL.

    Validate that URL is HTTPS. Reject HTTP URLs.

    Returns:
        Valid HTTPS URL string.
    """
    console.print()
    console.print("[dim]Enter your organization config URL (HTTPS only)[/dim]")
    console.print()

    while True:
        url = Prompt.ask("[cyan]Organization config URL[/cyan]")

        # Validate HTTPS
        if url.startswith("http://"):
            console.print("[red]✗ HTTP URLs are not allowed. Please use HTTPS.[/red]")
            continue

        if not url.startswith("https://"):
            console.print("[red]✗ URL must start with https://[/red]")
            continue

        return url


# ═══════════════════════════════════════════════════════════════════════════════
# Authentication
# ═══════════════════════════════════════════════════════════════════════════════


def prompt_auth_method(console: Console) -> str | None:
    """Prompt the user to select an authentication method.

    Options:
    1. Environment variable (env:VAR)
    2. Command (command:CMD)
    3. Skip (no auth)

    Returns:
        Auth spec string (env:VAR or command:CMD) or None to skip.
    """
    console.print()
    console.print("[bold cyan]Authentication required[/bold cyan]")
    console.print()
    console.print("[dim]How would you like to provide authentication?[/dim]")
    console.print()
    console.print("  [yellow][1][/yellow] Environment variable (env:VAR_NAME)")
    console.print("  [yellow][2][/yellow] Command (command:your-command)")
    console.print("  [yellow][3][/yellow] Skip authentication")
    console.print()

    choice = Prompt.ask(
        "[cyan]Select option[/cyan]",
        choices=["1", "2", "3"],
        default="1",
    )

    if choice == "1":
        var_name = Prompt.ask("[cyan]Environment variable name[/cyan]")
        return f"env:{var_name}"

    if choice == "2":
        command = Prompt.ask("[cyan]Command to run[/cyan]")
        return f"command:{command}"

    # Choice 3: Skip
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Remote Config Fetching
# ═══════════════════════════════════════════════════════════════════════════════


def fetch_and_validate_org_config(
    console: Console, url: str, auth: str | None
) -> dict[str, Any] | None:
    """Fetch and validate the organization config from a URL.

    Args:
        console: Rich console for output
        url: HTTPS URL to org config
        auth: Auth spec (env:VAR, command:CMD) or None

    Returns:
        Organization config dict if successful, None if auth required (401).
    """
    console.print()
    console.print("[dim]Fetching organization config...[/dim]")

    config_data, etag, status = fetch_org_config(url, auth=auth, etag=None)

    if status == 401:
        console.print("[yellow]⚠️ Authentication required (401)[/yellow]")
        return None

    if status == 403:
        console.print("[red]✗ Access denied (403)[/red]")
        return None

    if status != 200 or config_data is None:
        console.print(f"[red]✗ Failed to fetch config (status: {status})[/red]")
        return None

    org_name = config_data.get("organization", {}).get("name", "Unknown")
    console.print(f"[green]✓ Connected to: {org_name}[/green]")

    return config_data


# ═══════════════════════════════════════════════════════════════════════════════
# Profile Selection
# ═══════════════════════════════════════════════════════════════════════════════


def prompt_profile_selection(console: Console, org_config: dict[str, Any]) -> str | None:
    """Prompt the user to select a profile from the org config.

    Args:
        console: Rich console for output
        org_config: Organization config with profiles

    Returns:
        Selected profile name or None for no profile.
    """
    profiles = org_config.get("profiles", {})

    if not profiles:
        console.print("[dim]No profiles configured.[/dim]")
        return None

    console.print()
    console.print("[bold cyan]Select your team profile[/bold cyan]")
    console.print()

    # Build selection table
    table = Table(
        box=box.SIMPLE,
        show_header=False,
        padding=(0, 2),
        border_style="dim",
    )
    table.add_column("Option", style="yellow", width=4)
    table.add_column("Profile", style="cyan", min_width=15)
    table.add_column("Description", style="dim")

    profile_list = list(profiles.keys())

    for i, profile_name in enumerate(profile_list, 1):
        profile_info = profiles[profile_name]
        desc = profile_info.get("description", "")
        table.add_row(f"[{i}]", profile_name, desc)

    table.add_row("[0]", "none", "No profile")

    console.print(table)
    console.print()

    # Get selection
    valid_choices = [str(i) for i in range(0, len(profile_list) + 1)]
    choice_str = Prompt.ask(
        "[cyan]Select profile[/cyan]",
        default="0" if not profile_list else "1",
        choices=valid_choices,
    )
    choice = int(choice_str)

    if choice == 0:
        return None

    return cast(str, profile_list[choice - 1])


# ═══════════════════════════════════════════════════════════════════════════════
# Hooks Configuration
# ═══════════════════════════════════════════════════════════════════════════════


def prompt_hooks_enablement(console: Console) -> bool:
    """Prompt the user about git hooks installation.

    Returns:
        True if hooks should be enabled, False otherwise.
    """
    console.print()
    console.print("[bold cyan]Git Hooks Protection[/bold cyan]")
    console.print()
    console.print("[dim]Install repo-local hooks to block pushes to protected branches?[/dim]")
    console.print("[dim](main, master, develop, production, staging)[/dim]")
    console.print()

    return Confirm.ask(
        "[cyan]Enable git hooks protection?[/cyan]",
        default=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Save Configuration
# ═══════════════════════════════════════════════════════════════════════════════


def save_setup_config(
    console: Console,
    org_url: str | None,
    auth: str | None,
    profile: str | None,
    hooks_enabled: bool,
    standalone: bool = False,
) -> None:
    """Save the setup configuration to the user config file.

    Args:
        console: Rich console for output
        org_url: Organization config URL or None
        auth: Auth spec or None
        profile: Selected profile name or None
        hooks_enabled: Whether git hooks are enabled
        standalone: Whether running in standalone mode
    """
    console.print()
    console.print("[dim]Saving configuration...[/dim]")

    # Ensure config directory exists
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Build configuration
    user_config: dict[str, Any] = {
        "config_version": "1.0.0",
        "hooks": {"enabled": hooks_enabled},
    }

    if standalone:
        user_config["standalone"] = True
        user_config["organization_source"] = None
    elif org_url:
        user_config["organization_source"] = {
            "url": org_url,
            "auth": auth,
        }
        user_config["selected_profile"] = profile

    # Save to config file
    config.save_user_config(user_config)

    console.print(f"[green]✓ Configuration saved to {config.CONFIG_FILE}[/green]")


# ═══════════════════════════════════════════════════════════════════════════════
# Setup Complete Display
# ═══════════════════════════════════════════════════════════════════════════════


def show_setup_complete(
    console: Console,
    org_name: str | None = None,
    profile: str | None = None,
    standalone: bool = False,
) -> None:
    """Display the setup completion message.

    Args:
        console: Rich console for output
        org_name: Organization name (if connected)
        profile: Selected profile name
        standalone: Whether in standalone mode
    """
    console.print()

    # Build completion info
    info_lines = []
    if standalone:
        info_lines.append("[cyan]Mode:[/cyan] Standalone (no organization)")
    elif org_name:
        info_lines.append(f"[cyan]Organization:[/cyan] {org_name}")
        info_lines.append(f"[cyan]Profile:[/cyan] {profile or 'none'}")

    info_lines.append(f"[cyan]Config:[/cyan] {config.CONFIG_DIR}")

    # Create panel
    panel = Panel(
        "\n".join(info_lines),
        title="[bold green]✓ Setup Complete[/bold green]",
        border_style="green",
        padding=(1, 2),
    )
    console.print(panel)

    # Next steps
    console.print()
    console.print("[bold white]Get started:[/bold white]")
    console.print()
    console.print("  [cyan]scc start ~/project[/cyan]     [dim]Start Claude Code[/dim]")
    console.print("  [cyan]scc team list[/cyan]          [dim]List available teams[/dim]")
    console.print("  [cyan]scc doctor[/cyan]              [dim]Check system health[/dim]")
    console.print()


# ═══════════════════════════════════════════════════════════════════════════════
# Main Setup Wizard
# ═══════════════════════════════════════════════════════════════════════════════


def run_setup_wizard(console: Console) -> bool:
    """Run the interactive setup wizard.

    Flow:
    1. Prompt if user has org config URL
    2. If yes: fetch config, handle auth, select profile
    3. If no: standalone mode
    4. Configure hooks
    5. Save config

    Returns:
        True if setup completed successfully.
    """
    # Welcome
    show_welcome(console)

    # Check for org config
    has_org_config = prompt_has_org_config(console)

    if has_org_config:
        # Get org URL
        org_url = prompt_org_url(console)

        # Try to fetch without auth first
        org_config = fetch_and_validate_org_config(console, org_url, auth=None)

        # If 401, prompt for auth and retry
        auth = None
        if org_config is None:
            auth = prompt_auth_method(console)
            if auth:
                org_config = fetch_and_validate_org_config(console, org_url, auth=auth)

        if org_config is None:
            console.print("[red]✗ Could not fetch organization config[/red]")
            return False

        # Profile selection
        profile = prompt_profile_selection(console, org_config)

        # Hooks
        hooks_enabled = prompt_hooks_enablement(console)

        # Save config
        save_setup_config(
            console,
            org_url=org_url,
            auth=auth,
            profile=profile,
            hooks_enabled=hooks_enabled,
        )

        # Complete
        org_name = org_config.get("organization", {}).get("name")
        show_setup_complete(console, org_name=org_name, profile=profile)

    else:
        # Standalone mode
        console.print()
        console.print("[dim]Setting up standalone mode (no organization config)[/dim]")

        # Hooks
        hooks_enabled = prompt_hooks_enablement(console)

        # Save config
        save_setup_config(
            console,
            org_url=None,
            auth=None,
            profile=None,
            hooks_enabled=hooks_enabled,
            standalone=True,
        )

        # Complete
        show_setup_complete(console, standalone=True)

    return True


# ═══════════════════════════════════════════════════════════════════════════════
# Non-Interactive Setup
# ═══════════════════════════════════════════════════════════════════════════════


def run_non_interactive_setup(
    console: Console,
    org_url: str | None = None,
    team: str | None = None,
    auth: str | None = None,
    standalone: bool = False,
) -> bool:
    """Run non-interactive setup using CLI arguments.

    Args:
        console: Rich console for output
        org_url: Organization config URL
        team: Team/profile name
        auth: Auth spec (env:VAR or command:CMD)
        standalone: Enable standalone mode

    Returns:
        True if setup completed successfully.
    """
    if standalone:
        # Standalone mode - no org config needed
        save_setup_config(
            console,
            org_url=None,
            auth=None,
            profile=None,
            hooks_enabled=False,
            standalone=True,
        )
        show_setup_complete(console, standalone=True)
        return True

    if not org_url:
        console.print("[red]✗ Organization URL required (use --org-url)[/red]")
        return False

    # Fetch org config
    org_config = fetch_and_validate_org_config(console, org_url, auth=auth)

    if org_config is None:
        console.print("[red]✗ Could not fetch organization config[/red]")
        return False

    # Validate team if provided
    if team:
        profiles = org_config.get("profiles", {})
        if team not in profiles:
            available = ", ".join(profiles.keys())
            console.print(f"[red]✗ Team '{team}' not found. Available: {available}[/red]")
            return False

    # Save config
    save_setup_config(
        console,
        org_url=org_url,
        auth=auth,
        profile=team,
        hooks_enabled=True,  # Default to enabled for non-interactive
    )

    org_name = org_config.get("organization", {}).get("name")
    show_setup_complete(console, org_name=org_name, profile=team)

    return True


# ═══════════════════════════════════════════════════════════════════════════════
# Setup Detection
# ═══════════════════════════════════════════════════════════════════════════════


def is_setup_needed() -> bool:
    """Check if first-run setup is needed and return the result.

    Return True if:
    - Config directory doesn't exist
    - Config file doesn't exist
    - config_version field is missing
    """
    if not config.CONFIG_DIR.exists():
        return True

    if not config.CONFIG_FILE.exists():
        return True

    # Check for config version
    user_config = config.load_user_config()
    return "config_version" not in user_config


def maybe_run_setup(console: Console) -> bool:
    """Run setup if needed, otherwise return True.

    Call at the start of commands that require configuration.
    Return True if ready to proceed, False if setup failed.
    """
    if not is_setup_needed():
        return True

    console.print()
    console.print("[dim]First-time setup detected. Let's get you started![/dim]")
    console.print()

    return run_setup_wizard(console)


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration Reset
# ═══════════════════════════════════════════════════════════════════════════════


def reset_setup(console: Console) -> None:
    """Reset setup configuration to defaults.

    Use when user wants to reconfigure.
    """
    console.print()
    console.print("[bold yellow]Resetting configuration...[/bold yellow]")

    if config.CONFIG_FILE.exists():
        config.CONFIG_FILE.unlink()
        console.print(f"  [dim]Removed {config.CONFIG_FILE}[/dim]")

    console.print()
    console.print("[green]✓ Configuration reset.[/green] Run [bold]scc setup[/bold] again.")
    console.print()
