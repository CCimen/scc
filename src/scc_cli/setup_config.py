"""
Configuration building, preview, and persistence for the SCC setup wizard.

Extracted from setup.py to reduce module size.
Contains: config preview rendering, proposed config assembly, config diff,
save logic, setup summary, and confirmation flow.
"""

from typing import Any

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from . import config
from .setup_ui import _layout_metrics, _print_padded
from .ui.prompts import confirm_with_layout

# ═══════════════════════════════════════════════════════════════════════════════
# Config Preview Helpers
# ═══════════════════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════════════════
# Proposed Config Assembly
# ═══════════════════════════════════════════════════════════════════════════════


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
# Setup Summary & Confirmation
# ═══════════════════════════════════════════════════════════════════════════════


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
