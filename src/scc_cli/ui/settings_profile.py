"""Profile-related operations for the Settings screen.

Extracted from settings.py: _profile_diff, _profile_sync, and _sync_*
helpers. These functions receive the console and context explicitly
rather than through `self`.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from scc_cli.application import settings as app_settings
from scc_cli.application.settings import (
    ConfirmationKind,
    ProfileDiffInfo,
    ProfileSyncMode,
    ProfileSyncPathPayload,
    ProfileSyncPayload,
    ProfileSyncPreview,
    ProfileSyncResult,
    SettingsActionResult,
    SettingsChangeRequest,
    SettingsContext,
    SettingsValidationRequest,
)


def profile_diff(console: Console, diff_info: ProfileDiffInfo) -> None:
    """Show diff between profile and workspace settings with visual overlay."""
    diff = diff_info.diff
    if diff.is_empty:
        console.print()
        console.print("[green]✓ Profile is in sync with workspace[/green]")
        return None

    lines: list[str] = []
    current_section = ""
    rendered_lines = 0
    max_lines = 12
    truncated = False

    indicators = {
        "added": "[green]+[/green]",
        "removed": "[red]−[/red]",
        "modified": "[yellow]~[/yellow]",
    }

    section_names = {
        "plugins": "plugins",
        "mcp_servers": "mcp_servers",
        "marketplaces": "marketplaces",
    }

    for item in diff.items:
        if rendered_lines >= max_lines and not truncated:
            truncated = True
            break

        if item.section != current_section:
            if current_section:
                lines.append("")
                rendered_lines += 1
            lines.append(f"  [bold]{section_names.get(item.section, item.section)}[/bold]")
            rendered_lines += 1
            current_section = item.section

        indicator = indicators.get(item.status, " ")
        modifier = "(modified)" if item.status == "modified" else ""
        if modifier:
            lines.append(f"    {indicator} {item.name}  [dim]{modifier}[/dim]")
        else:
            lines.append(f"    {indicator} {item.name}")
        rendered_lines += 1

    if truncated:
        remaining = diff.total_count - (rendered_lines - len(set(i.section for i in diff.items)))
        lines.append("")
        lines.append(f"  [dim]+ {remaining} more items...[/dim]")

    lines.append("")
    lines.append(f"  [dim]{diff.total_count} difference(s) · Esc close[/dim]")

    content = "\n".join(lines)

    console.print()
    console.print(
        Panel(
            content,
            title="[bold]Profile Diff[/bold]",
            border_style="bright_black",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )

    return None


def profile_sync(
    console: Console,
    context: SettingsContext,
    view_model: app_settings.SettingsViewModel,
    refresh_view_model: Callable[[], None],
    handle_action_result: Callable[[SettingsActionResult], str | None],
    render_profile_sync_preview: Callable[[ProfileSyncPreview], None],
) -> str | None:
    """Sync profiles with a repository using overlay picker."""
    from .list_screen import ListItem, ListScreen

    default_path = view_model.sync_repo_path

    items: list[ListItem[str]] = [
        ListItem(
            value="change_path",
            label=f"📁 {default_path}",
            description="Change path",
        ),
        ListItem(
            value="export",
            label="Export",
            description="Save profiles to folder",
        ),
        ListItem(
            value="import",
            label="Import",
            description="Load profiles from folder",
        ),
        ListItem(
            value="full_sync",
            label="Full sync",
            description="Load then save  (advanced)",
        ),
    ]

    screen = ListScreen(items, title="[cyan]Sync[/cyan] Profiles")
    selected = screen.run()

    if not selected:
        return None

    repo_path = Path(default_path).expanduser()

    if selected == "change_path":
        return _sync_change_path(
            console,
            context,
            default_path,
            refresh_view_model=refresh_view_model,
            handle_action_result=handle_action_result,
            profile_sync_fn=lambda: profile_sync(
                console,
                context,
                view_model,
                refresh_view_model,
                handle_action_result,
                render_profile_sync_preview,
            ),
        )
    if selected == "export":
        return _sync_export(
            console,
            context,
            repo_path,
            handle_action_result=handle_action_result,
            refresh_view_model=refresh_view_model,
        )
    if selected == "import":
        return _sync_import(
            console,
            context,
            repo_path,
            handle_action_result=handle_action_result,
            refresh_view_model=refresh_view_model,
            render_profile_sync_preview=render_profile_sync_preview,
        )
    if selected == "full_sync":
        return _sync_full(
            console,
            context,
            repo_path,
            handle_action_result=handle_action_result,
            refresh_view_model=refresh_view_model,
        )

    return None


def _confirm_create_directory(console: Console, message: str) -> bool:
    """Confirm directory creation."""
    path = message.replace("Create directory?", "").strip()
    console.print()
    panel = Panel(
        f"[yellow]Path does not exist:[/yellow]\n  {path}",
        title="[cyan]Create[/cyan] Directory",
        border_style="yellow",
        box=box.ROUNDED,
        padding=(1, 2),
    )
    console.print(panel)
    return Confirm.ask("[cyan]Create directory?[/cyan]", default=True)


def _sync_change_path(
    console: Console,
    context: SettingsContext,
    current_path: str,
    *,
    refresh_view_model: Callable[[], None],
    handle_action_result: Callable[[SettingsActionResult], str | None],
    profile_sync_fn: Callable[[], str | None],
) -> str | None:
    """Handle path editing for sync."""
    console.print()
    panel = Panel(
        f"[dim]Current:[/dim] {current_path}\n\n"
        "[dim]Enter new path or press Enter to keep current[/dim]",
        title="[cyan]Edit[/cyan] Repository Path",
        border_style="cyan",
        box=box.ROUNDED,
        padding=(1, 2),
    )
    console.print(panel)
    new_path = Prompt.ask("[cyan]Path[/cyan]", default=current_path)

    if new_path and new_path != current_path:
        result = app_settings.apply_settings_change(
            SettingsChangeRequest(
                action_id="profile_sync",
                workspace=context.workspace,
                payload=ProfileSyncPathPayload(new_path=new_path),
            )
        )
        handle_action_result(result)
        refresh_view_model()

    return profile_sync_fn()


def _sync_export(
    console: Console,
    context: SettingsContext,
    repo_path: Path,
    *,
    handle_action_result: Callable[[SettingsActionResult], str | None],
    refresh_view_model: Callable[[], None],
) -> str | None:
    """Export profiles to repository."""
    payload = ProfileSyncPayload(mode=ProfileSyncMode.EXPORT, repo_path=repo_path)
    validation = app_settings.validate_settings(
        SettingsValidationRequest(
            action_id="profile_sync",
            workspace=context.workspace,
            payload=payload,
        )
    )
    if validation and validation.error:
        console.print(f"[yellow]{validation.error}[/yellow]")
        Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
        return None

    create_dir = False
    if validation and validation.confirmation == ConfirmationKind.CONFIRM and validation.message:
        create_dir = _confirm_create_directory(console, validation.message)
        if not create_dir:
            return None

    console.print(f"[dim]Exporting to {repo_path}...[/dim]")
    payload = ProfileSyncPayload(
        mode=ProfileSyncMode.EXPORT,
        repo_path=repo_path,
        create_dir=create_dir,
    )
    result = app_settings.apply_settings_change(
        SettingsChangeRequest(
            action_id="profile_sync",
            workspace=context.workspace,
            payload=payload,
        )
    )
    message = handle_action_result(result)
    refresh_view_model()
    return message


def _sync_import(
    console: Console,
    context: SettingsContext,
    repo_path: Path,
    *,
    handle_action_result: Callable[[SettingsActionResult], str | None],
    refresh_view_model: Callable[[], None],
    render_profile_sync_preview: Callable[[ProfileSyncPreview], None],
) -> str | None:
    """Import profiles from repository with preview."""
    console.print(f"[dim]Checking {repo_path}...[/dim]")
    payload = ProfileSyncPayload(mode=ProfileSyncMode.IMPORT, repo_path=repo_path)
    validation = app_settings.validate_settings(
        SettingsValidationRequest(
            action_id="profile_sync",
            workspace=context.workspace,
            payload=payload,
        )
    )

    if validation and validation.error:
        console.print(
            Panel(
                f"[yellow]✗ {validation.error}[/yellow]",
                title="[cyan]Sync[/cyan] Profiles",
                border_style="bright_black",
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )
        Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
        return None

    confirmed = True
    if validation and isinstance(validation.detail, ProfileSyncPreview):
        render_profile_sync_preview(validation.detail)
        confirmed = Confirm.ask("Import now?", default=True)
        if not confirmed:
            return None

    result = app_settings.apply_settings_change(
        SettingsChangeRequest(
            action_id="profile_sync",
            workspace=context.workspace,
            payload=payload,
            confirmed=confirmed,
        )
    )
    message = handle_action_result(result)
    refresh_view_model()
    return message


def _sync_full(
    console: Console,
    context: SettingsContext,
    repo_path: Path,
    *,
    handle_action_result: Callable[[SettingsActionResult], str | None],
    refresh_view_model: Callable[[], None],
) -> str | None:
    """Full sync: import then export."""
    console.print(f"[dim]Full sync with {repo_path}...[/dim]")
    payload = ProfileSyncPayload(mode=ProfileSyncMode.FULL_SYNC, repo_path=repo_path)
    result = app_settings.apply_settings_change(
        SettingsChangeRequest(
            action_id="profile_sync",
            workspace=context.workspace,
            payload=payload,
        )
    )
    message = handle_action_result(result)
    refresh_view_model()
    return message


def render_profile_sync_result(console: Console, result: ProfileSyncResult) -> None:
    """Render profile sync result."""
    lines: list[str] = []
    if result.mode == ProfileSyncMode.EXPORT:
        lines.append(f"[green]✓ Exported {result.exported} profile(s)[/green]")
        for profile_id in result.profile_ids:
            lines.append(f"  [green]+[/green] {profile_id}")
        if result.warnings:
            lines.append("")
            for warning in result.warnings:
                lines.append(f"  [yellow]![/yellow] {warning}")
        lines.append("")
        lines.append("[dim]Files written locally · no git commit/push[/dim]")
        lines.append("[dim]For git: scc profile export --repo PATH --commit --push[/dim]")

    if result.mode == ProfileSyncMode.IMPORT:
        lines.append(f"[green]✓ Imported {result.imported} profile(s)[/green]")
        if result.warnings:
            lines.append("")
            for warning in result.warnings:
                lines.append(f"  [yellow]![/yellow] {warning}")
        lines.append("")
        lines.append("[dim]Profiles copied locally · no git pull[/dim]")
        lines.append("[dim]For git: scc profile import --repo PATH --pull[/dim]")

    if result.mode == ProfileSyncMode.FULL_SYNC:
        lines.append("[green]✓ Sync complete[/green]")
        lines.append("")
        lines.append(f"  Imported: {result.imported} profile(s)")
        lines.append(f"  Exported: {result.exported} profile(s)")
        lines.append("")
        lines.append("[dim]Files synced locally · no git operations[/dim]")
        lines.append("[dim]For git: scc profile sync --repo PATH --pull --commit --push[/dim]")

    console.print()
    console.print(
        Panel(
            "\n".join(lines),
            title="[cyan]Sync[/cyan] Profiles",
            border_style="bright_black",
            box=box.ROUNDED,
            padding=(1, 2),
        )
    )
