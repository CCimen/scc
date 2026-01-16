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

import readchar
from rich import box
from rich.columns import Columns
from rich.console import Console, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import config
from .remote import (
    fetch_org_config,
    looks_like_github_url,
    looks_like_gitlab_url,
    save_to_cache,
)
from .theme import Borders, Indicators, Spinners
from .ui.chrome import LayoutMetrics, apply_layout, get_layout_metrics, print_with_layout
from .ui.prompts import confirm_with_layout, prompt_with_layout

# ═══════════════════════════════════════════════════════════════════════════════
# Arrow-Key Selection Component
# ═══════════════════════════════════════════════════════════════════════════════


def _layout_metrics(console: Console) -> LayoutMetrics:
    """Return layout metrics for setup rendering."""
    return get_layout_metrics(console, max_width=104)


def _print_padded(console: Console, renderable: RenderableType, metrics: LayoutMetrics) -> None:
    """Print with layout padding when applicable."""
    print_with_layout(console, renderable, metrics=metrics, constrain=True)


def _build_hint_text(hints: list[tuple[str, str]]) -> Text:
    """Build a compact hint line with middot separators."""
    text = Text()
    for index, (key, action) in enumerate(hints):
        if index > 0:
            text.append(" · ", style="dim")
        text.append(key, style="cyan bold")
        text.append(" ", style="dim")
        text.append(action, style="dim")
    return text


def _select_option(
    console: Console,
    options: list[tuple[str, str, str]],
    *,
    default: int = 0,
) -> int | None:
    """Interactive arrow-key selection for setup options.

    Args:
        console: Rich console for output.
        options: List of (label, tag, description) tuples.
        default: Default selected index.

    Returns:
        Selected index (0-based), or None if cancelled.
    """
    cursor = default
    cursor_symbol = Indicators.get("CURSOR")

    def _render_options() -> RenderableType:
        """Render options for the live picker."""
        metrics = _layout_metrics(console)
        content_width = metrics.content_width
        min_label_width = min(36, max(24, content_width // 3))
        label_width = max(min_label_width, max((len(label) for label, _, _ in options), default=0))
        tag_width = max((len(tag) for _, tag, _ in options), default=0)

        body = Text()
        if not metrics.tight_height:
            body.append("\n")

        for i, (label, tag, desc) in enumerate(options):
            is_selected = i == cursor
            line = Text()
            line.append("  ")
            line.append(cursor_symbol if is_selected else " ", style="cyan" if is_selected else "")
            line.append(" ")
            line.append(label, style="bold white" if is_selected else "dim")
            if tag:
                padding = label_width - len(label) + (3 if tag_width else 2)
                line.append(" " * max(2, padding))
                line.append(tag, style="cyan" if is_selected else "dim")
            body.append_text(line)
            body.append("\n")
            if desc:
                body.append(f"    {desc}\n", style="dim")

            if i < len(options) - 1 and not metrics.tight_height:
                body.append("\n")

        if not metrics.tight_height:
            body.append("\n")

        hints = _build_hint_text(
            [
                ("↑↓", "navigate"),
                ("Enter", "confirm"),
                ("Esc", "cancel"),
            ]
        )
        inner_width = (
            metrics.inner_width(padding_x=1, border=2)
            if metrics.should_center and metrics.apply
            else content_width
        )
        separator_len = max(len(hints.plain), inner_width)
        body.append(Borders.FOOTER_SEPARATOR * separator_len, style="dim")
        body.append("\n")
        body.append_text(hints)

        renderable: RenderableType = body
        if metrics.apply and metrics.should_center:
            renderable = Panel(
                body,
                border_style="bright_black",
                box=box.ROUNDED,
                padding=(0, 1),
                width=metrics.content_width,
            )

        if metrics.apply:
            renderable = apply_layout(renderable, metrics)

        return renderable

    with Live(_render_options(), console=console, auto_refresh=False, transient=True) as live:
        while True:
            key = readchar.readkey()

            if key in (readchar.key.UP, "k"):
                cursor = (cursor - 1) % len(options)
                live.update(_render_options(), refresh=True)
            elif key in (readchar.key.DOWN, "j"):
                cursor = (cursor + 1) % len(options)
                live.update(_render_options(), refresh=True)
            elif key in (readchar.key.ENTER, "\r", "\n"):
                return cursor
            elif key in (readchar.key.ESC, "q"):
                return None
            else:
                continue


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
    auth_header: str | None,
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
        if auth_header:
            _append_dot_leader(
                preview,
                "org.auth_header",
                _format_preview_value(auth_header),
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
    auth_header: str | None,
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
        org_source: dict[str, Any] = {
            "url": org_url,
            "auth": auth,
        }
        if auth_header:
            org_source["auth_header"] = auth_header
        user_config["organization_source"] = org_source
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
        "organization_source.auth_header",
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
    """Render the setup step header with underline-style tabs."""
    console.clear()

    metrics = _layout_metrics(console)
    content_width = metrics.content_width

    console.print()
    _print_padded(console, Text("SCC Setup", style="bold white"), metrics)
    if not metrics.tight_height:
        console.print()

    tabs = Text()
    underline = Text()
    separator = "   "

    for idx, step in enumerate(SETUP_STEPS):
        if idx > 0:
            tabs.append(separator)
            underline.append(" " * len(separator))

        is_active = idx == step_index
        is_complete = idx < step_index
        if is_active:
            tab_style = "bold cyan"
        elif is_complete:
            tab_style = "green"
        else:
            tab_style = "dim"

        tabs.append(step, style=tab_style)
        underline_segment = (
            Indicators.get("HORIZONTAL_LINE") * len(step) if is_active else " " * len(step)
        )
        underline.append(underline_segment, style="cyan" if is_active else "dim")

    _print_padded(console, tabs, metrics)
    _print_padded(console, underline, metrics)

    if not metrics.should_center:
        separator_len = max(len(tabs.plain), content_width)
        _print_padded(console, Borders.FOOTER_SEPARATOR * separator_len, metrics)

    if subtitle:
        if not metrics.tight_height:
            console.print()
        _print_padded(console, f"  {subtitle}", metrics)
        console.print()
    else:
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

    metrics = _layout_metrics(console)
    content_width = metrics.content_width
    width = console.size.width
    stacked_width = content_width
    column_width = max(32, (content_width - 4) // 2)

    expand_panels = width >= 100

    left_panel = Panel(
        left_body,
        title=f"[dim]{left_title}[/dim]",
        border_style="bright_black",
        padding=(0, 1),
        box=box.ROUNDED,
        width=stacked_width if width < 100 else column_width,
        expand=expand_panels,
    )
    right_panel = Panel(
        right_body,
        title=f"[dim]{right_title}[/dim]",
        border_style="bright_black",
        padding=(0, 1),
        box=box.ROUNDED,
        width=stacked_width if width < 100 else column_width,
        expand=expand_panels,
    )

    if width < 100:
        _print_padded(console, left_panel, metrics)
        if not metrics.tight_height:
            console.print()
        _print_padded(console, right_panel, metrics)
    else:
        columns = Columns([left_panel, right_panel], expand=False, equal=True)
        _print_padded(console, columns, metrics)

    console.print()
    if footer_hint:
        separator_len = max(len(footer_hint), content_width)
        _print_padded(console, Borders.FOOTER_SEPARATOR * separator_len, metrics)
        _print_padded(console, f"  [dim]{footer_hint}[/dim]", metrics)
        return

    hints = _build_hint_text(
        [
            ("↑↓", "navigate"),
            ("Enter", "confirm"),
            ("Esc", "cancel"),
        ]
    )
    separator_len = max(len(hints.plain), content_width)
    _print_padded(console, Borders.FOOTER_SEPARATOR * separator_len, metrics)
    _print_padded(console, hints, metrics)


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
    choice = prompt_with_layout(
        console,
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
        url = prompt_with_layout(console, "[cyan]Organization config URL[/cyan]")

        # Validate HTTPS
        if url.startswith("http://"):
            console.print("[red]✗ HTTP URLs are not allowed. Please use HTTPS.[/red]")
            continue

        if not url.startswith("https://"):
            console.print("[red]URL must start with https://[/red]")
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

    choice = prompt_with_layout(
        console,
        "[cyan]Select auth method[/cyan]",
        choices=["1", "2", "3"],
        default="1",
    )

    if choice == "1":
        var_name = prompt_with_layout(console, "[cyan]Environment variable name[/cyan]")
        return f"env:{var_name}"

    if choice == "2":
        command = prompt_with_layout(console, "[cyan]Command to run[/cyan]")
        return f"command:{command}"

    # Choice 3: Skip
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Remote Config Fetching
# ═══════════════════════════════════════════════════════════════════════════════


def fetch_and_validate_org_config(
    console: Console,
    url: str,
    auth: str | None,
    auth_header: str | None = None,
) -> dict[str, Any] | None:
    """Fetch and validate the organization config from a URL.

    Args:
        console: Rich console for output
        url: HTTPS URL to org config
        auth: Auth spec (env:VAR, command:CMD) or None
        auth_header: Optional header name for auth (e.g., PRIVATE-TOKEN)

    Returns:
        Organization config dict if successful, None if auth required (401).
    """
    console.print()
    with console.status("Fetching organization config...", spinner=Spinners.NETWORK):
        config_data, etag, status = fetch_org_config(
            url,
            auth=auth,
            etag=None,
            auth_header=auth_header,
        )

    if status == 401:
        console.print("[yellow]Authentication required (401)[/yellow]")
        return None

    if status == 403:
        console.print("[red]Access denied (403)[/red]")
        return None

    if status != 200 or config_data is None:
        console.print(f"[red]Failed to fetch config (status: {status})[/red]")
        return None

    org_name = config_data.get("organization", {}).get("name", "Unknown")
    console.print(f"[green]Connected to: {org_name}[/green]")

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
        border_style="bright_black",
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
    choice_str = prompt_with_layout(
        console,
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

    return confirm_with_layout(
        console,
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
    auth_header: str | None,
    profile: str | None,
    hooks_enabled: bool,
    standalone: bool = False,
) -> None:
    """Save the setup configuration to the user config file.

    Args:
        console: Rich console for output
        org_url: Organization config URL or None
        auth: Auth spec or None
        auth_header: Optional auth header for org fetch
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
        org_source: dict[str, Any] = {
            "url": org_url,
            "auth": auth,
        }
        if auth_header:
            org_source["auth_header"] = auth_header
        user_config["organization_source"] = org_source
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

    metrics = _layout_metrics(console)
    content_width = metrics.content_width
    _print_padded(console, Text("Setup Complete", style="bold green"), metrics)
    if not metrics.tight_height:
        console.print()

    # Build content
    content = Text()

    if standalone:
        _append_dot_leader(content, "mode", "standalone", value_style="white")
    elif org_name:
        _append_dot_leader(content, "organization", org_name, value_style="white")
        _append_dot_leader(content, "profile", profile or "none", value_style="white")

    _append_dot_leader(content, "config", str(config.CONFIG_DIR), value_style="cyan")

    # Main panel
    main_panel = Panel(
        content,
        border_style="bright_black",
        box=box.ROUNDED,
        padding=(1, 2),
        width=min(content_width, 80),
    )
    _print_padded(console, main_panel, metrics)

    # Next steps
    if not metrics.tight_height:
        console.print()
    _print_padded(console, "  [bold white]Get started[/bold white]", metrics)
    if not metrics.tight_height:
        console.print()
    _print_padded(
        console,
        "  [cyan]scc start ~/project[/cyan]   [dim]Launch Claude in a workspace[/dim]",
        metrics,
    )
    _print_padded(
        console,
        "  [cyan]scc team list[/cyan]         [dim]List available teams[/dim]",
        metrics,
    )
    _print_padded(
        console,
        "  [cyan]scc doctor[/cyan]            [dim]Check system health[/dim]",
        metrics,
    )
    console.print()


def _build_setup_summary(
    *,
    org_url: str | None,
    auth: str | None,
    auth_header: str | None,
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
        if auth_header:
            _line("Auth Header", auth_header)

    _line("Hooks", "enabled" if hooks_enabled else "disabled")
    _line("Config dir", str(config.CONFIG_DIR))
    return summary


def _confirm_setup(
    console: Console,
    *,
    org_url: str | None,
    auth: str | None,
    auth_header: str | None = None,
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
        auth_header=auth_header,
        profile=profile,
        hooks_enabled=hooks_enabled,
        standalone=standalone,
        org_name=org_name,
    )

    if not rendered:
        metrics = _layout_metrics(console)
        panel = Panel(
            summary,
            title="[bold cyan]Review & Confirm[/bold cyan]",
            border_style="bright_black",
            box=box.ROUNDED,
            padding=(1, 2),
            width=min(metrics.content_width, 80),
        )
        _print_padded(console, panel, metrics)
        console.print()

    return confirm_with_layout(console, "[cyan]Apply these settings?[/cyan]", default=True)


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
    if selected is None:
        console.print("[yellow]Setup cancelled.[/yellow]")
        return False
    has_org_config = selected == 0
    standalone = not has_org_config
    org_name = None
    auth_header: str | None = None

    if has_org_config:
        # Get org URL - single centered panel
        _render_setup_header(console, step_index=1, subtitle="Enter your organization config URL.")

        org_help = Text()
        org_help.append("Your platform team provides this URL.\n\n", style="dim")
        org_help.append("  • Must be HTTPS\n", style="dim")
        org_help.append("  • Points to your org-config.json\n", style="dim")
        org_help.append("  • If the URL loads without a token, skip auth\n", style="dim")
        org_help.append("  • Example: ", style="dim")
        org_help.append("https://example.com/scc/org.json", style="cyan dim")

        metrics = _layout_metrics(console)
        org_panel = Panel(
            org_help,
            title="[bold cyan]Organization URL[/bold cyan]",
            border_style="bright_black",
            box=box.ROUNDED,
            padding=(1, 2),
            width=min(metrics.content_width, 80),
        )
        console.print()
        _print_padded(console, org_panel, metrics)
        console.print()

        org_url = prompt_org_url(console, rendered=True)

        # Try to fetch without auth first
        org_config = fetch_and_validate_org_config(
            console,
            org_url,
            auth=None,
            auth_header=None,
        )

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
            if auth_choice is None:
                console.print("[yellow]Setup cancelled.[/yellow]")
                return False

            if auth_choice == 0:
                console.print()
                if looks_like_gitlab_url(org_url):
                    default_var = "GITLAB_TOKEN"
                elif looks_like_github_url(org_url):
                    default_var = "GITHUB_TOKEN"
                else:
                    default_var = "SCC_ORG_TOKEN"
                var_name = prompt_with_layout(
                    console,
                    "[cyan]Environment variable name[/cyan]",
                    default=default_var,
                )
                auth = f"env:{var_name}"
            elif auth_choice == 1:
                console.print()
                command = prompt_with_layout(console, "[cyan]Command to run[/cyan]")
                auth = f"command:{command}"
            # else: auth stays None (skip)

            if auth and looks_like_gitlab_url(org_url):
                console.print("[dim]GitLab detected. Default header: PRIVATE-TOKEN.[/dim]")
                auth_header = prompt_with_layout(
                    console, "[cyan]Auth header[/cyan]", default="PRIVATE-TOKEN"
                )

            if auth:
                org_config = fetch_and_validate_org_config(
                    console,
                    org_url,
                    auth=auth,
                    auth_header=auth_header,
                )

        if org_config is None:
            console.print("[red]Could not fetch organization config[/red]")
            return False

        org_name = org_config.get("organization", {}).get("name")

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
            if profile_choice is None:
                console.print("[yellow]Setup cancelled.[/yellow]")
                return False
            if profile_choice < len(profile_list):
                profile = profile_list[profile_choice]
            else:
                profile = None  # "No profile" selected
        else:
            console.print("[dim]No profiles configured in org config.[/dim]")
            profile = None

    else:
        standalone_left = Text()
        standalone_left.append("Standalone mode selected.\n\n")
        standalone_left.append("• No organization config required\n", style="dim")
        standalone_left.append("• You can switch later with `scc setup`\n", style="dim")
        standalone_left.append("• Teams and profiles stay disabled\n", style="dim")

        preview = _build_config_preview(
            org_url=None,
            auth=None,
            auth_header=None,
            profile=None,
            hooks_enabled=None,
            standalone=True,
        )

        _render_setup_layout(
            console,
            step_index=1,
            subtitle="Standalone mode (no organization config).",
            left_title="Standalone",
            left_body=standalone_left,
            right_title="Config Preview",
            right_body=preview,
            footer_hint="Next: configure hooks",
        )

    # Hooks with arrow-key selection
    _render_setup_header(
        console, step_index=4, subtitle="Optional safety guardrails for protected branches."
    )

    hooks_options = [
        ("Enable hooks", "recommended", "Block direct pushes to main, master, develop"),
        ("Skip hooks", "", "No git hook protection"),
    ]

    hooks_choice = _select_option(console, hooks_options, default=0)
    if hooks_choice is None:
        console.print("[yellow]Setup cancelled.[/yellow]")
        return False
    hooks_enabled = hooks_choice == 0

    # Confirm - single centered panel showing changes
    proposed = _build_proposed_config(
        org_url=org_url,
        auth=auth,
        auth_header=auth_header,
        profile=profile,
        hooks_enabled=bool(hooks_enabled),
        standalone=standalone,
    )
    existing = config.load_user_config()
    changes = _build_config_changes(existing, proposed)

    _render_setup_header(console, step_index=5, subtitle="Review and confirm your settings.")

    # Single centered Changes panel
    metrics = _layout_metrics(console)
    changes_panel = Panel(
        changes,
        title="[bold cyan]Changes[/bold cyan]",
        border_style="bright_black",
        box=box.ROUNDED,
        padding=(1, 2),
        width=min(metrics.content_width, 80),
    )
    console.print()
    _print_padded(console, changes_panel, metrics)
    console.print()
    _print_padded(console, "[dim]  This will update your config file.[/dim]", metrics)

    # Arrow-key confirm selection
    confirm_options = [
        ("Apply changes", "", "Write config and complete setup"),
        ("Cancel", "", "Exit without saving"),
    ]
    confirm_choice = _select_option(console, confirm_options, default=0)

    if confirm_choice is None or confirm_choice != 0:
        console.print("[yellow]Setup cancelled.[/yellow]")
        return False

    # Save config
    save_setup_config(
        console,
        org_url=org_url,
        auth=auth,
        auth_header=auth_header,
        profile=profile,
        hooks_enabled=hooks_enabled,
        standalone=standalone,
    )

    # Complete
    if standalone:
        show_setup_complete(console, standalone=True)
    else:
        show_setup_complete(console, org_name=org_name, profile=profile)

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
            auth_header=None,
            profile=None,
            hooks_enabled=False,
            standalone=True,
        )
        show_setup_complete(console, standalone=True)
        return True

    if not org_url:
        console.print("[red]Organization URL required (use --org-url)[/red]")
        return False

    auth_header = "PRIVATE-TOKEN" if auth and looks_like_gitlab_url(org_url) else None

    # Fetch org config
    org_config = fetch_and_validate_org_config(
        console,
        org_url,
        auth=auth,
        auth_header=auth_header,
    )

    if org_config is None:
        console.print("[red]Could not fetch organization config[/red]")
        return False

    # Validate team if provided
    if team:
        profiles = org_config.get("profiles", {})
        if team not in profiles:
            available = ", ".join(profiles.keys())
            console.print(f"[red]Team '{team}' not found. Available: {available}[/red]")
            return False

    # Save config
    save_setup_config(
        console,
        org_url=org_url,
        auth=auth,
        auth_header=auth_header,
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
