"""
Setup wizard for SCC - Sandboxed Coding CLI.

Remote organization config workflow:
- Prompt for org config URL (or standalone mode)
- Handle authentication (env:VAR, command:CMD)
- Team/profile selection from remote config
- Git hooks enablement option
"""

from typing import Any, cast

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from . import config
from .bootstrap import get_default_adapters
from .commands.launch.dependencies import get_agent_provider
from .commands.launch.provider_choice import collect_provider_readiness
from .core.errors import ProviderNotReadyError
from .core.provider_resolution import get_provider_display_name
from .panels import create_info_panel
from .remote import (
    fetch_org_config,
    looks_like_github_url,
    looks_like_gitlab_url,
    save_to_cache,
)

# ── Re-exports from setup_config.py (preserve test-patch targets) ───────────
from .setup_config import (  # noqa: F401
    _append_dot_leader,
    _build_config_changes,
    _build_config_preview,
    _build_proposed_config,
    _build_setup_summary,
    _confirm_setup,
    _format_preview_value,
    _get_config_value,
    save_setup_config,
)

# ── Re-exports from setup_ui.py (preserve test-patch targets) ──────────────
from .setup_ui import (  # noqa: F401
    SETUP_STEPS,
    WELCOME_BANNER,
    _build_hint_text,
    _layout_metrics,
    _print_padded,
    _render_setup_header,
    _render_setup_layout,
    _select_option,
    show_welcome,
)
from .theme import Spinners
from .ui.prompts import confirm_with_layout, prompt_with_layout  # noqa: F401

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
        console.print("[dim]This does not affect agent auth inside the container.[/dim]")
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
# Setup Complete Display
# ═══════════════════════════════════════════════════════════════════════════════


def _three_tier_status(provider_id: str, auth_readiness: Any) -> str:
    """Return three-tier readiness label for a provider.

    Three-tier vocabulary: 'launch-ready' (image + auth), 'auth cache present'
    (auth ok, image missing), 'image available' (image ok, auth missing),
    'sign-in needed' (no auth, image status unknown).
    """
    from .commands.launch.preflight import ImageStatus, _check_image_available

    has_auth = auth_readiness is not None and auth_readiness.status == "present"
    image_status = _check_image_available(provider_id)
    has_image = image_status == ImageStatus.AVAILABLE

    if has_auth and has_image:
        return "launch-ready"
    if has_auth and not has_image:
        return "auth cache present"
    if not has_auth and has_image:
        return "image available"
    return "sign-in needed"


def show_setup_complete(
    console: Console,
    org_name: str | None = None,
    profile: str | None = None,
    standalone: bool = False,
    provider_readiness: dict[str, Any] | None = None,
    provider_preference: str | None = None,
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
    if provider_readiness is not None:
        claude_ready = provider_readiness.get("claude")
        codex_ready = provider_readiness.get("codex")
        _append_dot_leader(
            content,
            "claude",
            _three_tier_status("claude", claude_ready),
            value_style="white",
        )
        _append_dot_leader(
            content,
            "codex",
            _three_tier_status("codex", codex_ready),
            value_style="white",
        )
    if provider_preference is not None:
        preference_label = {
            "ask": "ask every time",
            "claude": "prefer Claude Code",
            "codex": "prefer Codex",
        }.get(provider_preference, provider_preference)
        _append_dot_leader(content, "startup", preference_label, value_style="white")

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
        "  [cyan]scc start ~/project[/cyan]   [dim]Launch agent in a workspace[/dim]",
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
    _print_padded(
        console,
        "  [cyan]scc provider show[/cyan]     [dim]Show current provider preference[/dim]",
        metrics,
    )
    _print_padded(
        console,
        "  [cyan]scc provider set[/cyan]      [dim]Set preference (ask|claude|codex)[/dim]",
        metrics,
    )
    console.print()


def _render_provider_status(readiness: dict[str, Any]) -> Table:
    """Build a provider connection status table."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style="cyan", no_wrap=True)
    table.add_column(style="white", no_wrap=True)
    table.add_column(style="dim")

    for provider_id in ("claude", "codex"):
        state = readiness.get(provider_id)
        status = _three_tier_status(provider_id, state)
        guidance = state.guidance if state is not None else "unavailable"
        table.add_row(get_provider_display_name(provider_id), status, guidance)
    return table


def _prompt_provider_connections(console: Console, readiness: dict[str, Any]) -> tuple[str, ...]:
    """Prompt for provider onboarding choices during setup."""
    missing = tuple(
        provider_id
        for provider_id in ("claude", "codex")
        if readiness.get(provider_id) is None or readiness[provider_id].status != "present"
    )
    if not missing:
        return ()

    options: list[tuple[str, str, str]] = []
    if len(missing) == 2:
        options.append(
            (
                "Connect both",
                "recommended",
                "Authenticate Claude first, then Codex, and reuse both later.",
            )
        )
    for provider_id in missing:
        options.append(
            (
                f"Connect {get_provider_display_name(provider_id)}",
                "browser",
                f"Authenticate {get_provider_display_name(provider_id)} now.",
            )
        )
    options.append(("Skip for now", "", "You can connect a provider later during start."))

    console.print()
    _print_padded(
        console,
        Panel(
            _render_provider_status(readiness),
            title="[bold cyan]Connect Coding Agents[/bold cyan]",
            subtitle=(
                "Connect Claude, Codex, or both now so future starts reuse the saved auth cache."
            ),
            border_style="bright_black",
            box=box.ROUNDED,
            padding=(0, 1),
        ),
        _layout_metrics(console),
    )
    console.print()

    selected = _select_option(console, options, default=0)
    if selected is None:
        return ()

    label = options[selected][0]
    if label == "Skip for now":
        return ()
    if label == "Connect both":
        return ("claude", "codex")
    if "Claude" in label:
        return ("claude",)
    return ("codex",)


def _prompt_provider_preference(console: Console, current: str | None) -> str | None:
    """Prompt for how SCC should behave when both providers are connected."""
    options = [
        ("Ask me when both are available", "default", "Choose at start time when needed."),
        ("Prefer Claude Code", "", "Use Claude automatically unless you override it."),
        ("Prefer Codex", "", "Use Codex automatically unless you override it."),
    ]
    default_index = 0
    if current == "claude":
        default_index = 1
    elif current == "codex":
        default_index = 2

    console.print()
    selected = _select_option(console, options, default=default_index)
    if selected is None:
        return current
    if selected == 0:
        return "ask"
    if selected == 1:
        return "claude"
    return "codex"


def _run_provider_onboarding(console: Console) -> tuple[dict[str, Any] | None, str | None]:
    """Offer one-time provider sign-in during setup."""
    adapters = get_default_adapters()
    try:
        adapters.sandbox_runtime.ensure_available()
    except Exception:
        console.print()
        console.print(
            "[dim]Provider sign-in skipped during setup because Docker is not available yet.[/dim]"
        )
        return None, config.get_selected_provider()

    readiness = collect_provider_readiness(adapters)
    sequence = _prompt_provider_connections(console, readiness)

    for provider_id in sequence:
        display_name = get_provider_display_name(provider_id)
        console.print()
        _print_padded(
            console,
            create_info_panel(
                f"Connecting {display_name}",
                f"SCC will open the normal {display_name} sign-in flow now.",
                "When sign-in completes, the auth cache will be reused on future starts.",
            ),
            _layout_metrics(console),
        )
        console.print()
        provider_adapter = get_agent_provider(adapters, provider_id)
        if provider_adapter is None:
            continue
        try:
            provider_adapter.bootstrap_auth()
        except ProviderNotReadyError as exc:
            console.print()
            _print_padded(
                console,
                create_info_panel(
                    f"{display_name} sign-in incomplete",
                    exc.user_message,
                    exc.suggested_action or "You can retry the provider sign-in later during start.",
                ),
                _layout_metrics(console),
            )
            console.print()

    refreshed = collect_provider_readiness(adapters)
    selected_preference = config.get_selected_provider()
    if all(
        refreshed.get(provider_id) is not None and refreshed[provider_id].status == "present"
        for provider_id in ("claude", "codex")
    ):
        preference = _prompt_provider_preference(console, config.get_selected_provider())
        config.set_selected_provider(preference)
        selected_preference = preference
    return refreshed, selected_preference


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

    provider_readiness, provider_preference = _run_provider_onboarding(console)

    # Complete
    if standalone:
        show_setup_complete(
            console,
            standalone=True,
            provider_readiness=provider_readiness,
            provider_preference=provider_preference,
        )
    else:
        show_setup_complete(
            console,
            org_name=org_name,
            profile=profile,
            provider_readiness=provider_readiness,
            provider_preference=provider_preference,
        )

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

    provider_readiness, provider_preference = _run_provider_onboarding(console)

    org_name = org_config.get("organization", {}).get("name")
    show_setup_complete(
        console,
        org_name=org_name,
        profile=team,
        provider_readiness=provider_readiness,
        provider_preference=provider_preference,
    )

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
