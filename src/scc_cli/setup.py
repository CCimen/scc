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

import sys
from typing import Any, cast

import readchar
from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table
from rich.text import Text

from . import config
from .confirm import Confirm
from .remote import fetch_org_config, save_to_cache

# ═══════════════════════════════════════════════════════════════════════════════
# Arrow-Key Selection Component
# ═══════════════════════════════════════════════════════════════════════════════


def _select_option(
    console: Console,
    options: list[tuple[str, str, str]],
    *,
    default: int = 0,
) -> int:
    """Interactive arrow-key selection for setup options.

    Args:
        console: Rich console for output.
        options: List of (label, tag, description) tuples.
        default: Default selected index.

    Returns:
        Selected index (0-based).
    """
    cursor = default

    def _render_options() -> int:
        """Render options and return line count."""
        lines = 0
        console.print()
        lines += 1

        for i, (label, tag, desc) in enumerate(options):
            if i == cursor:
                # Selected: bold with › cursor, tag right-aligned
                line = Text()
                line.append("  ")
                line.append("›", style="cyan")
                line.append(f" {label}", style="bold white")
                if tag:
                    # Right-align tag
                    padding = 30 - len(label)
                    line.append(" " * max(2, padding))
                    line.append(tag, style="cyan")
                console.print(line)
                lines += 1
                if desc:
                    console.print(f"    [dim]{desc}[/dim]")
                    lines += 1
            else:
                # Unselected: all dim
                line = Text()
                line.append("    ")
                line.append(label, style="dim")
                if tag:
                    padding = 30 - len(label)
                    line.append(" " * max(2, padding))
                    line.append(tag, style="dim")
                console.print(line)
                lines += 1
                if desc:
                    console.print(f"    [dim]{desc}[/dim]")
                    lines += 1

            # Add spacing between options
            if i < len(options) - 1:
                console.print()
                lines += 1

        # Footer hints
        console.print()
        lines += 1
        console.print("[dim]  ↑↓ select  ·  enter confirm  ·  esc cancel[/dim]")
        lines += 1
        return lines

    # Hide cursor for smoother redraws
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    try:
        lines_rendered = _render_options()

        while True:
            # Read key
            key = readchar.readkey()

            # Handle navigation
            if key in (readchar.key.UP, "k"):
                cursor = (cursor - 1) % len(options)
            elif key in (readchar.key.DOWN, "j"):
                cursor = (cursor + 1) % len(options)
            elif key in (readchar.key.ENTER, "\r", "\n"):
                return cursor
            elif key in (readchar.key.ESC, "q"):
                return default  # Return default on cancel
            else:
                continue  # Ignore other keys, don't redraw

            # Move cursor up to redraw (clear previous render)
            sys.stdout.write(f"\033[{lines_rendered}A\033[J")
            sys.stdout.flush()
            lines_rendered = _render_options()
    finally:
        # Always restore cursor visibility
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()


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
# Setup Header (TUI-style)
# ═══════════════════════════════════════════════════════════════════════════════


SETUP_STEPS = ("Mode", "Org", "Auth", "Team", "Hooks", "Confirm")


def _append_dot_leader(
    text: Text,
    label: str,
    value: str,
    *,
    width: int = 40,
    label_style: str = "dim",
    value_style: str = "white",
) -> None:
    """Append a middle-dot leader line to a Text block."""
    label = label.strip()
    value = value.strip()
    gap = width - len(label) - len(value)
    # Use middle dot · for cleaner aesthetic
    dots = "·" * max(2, gap)
    text.append(label, style=label_style)
    text.append(f" {dots} ", style="dim")
    text.append(value, style=value_style)
    text.append("\n")


def _format_preview_value(value: str | None) -> str:
    """Format preview value, using em-dash for unset."""
    if value is None or value == "":
        return "—"  # Em-dash for unset
    return value


def _build_config_preview(
    *,
    org_url: str | None,
    auth: str | None,
    profile: str | None,
    hooks_enabled: bool | None,
    standalone: bool | None,
) -> Text:
    """Build a dot-leader preview of the config that will be written."""
    preview = Text()
    preview.append(str(config.CONFIG_FILE), style="dim")
    preview.append("\n\n")

    mode_value = "standalone" if standalone else "organization"
    _append_dot_leader(preview, "mode", mode_value, value_style="cyan")

    if not standalone:
        _append_dot_leader(
            preview,
            "org.url",
            _format_preview_value(org_url),
        )
        _append_dot_leader(
            preview,
            "org.auth",
            _format_preview_value(auth),
        )
        _append_dot_leader(
            preview,
            "profile",
            _format_preview_value(profile),
        )

    if hooks_enabled is None:
        hooks_display = "unset"
    else:
        hooks_display = "true" if hooks_enabled else "false"
    _append_dot_leader(preview, "hooks.enabled", hooks_display)
    _append_dot_leader(
        preview,
        "standalone",
        "true" if standalone else "false",
    )

    return preview


def _build_proposed_config(
    *,
    org_url: str | None,
    auth: str | None,
    profile: str | None,
    hooks_enabled: bool,
    standalone: bool,
) -> dict[str, Any]:
    """Build the config dict that will be written."""
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
    return user_config


def _get_config_value(cfg: dict[str, Any], key: str) -> str | None:
    """Get a dotted-path value from config dict."""
    parts = key.split(".")
    current: Any = cfg
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    if current is None:
        return None
    return str(current)


def _build_config_changes(before: dict[str, Any], after: dict[str, Any]) -> Text:
    """Build a diff-style preview for config changes."""
    changes = Text()
    keys = [
        "organization_source.url",
        "organization_source.auth",
        "selected_profile",
        "hooks.enabled",
        "standalone",
    ]

    any_changes = False
    for key in keys:
        old = _get_config_value(before, key)
        new = _get_config_value(after, key)
        if old != new:
            any_changes = True
            changes.append(f"{key}\n", style="bold")
            changes.append(f"  - {old or 'unset'}\n", style="red")
            changes.append(f"  + {new or 'unset'}\n\n", style="green")

    if not any_changes:
        changes.append("No changes detected.\n", style="dim")
    return changes


def _render_setup_header(console: Console, *, step_index: int, subtitle: str | None = None) -> None:
    """Render the setup step header with pill-style tabs."""
    console.clear()

    # Title
    console.print()
    console.print("                    [bold white]SCC Setup[/bold white]")
    console.print()

    # Pill-style tabs with inverse for active (no brackets)
    tabs = Text()
    tabs.append("   ")
    for idx, step in enumerate(SETUP_STEPS):
        if idx == step_index:
            # Active tab: inverse background (space padding for pill effect)
            tabs.append(f" {step} ", style="black on cyan")
        elif idx < step_index:
            # Completed: green
            tabs.append(step, style="green")
        else:
            # Future: dim
            tabs.append(step, style="dim")
        tabs.append("   ")

    console.print(tabs)
    console.print("━" * min(console.size.width, 72), style="dim")
    console.print()

    if subtitle:
        console.print(f"  {subtitle}", style="dim")
        console.print()


def _render_setup_layout(
    console: Console,
    *,
    step_index: int,
    subtitle: str | None,
    left_title: str,
    left_body: "Text | Table",
    right_title: str,
    right_body: "Text | Table",
    footer_hint: str | None = None,
) -> None:
    """Render a two-pane setup layout with a shared header."""
    _render_setup_header(console, step_index=step_index, subtitle=subtitle)

    # Use rounded box for softer aesthetic
    left_panel = Panel.fit(
        left_body,
        title=left_title,
        border_style="cyan",
        padding=(1, 2),
        box=box.ROUNDED,
    )
    right_panel = Panel.fit(
        right_body,
        title=right_title,
        border_style="blue",
        padding=(1, 2),
        box=box.ROUNDED,
    )

    width = console.size.width
    if width < 100:
        console.print(left_panel)
        console.print()
        console.print(right_panel)
    else:
        console.print(Columns([left_panel, right_panel], expand=True, equal=True))

    # Consistent footer hint bar with middot separators
    console.print()
    console.print("─" * min(console.size.width, 72), style="dim")
    console.print("  [dim]↑↓ select  ·  enter confirm  ·  esc cancel[/dim]")


# ═══════════════════════════════════════════════════════════════════════════════
# Organization Config URL
# ═══════════════════════════════════════════════════════════════════════════════


def prompt_has_org_config(console: Console, *, rendered: bool = False) -> bool:
    """Prompt the user to confirm if they have an organization config URL.

    Returns:
        True if user has org config URL, False for standalone mode.
    """
    if not rendered:
        console.print()
    choice = Prompt.ask(
        "[cyan]Select mode[/cyan]",
        choices=["1", "2"],
        default="1",
    )
    return choice == "1"


def prompt_org_url(console: Console, *, rendered: bool = False) -> str:
    """Prompt the user to enter the organization config URL.

    Validate that URL is HTTPS. Reject HTTP URLs.

    Returns:
        Valid HTTPS URL string.
    """
    if not rendered:
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


def prompt_auth_method(console: Console, *, rendered: bool = False) -> str | None:
    """Prompt the user to select an authentication method.

    Options:
    1. Environment variable (env:VAR)
    2. Command (command:CMD)
    3. Skip (no auth)

    Returns:
        Auth spec string (env:VAR or command:CMD) or None to skip.
    """
    if not rendered:
        console.print()
        console.print("[bold cyan]Authentication for org config[/bold cyan]")
        console.print()
        console.print("[dim]This is only used to fetch your organization config URL.[/dim]")
        console.print("[dim]If your config is private, SCC needs a token to download it.[/dim]")
        console.print("[dim]This does not affect Claude auth inside the container.[/dim]")
        console.print()
        console.print("[dim]How would you like to provide the token?[/dim]")
        console.print()
        console.print("  [yellow][1][/yellow] Environment variable (env:VAR_NAME)")
        console.print("      [dim]Example: env:SCC_ORG_TOKEN[/dim]")
        console.print("  [yellow][2][/yellow] Command (command:your-command)")
        console.print("      [dim]Example: command:op read --password scc/token[/dim]")
        console.print("  [yellow][3][/yellow] Skip authentication (public URL)")
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

    # Save org config to cache so team commands can access it
    # Use default TTL of 24 hours (can be overridden in config defaults)
    ttl_hours = config_data.get("defaults", {}).get("cache_ttl_hours", 24)
    save_to_cache(config_data, source_url=url, etag=etag, ttl_hours=ttl_hours)
    console.print("[dim]Organization config cached locally[/dim]")

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

    table, profile_list = build_profile_table(profiles)

    if not profile_list:
        console.print("[dim]No profiles configured.[/dim]")
        return None

    console.print()
    console.print("[bold cyan]Select your team profile[/bold cyan]")
    console.print()
    console.print(table)
    console.print()

    return prompt_profile_choice(console, profile_list)


def build_profile_table(profiles: dict[str, Any]) -> tuple[Table, list[str]]:
    """Build the profile selection table and return it with profile list."""
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
    return table, profile_list


def prompt_profile_choice(console: Console, profile_list: list[str]) -> str | None:
    """Prompt user to choose a profile from a list."""
    if not profile_list:
        return None
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


def prompt_hooks_enablement(console: Console, *, rendered: bool = False) -> bool:
    """Prompt the user about git hooks installation.

    Returns:
        True if hooks should be enabled, False otherwise.
    """
    if not rendered:
        console.print()
        console.print("[bold cyan]Git Hooks Protection[/bold cyan]")
        console.print()
        console.print("[dim]SCC can install a local pre-push hook that blocks direct pushes[/dim]")
        console.print(
            "[dim]to protected branches (main, master, develop, production, staging).[/dim]"
        )
        console.print("[dim]Hooks run inside the container too (unless --no-verify is used).[/dim]")
        console.print(
            "[dim]You can disable or remove it later; SCC only touches its own hook.[/dim]"
        )
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
    # Clear screen for clean completion display
    console.clear()
    console.print()
    console.print("                    [bold green]✓ Setup Complete[/bold green]")
    console.print()

    # Build content
    content = Text()

    if standalone:
        content.append("  Mode", style="dim")
        content.append(" ··········· ", style="dim")
        content.append("Standalone\n", style="white")
    elif org_name:
        content.append("  Organization", style="dim")
        content.append(" ·· ", style="dim")
        content.append(f"{org_name}\n", style="white")
        content.append("  Profile", style="dim")
        content.append(" ········ ", style="dim")
        content.append(f"{profile or 'none'}\n", style="white")

    content.append("  Config", style="dim")
    content.append(" ········· ", style="dim")
    content.append(f"{config.CONFIG_DIR}\n", style="cyan")

    # Main panel
    main_panel = Panel(
        content,
        border_style="bright_black",
        box=box.ROUNDED,
        padding=(1, 2),
        width=min(55, console.size.width - 4),
    )
    console.print(main_panel)

    # Next steps
    console.print()
    console.print("  [bold white]Get started[/bold white]")
    console.print()
    console.print("  [cyan]scc start ~/project[/cyan]   [dim]Launch Claude in a workspace[/dim]")
    console.print("  [cyan]scc team list[/cyan]         [dim]List available teams[/dim]")
    console.print("  [cyan]scc doctor[/cyan]            [dim]Check system health[/dim]")
    console.print()


def _build_setup_summary(
    *,
    org_url: str | None,
    auth: str | None,
    profile: str | None,
    hooks_enabled: bool,
    standalone: bool,
    org_name: str | None = None,
) -> Text:
    """Build a summary text block for setup confirmation."""
    summary = Text()

    def _line(label: str, value: str) -> None:
        summary.append(f"{label}: ", style="cyan")
        summary.append(value, style="white")
        summary.append("\n")

    if standalone:
        _line("Mode", "Standalone")
    else:
        _line("Mode", "Organization")
        if org_name:
            _line("Organization", org_name)
        if org_url:
            _line("Org URL", org_url)
        _line("Profile", profile or "none")
        _line("Auth", auth or "none")

    _line("Hooks", "enabled" if hooks_enabled else "disabled")
    _line("Config dir", str(config.CONFIG_DIR))
    return summary


def _confirm_setup(
    console: Console,
    *,
    org_url: str | None,
    auth: str | None,
    profile: str | None,
    hooks_enabled: bool,
    standalone: bool,
    org_name: str | None = None,
    rendered: bool = False,
) -> bool:
    """Show a configuration summary and ask for confirmation."""
    summary = _build_setup_summary(
        org_url=org_url,
        auth=auth,
        profile=profile,
        hooks_enabled=hooks_enabled,
        standalone=standalone,
        org_name=org_name,
    )

    if not rendered:
        panel = Panel(
            summary,
            title="[bold cyan]Review & Confirm[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
        console.print(panel)
        console.print()

    return Confirm.ask("[cyan]Apply these settings?[/cyan]", default=True)


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
    org_url = None
    auth = None
    profile = None
    hooks_enabled = None

    # Step 1: Mode selection with arrow-key navigation
    _render_setup_header(console, step_index=0, subtitle="Choose how SCC should run.")

    # Arrow-key selection
    mode_options = [
        ("Organization mode", "recommended", "Use org config URL and team profiles"),
        ("Standalone mode", "basic", "Run without a team or org config"),
    ]

    selected = _select_option(console, mode_options, default=0)
    has_org_config = selected == 0

    if has_org_config:
        # Get org URL - single centered panel
        _render_setup_header(console, step_index=1, subtitle="Enter your organization config URL.")

        org_help = Text()
        org_help.append("Your platform team provides this URL.\n\n", style="dim")
        org_help.append("  • Must be HTTPS\n", style="dim")
        org_help.append("  • Points to your org-config.json\n", style="dim")
        org_help.append("  • Example: ", style="dim")
        org_help.append("https://example.com/scc/org.json", style="cyan dim")

        org_panel = Panel(
            org_help,
            title="[bold]Organization URL[/bold]",
            border_style="bright_black",
            box=box.ROUNDED,
            padding=(1, 2),
            width=min(65, console.size.width - 4),
        )
        console.print()
        console.print(org_panel)
        console.print()

        org_url = prompt_org_url(console, rendered=True)

        # Try to fetch without auth first
        org_config = fetch_and_validate_org_config(console, org_url, auth=None)

        # If 401, prompt for auth and retry
        auth = None
        if org_config is None:
            _render_setup_header(
                console, step_index=2, subtitle="Provide a token if the org config is private."
            )

            # Arrow-key auth selection
            auth_options = [
                ("Environment variable", "env:VAR", "Example: env:SCC_ORG_TOKEN"),
                ("Command", "command:...", "Example: command:op read --password scc/token"),
                ("Skip authentication", "public URL", "Use if org config is publicly accessible"),
            ]

            auth_choice = _select_option(console, auth_options, default=0)

            if auth_choice == 0:
                console.print()
                var_name = Prompt.ask("[cyan]Environment variable name[/cyan]")
                auth = f"env:{var_name}"
            elif auth_choice == 1:
                console.print()
                command = Prompt.ask("[cyan]Command to run[/cyan]")
                auth = f"command:{command}"
            # else: auth stays None (skip)

            if auth:
                org_config = fetch_and_validate_org_config(console, org_url, auth=auth)

        if org_config is None:
            console.print("[red]✗ Could not fetch organization config[/red]")
            return False

        # Profile selection with arrow-key navigation
        profiles = org_config.get("profiles", {})
        profile_list = list(profiles.keys())

        _render_setup_header(console, step_index=3, subtitle="Select your team profile.")

        if profile_list:
            # Build options from profiles
            profile_options: list[tuple[str, str, str]] = []
            for profile_name in profile_list:
                profile_info = profiles[profile_name]
                desc = profile_info.get("description", "")
                profile_options.append((profile_name, "", desc))
            # Add "none" option at the end
            profile_options.append(("No profile", "skip", "Continue without a team profile"))

            profile_choice = _select_option(console, profile_options, default=0)
            if profile_choice < len(profile_list):
                profile = profile_list[profile_choice]
            else:
                profile = None  # "No profile" selected
        else:
            console.print("[dim]No profiles configured in org config.[/dim]")
            profile = None

        # Hooks with arrow-key selection
        _render_setup_header(
            console, step_index=4, subtitle="Optional safety guardrails for protected branches."
        )

        hooks_options = [
            ("Enable hooks", "recommended", "Block direct pushes to main, master, develop"),
            ("Skip hooks", "", "No git hook protection"),
        ]

        hooks_choice = _select_option(console, hooks_options, default=0)
        hooks_enabled = hooks_choice == 0

        # Confirm - single centered panel showing changes
        org_name = org_config.get("organization", {}).get("name")
        proposed = _build_proposed_config(
            org_url=org_url,
            auth=auth,
            profile=profile,
            hooks_enabled=bool(hooks_enabled),
            standalone=False,
        )
        existing = config.load_user_config()
        changes = _build_config_changes(existing, proposed)

        _render_setup_header(console, step_index=5, subtitle="Review and confirm your settings.")

        # Single centered Changes panel
        changes_panel = Panel(
            changes,
            title="[bold]Changes[/bold]",
            border_style="bright_black",
            box=box.ROUNDED,
            padding=(1, 2),
            width=min(60, console.size.width - 4),
        )
        console.print()
        console.print(changes_panel)
        console.print()
        console.print("[dim]  This will update your config file.[/dim]")

        # Arrow-key confirm selection
        confirm_options = [
            ("Apply changes", "", "Write config and complete setup"),
            ("Cancel", "", "Exit without saving"),
        ]
        confirm_choice = _select_option(console, confirm_options, default=0)

        if confirm_choice != 0:
            console.print("[yellow]Setup cancelled.[/yellow]")
            return False

        # Save config
        save_setup_config(
            console,
            org_url=org_url,
            auth=auth,
            profile=profile,
            hooks_enabled=hooks_enabled,
        )

        # Complete
        show_setup_complete(console, org_name=org_name, profile=profile)

    else:
        # Standalone mode
        standalone_left = Text()
        standalone_left.append("Standalone mode selected.\n\n")
        standalone_left.append("• No org config will be used\n", style="dim")
        standalone_left.append("• You can switch later by running scc setup\n", style="dim")

        preview = _build_config_preview(
            org_url=None,
            auth=None,
            profile=None,
            hooks_enabled=hooks_enabled,
            standalone=True,
        )

        _render_setup_layout(
            console,
            step_index=0,
            subtitle="Standalone mode (no organization config).",
            left_title="Standalone",
            left_body=standalone_left,
            right_title="Config Preview",
            right_body=preview,
            footer_hint="Press Enter to continue",
        )

        # Hooks with arrow-key selection (standalone)
        _render_setup_header(
            console, step_index=4, subtitle="Optional safety guardrails for protected branches."
        )

        hooks_options = [
            ("Enable hooks", "recommended", "Block direct pushes to main, master, develop"),
            ("Skip hooks", "", "No git hook protection"),
        ]

        hooks_choice = _select_option(console, hooks_options, default=0)
        hooks_enabled = hooks_choice == 0

        # Confirm - single centered panel showing changes
        proposed = _build_proposed_config(
            org_url=None,
            auth=None,
            profile=None,
            hooks_enabled=bool(hooks_enabled),
            standalone=True,
        )
        existing = config.load_user_config()
        changes = _build_config_changes(existing, proposed)

        _render_setup_header(console, step_index=5, subtitle="Review and confirm your settings.")

        # Single centered Changes panel
        changes_panel = Panel(
            changes,
            title="[bold]Changes[/bold]",
            border_style="bright_black",
            box=box.ROUNDED,
            padding=(1, 2),
            width=min(60, console.size.width - 4),
        )
        console.print()
        console.print(changes_panel)
        console.print()
        console.print("[dim]  This will update your config file.[/dim]")

        # Arrow-key confirm selection
        confirm_options = [
            ("Apply changes", "", "Write config and complete setup"),
            ("Cancel", "", "Exit without saving"),
        ]
        confirm_choice = _select_option(console, confirm_options, default=0)

        if confirm_choice != 0:
            console.print("[yellow]Setup cancelled.[/yellow]")
            return False

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
