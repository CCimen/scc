"""
First-run setup wizard for SCC - Sandboxed Claude CLI.

Provides a minimal, user-friendly onboarding experience:
- Prerequisite validation
- Workspace configuration
- Team profile selection (optional)
- Status line configuration (optional)

Philosophy: "Get started in under 60 seconds"
- Minimal questions
- Smart defaults
- Clear guidance
"""

import importlib.resources
import json
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from . import config, doctor
from . import platform as platform_module

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


WELCOME_BANNER_SIMPLE = """
[cyan]┌─────────────────────────────────────────────────────────┐[/cyan]
[cyan]│[/cyan]  [bold white]Welcome to SCC - Sandboxed Claude CLI[/bold white]               [cyan]│[/cyan]
[cyan]│[/cyan]  [dim]Safe development environment for AI-assisted coding[/dim]  [cyan]│[/cyan]
[cyan]└─────────────────────────────────────────────────────────┘[/cyan]
"""


def show_welcome(console: Console) -> None:
    """Display the welcome banner."""
    console.print()
    if platform_module.is_wide_terminal(90):
        console.print(WELCOME_BANNER)
    else:
        console.print(WELCOME_BANNER_SIMPLE)


# ═══════════════════════════════════════════════════════════════════════════════
# Setup Steps
# ═══════════════════════════════════════════════════════════════════════════════


def check_prerequisites(console: Console) -> bool:
    """
    Run prerequisite checks and display results.

    Returns True if all critical prerequisites pass.
    """
    console.print("[bold cyan]Checking prerequisites...[/bold cyan]")
    console.print()

    result = doctor.run_doctor()
    doctor.render_doctor_results(console, result)

    return result.all_ok


def prompt_workspace_base(console: Console) -> Path:
    """
    Prompt user for workspace base directory.

    Returns the selected or default workspace path.
    """
    default_path = platform_module.get_recommended_workspace_base()

    console.print()
    console.print("[bold cyan]Where do you keep your projects?[/bold cyan]")
    console.print()

    # Show platform-specific recommendation
    if platform_module.is_wsl2():
        console.print(
            "[dim]Tip: For best performance in WSL2, keep projects inside the Linux filesystem.[/dim]"
        )
        console.print()

    # Prompt with default
    path_str = Prompt.ask(
        "  [cyan]Projects directory[/cyan]",
        default=str(default_path),
    )

    workspace_path = Path(path_str).expanduser().resolve()

    # Create if doesn't exist
    if not workspace_path.exists():
        console.print()
        if Confirm.ask(
            "  [yellow]Directory doesn't exist. Create it?[/yellow]",
            default=True,
        ):
            workspace_path.mkdir(parents=True, exist_ok=True)
            console.print(f"  [green]  Created {workspace_path}[/green]")
        else:
            console.print("  [dim]Using path anyway (will create on first use)[/dim]")

    return workspace_path


def prompt_team_selection(console: Console) -> str | None:
    """
    Prompt user to select a team profile (optional).

    Returns the selected team name or None for base profile.
    """
    console.print()
    console.print("[bold cyan]Select your team (optional)[/bold cyan]")
    console.print()
    console.print("[dim]Team profiles provide pre-configured settings for your stack.[/dim]")
    console.print()

    # Get available teams from config
    teams_config = config.load_teams_config()
    profiles = teams_config.get("profiles", {})

    if not profiles:
        console.print("[dim]No team profiles configured. Using base settings.[/dim]")
        return None

    # Build selection table
    table = Table(
        box=box.SIMPLE,
        show_header=False,
        padding=(0, 2),
        border_style="dim",
    )
    table.add_column("Option", style="yellow", width=4)
    table.add_column("Team", style="cyan", min_width=15)
    table.add_column("Description", style="dim")

    # Filter out "base" from profiles list since it's always shown as [0] option
    team_list = [name for name in profiles.keys() if name.lower() != "base"]

    for i, team_name in enumerate(team_list, 1):
        team_info = profiles[team_name]
        desc = team_info.get("description", "")
        table.add_row(f"[{i}]", team_name, desc)

    table.add_row("[0]", "base", "No team-specific settings")

    console.print(table)
    console.print()

    # Get selection
    valid_choices = [str(i) for i in range(0, len(team_list) + 1)]
    choice_str = Prompt.ask(
        "  [cyan]Select team[/cyan]",
        default="0",
        choices=valid_choices,
    )
    choice = int(choice_str)

    if choice == 0:
        return None

    return team_list[choice - 1]


def install_statusline(console: Console) -> bool:
    """
    Install the SCC status line into Docker sandbox volume.

    SCC philosophy: Everything stays in Docker, not on host.
    Returns True if installation successful.
    """
    from . import docker

    # Get the status line script from package resources
    try:
        template_files = importlib.resources.files("scc_cli.templates")
        script_content = (template_files / "statusline.sh").read_text()
    except (FileNotFoundError, TypeError):
        # Fallback: read from relative path during development
        dev_path = Path(__file__).parent / "templates" / "statusline.sh"
        if dev_path.exists():
            script_content = dev_path.read_text()
        else:
            console.print("  [dim]Could not find statusline template, skipping.[/dim]")
            return False

    # Inject script into Docker volume (will be at /mnt/claude-data/scc-statusline.sh)
    script_ok = docker.inject_file_to_sandbox_volume("scc-statusline.sh", script_content)

    # Get existing settings from Docker volume (if any)
    existing_settings = docker.get_sandbox_settings() or {}

    # Add statusline config (path inside container)
    existing_settings["statusLine"] = {
        "type": "command",
        "command": "/mnt/claude-data/scc-statusline.sh",
        "padding": 0,
    }

    # Inject settings into Docker volume
    settings_ok = docker.inject_file_to_sandbox_volume(
        "settings.json", json.dumps(existing_settings, indent=2)
    )

    return script_ok and settings_ok


def prompt_statusline_setup(console: Console) -> bool:
    """
    Prompt user to install the SCC status line.

    Returns True if status line was installed.
    """
    console.print()
    console.print("[bold cyan]Status line configuration (optional)[/bold cyan]")
    console.print()
    console.print("[dim]The status line shows useful info in Claude Code:[/dim]")
    console.print(
        "  [dim]→ [bold]Model[/bold] | [cyan]🌿 branch[/cyan] or "
        "[magenta]⎇ worktree[/magenta]:branch | [green]Ctx %[/green] | "
        "[yellow]$cost[/yellow][/dim]"
    )
    console.print()

    if Confirm.ask(
        "  [cyan]Install the SCC status line?[/cyan]",
        default=True,
    ):
        if install_statusline(console):
            console.print("  [green]✓ Status line installed[/green]")
            return True
        else:
            console.print("  [yellow]! Could not install status line[/yellow]")
            return False

    console.print("  [dim]Skipped. Run 'scc statusline --install' later if needed.[/dim]")
    return False


def save_configuration(
    console: Console,
    workspace_base: Path,
    default_team: str | None = None,
) -> None:
    """
    Save the setup configuration.

    Creates config directory and saves user preferences.
    """
    console.print()
    console.print("[bold cyan]Saving configuration...[/bold cyan]")

    # Ensure config directory exists
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Build configuration
    user_config = {
        "workspace_base": str(workspace_base),
        "default_team": default_team,
        "setup_completed": True,
        "version": "1.0",
    }

    # Save to config file
    config.save_user_config(user_config)

    console.print(f"  [green]  Configuration saved to {config.CONFIG_FILE}[/green]")


def show_completion(
    console: Console,
    workspace_base: Path,
    team: str | None,
    statusline_installed: bool = False,
) -> None:
    """
    Display setup completion message with next steps.
    """
    console.print()

    # Build completion info
    info_lines = []
    info_lines.append(f"[cyan]Workspace:[/cyan] {workspace_base}")
    info_lines.append(f"[cyan]Team:[/cyan] {team or 'base'}")
    info_lines.append(f"[cyan]Config:[/cyan] {config.CONFIG_DIR}")
    if statusline_installed:
        info_lines.append("[cyan]Status line:[/cyan] [green]Enabled[/green]")

    # Create panel
    panel = Panel(
        "\n".join(info_lines),
        title="[bold green]  Setup Complete[/bold green]",
        border_style="green",
        padding=(1, 2),
    )
    console.print(panel)

    # Next steps
    console.print()
    console.print("[bold white]Next steps:[/bold white]")
    console.print()
    console.print("  [cyan]scc[/cyan]                  [dim]Start Claude Code interactively[/dim]")
    console.print("  [cyan]scc -w ~/project[/cyan]    [dim]Start with specific workspace[/dim]")
    console.print("  [cyan]scc doctor[/cyan]          [dim]Check system health anytime[/dim]")
    console.print("  [cyan]scc --help[/cyan]          [dim]See all available commands[/dim]")
    console.print()


# ═══════════════════════════════════════════════════════════════════════════════
# Main Setup Flow
# ═══════════════════════════════════════════════════════════════════════════════


def run_setup(console: Console, skip_prereqs: bool = False) -> bool:
    """
    Run the complete first-run setup wizard.

    Args:
        console: Rich console for output
        skip_prereqs: Skip prerequisite checks (for testing)

    Returns:
        True if setup completed successfully
    """
    # Welcome
    show_welcome(console)

    # Prerequisites
    if not skip_prereqs:
        if not check_prerequisites(console):
            console.print()
            console.print(
                "[yellow]  Setup paused. Please fix the issues above and run [bold]scc[/bold] again.[/yellow]"
            )
            console.print()
            return False

    # Workspace selection
    workspace_base = prompt_workspace_base(console)

    # Team selection (optional)
    team = prompt_team_selection(console)

    # Status line setup (optional)
    statusline_installed = prompt_statusline_setup(console)

    # Save configuration
    save_configuration(console, workspace_base, team)

    # Show completion
    show_completion(console, workspace_base, team, statusline_installed)

    return True


def run_quick_setup(console: Console, workspace_base: Path | None = None) -> bool:
    """
    Run minimal setup with defaults.

    Used when user wants to skip interactive prompts.
    Includes status line installation by default.
    """
    console.print("[bold cyan]Running quick setup with defaults...[/bold cyan]")
    console.print()

    # Use default workspace if not provided
    if workspace_base is None:
        workspace_base = platform_module.get_recommended_workspace_base()

    # Ensure workspace exists
    workspace_base.mkdir(parents=True, exist_ok=True)

    # Install status line by default (part of smart defaults)
    statusline_ok = install_statusline(console)

    # Save minimal configuration
    save_configuration(console, workspace_base, default_team=None)

    console.print(f"  [green]✓ Workspace: {workspace_base}[/green]")
    console.print(f"  [green]✓ Config: {config.CONFIG_DIR}[/green]")
    if statusline_ok:
        console.print("  [green]✓ Status line: Enabled[/green]")
    console.print()
    console.print("[dim]Run [bold]scc[/bold] to start Claude Code.[/dim]")
    console.print()

    return True


# ═══════════════════════════════════════════════════════════════════════════════
# Setup Detection
# ═══════════════════════════════════════════════════════════════════════════════


def is_setup_needed() -> bool:
    """
    Check if first-run setup is needed.

    Returns True if:
    - Config directory doesn't exist
    - Config file doesn't exist
    - setup_completed flag is False
    """
    if not config.CONFIG_DIR.exists():
        return True

    if not config.CONFIG_FILE.exists():
        return True

    # Check setup_completed flag
    user_config = config.load_user_config()
    return not user_config.get("setup_completed", False)


def maybe_run_setup(console: Console) -> bool:
    """
    Run setup if needed, otherwise return True.

    Call this at the start of commands that require configuration.
    Returns True if ready to proceed, False if setup failed.
    """
    if not is_setup_needed():
        return True

    console.print()
    console.print("[dim]First-time setup detected. Let's get you started![/dim]")
    console.print()

    return run_setup(console)


# ═══════════════════════════════════════════════════════════════════════════════
# Configuration Reset
# ═══════════════════════════════════════════════════════════════════════════════


def reset_setup(console: Console) -> None:
    """
    Reset setup configuration to defaults.

    Used when user wants to reconfigure.
    """
    console.print()
    console.print("[bold yellow]Resetting configuration...[/bold yellow]")

    if config.CONFIG_FILE.exists():
        config.CONFIG_FILE.unlink()
        console.print(f"  [dim]Removed {config.CONFIG_FILE}[/dim]")

    console.print()
    console.print("[green]  Configuration reset.[/green] Run [bold]scc[/bold] to set up again.")
    console.print()
