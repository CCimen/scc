"""Settings and Maintenance TUI screen.

This module provides an interactive settings screen accessible via 's' key
from the dashboard. It allows users to perform maintenance operations like:
- Clearing cache
- Pruning sessions
- Resetting configuration
- Factory reset

The screen uses a two-column layout with categories on the left and
actions on the right, following the risk tier confirmation model.
"""

from __future__ import annotations

from pathlib import Path

import readchar
from rich.console import Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from scc_cli.application import settings as app_settings
from scc_cli.application.settings import (
    ConfirmationKind,
    DoctorInfo,
    PathsInfo,
    ProfileDiffInfo,
    ProfileSyncMode,
    ProfileSyncPathPayload,
    ProfileSyncPayload,
    ProfileSyncPreview,
    ProfileSyncResult,
    SettingsAction,
    SettingsActionResult,
    SettingsActionStatus,
    SettingsChangeRequest,
    SettingsContext,
    SettingsValidationRequest,
    SettingsValidationResult,
    SupportBundleInfo,
    SupportBundlePayload,
    VersionInfo,
)
from scc_cli.application.settings import (
    SettingsCategory as Category,
)

from ..console import get_err_console
from ..maintenance import MaintenancePreview, RiskTier
from ..theme import Indicators
from .chrome import apply_layout, get_layout_metrics


def _get_risk_badge(tier: RiskTier) -> Text:
    """Get a color-coded risk badge for display.

    Uses both color and text/symbols for accessibility.
    Returns a Text object (not markup string) for proper rendering.
    """
    match tier:
        case RiskTier.SAFE:
            return Text.from_markup("[green]SAFE[/green]")
        case RiskTier.CHANGES_STATE:
            return Text.from_markup("[yellow]CHANGES STATE[/yellow]")
        case RiskTier.DESTRUCTIVE:
            return Text.from_markup("[red]DESTRUCTIVE[/red]")
        case RiskTier.FACTORY_RESET:
            return Text.from_markup("[bold red]VERY DESTRUCTIVE[/bold red]")
        case _:
            return Text("UNKNOWN")


def _format_bytes(size_bytes: int) -> str:
    """Format bytes as human-readable string."""
    if size_bytes == 0:
        return "0 B"
    size: float = size_bytes
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}" if size >= 10 else f"{int(size)} {unit}"
        size = size / 1024
    return f"{size:.1f} TB"


class SettingsScreen:
    """Interactive settings and maintenance screen.

    Provides a two-column layout with category navigation on the left
    and action list on the right. Supports keyboard navigation and
    risk-appropriate confirmation for each action.
    """

    def __init__(self, initial_category: Category | None = None) -> None:
        """Initialize the settings screen.

        Args:
            initial_category: Optional category to start on. Defaults to MAINTENANCE.
        """
        self._console = get_err_console()
        self._context = SettingsContext(workspace=Path.cwd())
        self._view_model = app_settings.load_settings_state(self._context)
        self._active_category = initial_category or Category.MAINTENANCE
        self._cursor = 0
        self._last_result: str | None = None  # Last action result (receipt line)
        self._show_info = False  # Info panel for current action
        self._show_help = False  # Help panel showing keybindings
        self._show_preview = False  # Preview panel for Tier 1/2 actions
        self._live: Live | None = None  # Reference to Live context

    def _refresh_view_model(self) -> None:
        self._view_model = app_settings.load_settings_state(self._context)

    def _actions_for_category(self, category: Category | None = None) -> list[SettingsAction]:
        target = category or self._active_category
        return list(self._view_model.actions_by_category.get(target, []))

    def run(self) -> str | None:
        """Run the interactive settings screen.

        Returns:
            Last success message if any action was performed, None otherwise.
        """
        with Live(
            self._render(),
            console=self._console,
            auto_refresh=False,
            transient=True,
        ) as live:
            self._live = live
            while True:
                key = readchar.readkey()

                # Dismiss overlay panels on any key
                if self._show_info or self._show_help or self._show_preview:
                    self._show_info = False
                    self._show_help = False
                    self._show_preview = False
                    live.update(self._render(), refresh=True)
                    continue

                result = self._handle_key(key, live)
                if result is False:
                    return self._last_result  # Return last action result
                if result is True:
                    live.update(self._render(), refresh=True)

    def _handle_key(self, key: str, live: Live) -> bool | None:
        """Handle a keypress.

        Returns:
            True to refresh, False to exit, None for no-op.
        """
        actions = self._actions_for_category()

        # Clear last result on navigation (keep visible for one action cycle)
        if key in (readchar.key.UP, "k", readchar.key.DOWN, "j"):
            self._last_result = None

        if key == readchar.key.UP or key == "k":
            if self._cursor > 0:
                self._cursor -= 1
                return True

        elif key == readchar.key.DOWN or key == "j":
            if self._cursor < len(actions) - 1:
                self._cursor += 1
                return True

        elif key == readchar.key.LEFT or key == "h":
            # Switch to previous category
            categories = list(Category)
            idx = categories.index(self._active_category)
            if idx > 0:
                self._active_category = categories[idx - 1]
                self._cursor = 0
                self._last_result = None
                return True

        elif key == readchar.key.RIGHT or key == "l":
            # Switch to next category
            categories = list(Category)
            idx = categories.index(self._active_category)
            if idx < len(categories) - 1:
                self._active_category = categories[idx + 1]
                self._cursor = 0
                self._last_result = None
                return True

        elif key == readchar.key.TAB:
            # Cycle through categories
            categories = list(Category)
            idx = (categories.index(self._active_category) + 1) % len(categories)
            self._active_category = categories[idx]
            self._cursor = 0
            self._last_result = None
            return True

        elif key == readchar.key.ENTER:
            # Execute selected action (stop Live for clean prompts)
            if actions:
                action = actions[self._cursor]
                live.stop()  # Pause Live for clean prompt output
                try:
                    result = self._execute_action(action)
                    if result:
                        self._last_result = result  # Show as receipt
                finally:
                    live.start()  # Resume Live
                return True

        elif key == "i":
            # Toggle info panel
            self._show_info = True
            return True

        elif key == "?":
            # Show help panel
            self._show_help = True
            return True

        elif key == "p":
            # Preview action (all tiers)
            if actions:
                self._show_preview = True
                return True

        elif key in (readchar.key.ESC, "q", "\x1b", "\x1b\x1b"):
            # Handle Esc key (single or double escape - some macOS systems send double)
            return False

        return None

    def _execute_action(self, action: SettingsAction) -> str | None:
        """Execute a settings action with appropriate confirmation."""
        self._console.print()

        if action.id == "profile_save":
            self._console.print("[bold]Save Personal Profile[/bold]")
            self._console.print()
        elif action.id == "profile_apply":
            self._console.print("[bold]Apply Personal Profile[/bold]")
            self._console.print()

        if action.id == "profile_sync":
            return self._profile_sync()

        if action.id == "generate_support_bundle":
            return self._generate_support_bundle()

        validation = app_settings.validate_settings(
            SettingsValidationRequest(
                action_id=action.id,
                workspace=self._context.workspace,
            )
        )
        if validation and validation.error:
            self._console.print(f"[yellow]{validation.error}[/yellow]")
            Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
            return None

        confirmed = self._confirm_action(action, validation)
        if not confirmed:
            return None

        result = app_settings.apply_settings_change(
            SettingsChangeRequest(
                action_id=action.id,
                workspace=self._context.workspace,
                confirmed=bool(validation and validation.confirmation),
            )
        )
        message = self._handle_action_result(result)
        self._refresh_view_model()
        return message

    def _confirm_action(
        self,
        action: SettingsAction,
        validation: SettingsValidationResult | None,
    ) -> bool:
        if not validation or not validation.confirmation:
            return True
        if validation.confirmation == ConfirmationKind.CONFIRM:
            return self._confirm_with_preview(action, validation)
        if validation.confirmation == ConfirmationKind.TYPE_TO_CONFIRM:
            return self._confirm_factory_reset(validation)
        return True

    def _confirm_with_preview(
        self,
        action: SettingsAction,
        validation: SettingsValidationResult,
    ) -> bool:
        detail = validation.detail
        if isinstance(detail, ProfileSyncPreview):
            self._render_profile_sync_preview(detail)
            return Confirm.ask("Import now?", default=True)

        if validation.message and validation.message.startswith("Create directory?"):
            return self._confirm_create_directory(validation.message)

        if isinstance(detail, MaintenancePreview):
            self._render_maintenance_preview(action, detail)
        else:
            self._console.print(f"[yellow]{action.label}[/yellow]: {action.description}")

        return Confirm.ask("Proceed?")

    def _confirm_create_directory(self, message: str) -> bool:
        from rich import box

        path = message.replace("Create directory?", "").strip()
        self._console.print()
        panel = Panel(
            f"[yellow]Path does not exist:[/yellow]\n  {path}",
            title="[cyan]Create[/cyan] Directory",
            border_style="yellow",
            box=box.ROUNDED,
            padding=(1, 2),
        )
        self._console.print(panel)
        return Confirm.ask("[cyan]Create directory?[/cyan]", default=True)

    def _render_maintenance_preview(
        self, action: SettingsAction, preview: MaintenancePreview
    ) -> None:
        self._console.print(f"[yellow]{action.label}[/yellow]: {action.description}")
        if preview.paths:
            self._console.print("[dim]Affects:[/dim]")
            for path in preview.paths[:3]:
                self._console.print(f"  {path}")
            if len(preview.paths) > 3:
                self._console.print(f"  [dim](+{len(preview.paths) - 3} more)[/dim]")
        if preview.item_count > 0:
            self._console.print(f"[dim]Items:[/dim] {preview.item_count}")
        if preview.bytes_estimate > 0:
            self._console.print(f"[dim]Size:[/dim] ~{_format_bytes(preview.bytes_estimate)}")
        if preview.backup_will_be_created:
            self._console.print("[yellow]Backup will be created[/yellow]")

    def _confirm_factory_reset(self, validation: SettingsValidationResult) -> bool:
        if isinstance(validation.detail, MaintenancePreview):
            paths_list = "\n".join(f"  {path}" for path in validation.detail.paths)
            size_info = (
                f"\nTotal size: ~{_format_bytes(validation.detail.bytes_estimate)}"
                if validation.detail.bytes_estimate > 0
                else ""
            )
            content = (
                "[bold red]WARNING: Factory Reset[/bold red]\n\n"
                "This will remove ALL SCC data:\n"
                f"{paths_list}{size_info}\n\n"
                "This action cannot be undone."
            )
        else:
            content = (
                "[bold red]WARNING: Factory Reset[/bold red]\n\n"
                "This will remove ALL SCC data including:\n"
                "  - Configuration files\n"
                "  - Session history\n"
                "  - Policy exceptions\n"
                "  - Cached data\n"
                "  - Work contexts\n\n"
                "This action cannot be undone."
            )

        self._console.print(Panel(content, border_style="red"))
        phrase = validation.required_phrase or "RESET"
        confirm = Prompt.ask(
            f"Type [bold red]{phrase}[/bold red] to confirm",
            default="",
        )
        if confirm.upper() != phrase:
            self._console.print("[dim]Cancelled[/dim]")
            return False
        return True

    def _handle_action_result(self, result: SettingsActionResult) -> str | None:
        if result.status == SettingsActionStatus.ERROR:
            message = result.message or "Error"
            self._console.print(f"[red]Error: {message}[/red]")
            return None

        if result.details:
            self._render_detail_lines(result)
        elif result.message and result.detail is None:
            if result.status == SettingsActionStatus.SUCCESS:
                self._console.print(f"[green]✓[/green] {result.message}")
            elif result.status == SettingsActionStatus.NOOP:
                self._console.print(f"[yellow]{result.message}[/yellow]")

        if isinstance(result.detail, PathsInfo):
            self._show_paths_info(result.detail)
        elif isinstance(result.detail, VersionInfo):
            self._show_version_info(result.detail)
        elif isinstance(result.detail, ProfileDiffInfo):
            self._profile_diff(result.detail)
        elif isinstance(result.detail, ProfileSyncResult):
            self._render_profile_sync_result(result.detail)
        elif isinstance(result.detail, SupportBundleInfo):
            self._render_support_bundle_result(result.detail)
        elif isinstance(result.detail, DoctorInfo):
            self._render_doctor_result(result.detail)

        if result.warnings:
            for warning in result.warnings:
                self._console.print(f"[yellow]![/yellow] {warning}")

        if result.needs_ack:
            Prompt.ask("[dim]Press Enter to continue[/dim]", default="")

        return result.message

    def _render_detail_lines(self, result: SettingsActionResult) -> None:
        if result.status == SettingsActionStatus.SUCCESS:
            for line in result.details:
                self._console.print(f"[green]✓[/green] {line}")
            return

        if result.status == SettingsActionStatus.NOOP and result.details:
            self._console.print(f"[yellow]{result.details[0]}[/yellow]")
            for line in result.details[1:]:
                self._console.print(f"[dim]{line}[/dim]")
            return

        for line in result.details:
            self._console.print(line)

    def _render_profile_sync_preview(self, preview: ProfileSyncPreview) -> None:
        from rich import box

        lines = [f"[cyan]Import preview from {preview.repo_path}[/cyan]", ""]
        lines.append(f"  {preview.imported} profile(s) will be imported")
        if preview.skipped > 0:
            lines.append(f"  {preview.skipped} profile(s) unchanged")

        self._console.print()
        self._console.print(
            Panel(
                "\n".join(lines),
                title="[cyan]Sync[/cyan] Profiles",
                border_style="bright_black",
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )

    def _show_paths_info(self, paths_info: PathsInfo) -> None:
        """Display SCC file paths information."""
        self._console.print()
        table = Table(title="SCC File Locations", box=None)
        table.add_column("Location", style="cyan")
        table.add_column("Path")
        table.add_column("Size", justify="right")
        table.add_column("Status")

        for path_info in paths_info.paths:
            exists = "✓" if path_info.exists else "✗"
            perms = path_info.permissions if path_info.exists else "-"
            table.add_row(
                path_info.name,
                str(path_info.path),
                path_info.size_human if path_info.exists else "-",
                f"{exists} {perms}",
            )

        table.add_section()
        table.add_row("Total", "", str(paths_info.total_size), "")

        self._console.print(table)
        self._console.print()

    def _generate_support_bundle(self) -> str | None:
        """Generate a support bundle for troubleshooting."""
        from scc_cli.support_bundle import get_default_bundle_path

        self._console.print()
        self._console.print("[bold]Generate Support Bundle[/bold]")
        self._console.print()
        self._console.print(
            "[yellow]Note:[/yellow] The bundle contains diagnostic information with "
            "secrets redacted,\nbut may include file paths and configuration details."
        )
        self._console.print()

        default_path = get_default_bundle_path()
        path_str = Prompt.ask("Save bundle to", default=str(default_path))

        if not path_str:
            self._console.print("[dim]Cancelled[/dim]")
            return None

        output_path = Path(path_str)
        self._console.print("[cyan]Generating bundle...[/cyan]")

        result = app_settings.apply_settings_change(
            SettingsChangeRequest(
                action_id="generate_support_bundle",
                workspace=self._context.workspace,
                payload=SupportBundlePayload(output_path=output_path),
            )
        )
        message = self._handle_action_result(result)
        if result.status == SettingsActionStatus.ERROR:
            Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
        self._refresh_view_model()
        return message

    def _show_version_info(self, version_info: VersionInfo) -> None:
        """Display version information."""
        self._console.print()
        self._console.print(f"[bold cyan]SCC CLI[/bold cyan] version {version_info.version}")
        self._console.print()

    def _profile_diff(self, diff_info: ProfileDiffInfo) -> None:
        """Show diff between profile and workspace settings with visual overlay."""
        from rich import box

        diff = diff_info.diff
        if diff.is_empty:
            self._console.print()
            self._console.print("[green]✓ Profile is in sync with workspace[/green]")
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
            remaining = diff.total_count - (
                rendered_lines - len(set(i.section for i in diff.items))
            )
            lines.append("")
            lines.append(f"  [dim]+ {remaining} more items...[/dim]")

        lines.append("")
        lines.append(f"  [dim]{diff.total_count} difference(s) · Esc close[/dim]")

        content = "\n".join(lines)

        self._console.print()
        self._console.print(
            Panel(
                content,
                title="[bold]Profile Diff[/bold]",
                border_style="bright_black",
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )

        return None

    def _profile_sync(self) -> str | None:
        """Sync profiles with a repository using overlay picker."""
        from pathlib import Path

        from .list_screen import ListItem, ListScreen

        self._refresh_view_model()
        default_path = self._view_model.sync_repo_path

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

        # Show picker with styled title (matching dashboard pattern)
        screen = ListScreen(items, title="[cyan]Sync[/cyan] Profiles")
        selected = screen.run()

        if not selected:
            return None

        repo_path = Path(default_path).expanduser()

        # Handle path change
        if selected == "change_path":
            return self._sync_change_path(default_path)

        # Handle export
        if selected == "export":
            return self._sync_export(repo_path)

        # Handle import
        if selected == "import":
            return self._sync_import(repo_path)

        # Handle full sync
        if selected == "full_sync":
            return self._sync_full(repo_path)

        return None

    def _sync_change_path(self, current_path: str) -> str | None:
        """Handle path editing for sync."""
        from rich import box

        self._console.print()
        panel = Panel(
            f"[dim]Current:[/dim] {current_path}\n\n"
            "[dim]Enter new path or press Enter to keep current[/dim]",
            title="[cyan]Edit[/cyan] Repository Path",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(1, 2),
        )
        self._console.print(panel)
        new_path = Prompt.ask("[cyan]Path[/cyan]", default=current_path)

        if new_path and new_path != current_path:
            result = app_settings.apply_settings_change(
                SettingsChangeRequest(
                    action_id="profile_sync",
                    workspace=self._context.workspace,
                    payload=ProfileSyncPathPayload(new_path=new_path),
                )
            )
            self._handle_action_result(result)
            self._refresh_view_model()

        return self._profile_sync()

    def _sync_export(self, repo_path: Path) -> str | None:
        """Export profiles to repository."""
        payload = ProfileSyncPayload(mode=ProfileSyncMode.EXPORT, repo_path=repo_path)
        validation = app_settings.validate_settings(
            SettingsValidationRequest(
                action_id="profile_sync",
                workspace=self._context.workspace,
                payload=payload,
            )
        )
        if validation and validation.error:
            self._console.print(f"[yellow]{validation.error}[/yellow]")
            Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
            return None

        create_dir = False
        if (
            validation
            and validation.confirmation == ConfirmationKind.CONFIRM
            and validation.message
        ):
            create_dir = self._confirm_create_directory(validation.message)
            if not create_dir:
                return None

        self._console.print(f"[dim]Exporting to {repo_path}...[/dim]")
        payload = ProfileSyncPayload(
            mode=ProfileSyncMode.EXPORT,
            repo_path=repo_path,
            create_dir=create_dir,
        )
        result = app_settings.apply_settings_change(
            SettingsChangeRequest(
                action_id="profile_sync",
                workspace=self._context.workspace,
                payload=payload,
            )
        )
        message = self._handle_action_result(result)
        self._refresh_view_model()
        return message

    def _sync_import(self, repo_path: Path) -> str | None:
        """Import profiles from repository with preview."""
        from rich import box

        self._console.print(f"[dim]Checking {repo_path}...[/dim]")
        payload = ProfileSyncPayload(mode=ProfileSyncMode.IMPORT, repo_path=repo_path)
        validation = app_settings.validate_settings(
            SettingsValidationRequest(
                action_id="profile_sync",
                workspace=self._context.workspace,
                payload=payload,
            )
        )

        if validation and validation.error:
            self._console.print(
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
            self._render_profile_sync_preview(validation.detail)
            confirmed = Confirm.ask("Import now?", default=True)
            if not confirmed:
                return None

        result = app_settings.apply_settings_change(
            SettingsChangeRequest(
                action_id="profile_sync",
                workspace=self._context.workspace,
                payload=payload,
                confirmed=confirmed,
            )
        )
        message = self._handle_action_result(result)
        self._refresh_view_model()
        return message

    def _sync_full(self, repo_path: Path) -> str | None:
        """Full sync: import then export."""
        self._console.print(f"[dim]Full sync with {repo_path}...[/dim]")
        payload = ProfileSyncPayload(mode=ProfileSyncMode.FULL_SYNC, repo_path=repo_path)
        result = app_settings.apply_settings_change(
            SettingsChangeRequest(
                action_id="profile_sync",
                workspace=self._context.workspace,
                payload=payload,
            )
        )
        message = self._handle_action_result(result)
        self._refresh_view_model()
        return message

    def _render_profile_sync_result(self, result: ProfileSyncResult) -> None:
        from rich import box

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

        self._console.print()
        self._console.print(
            Panel(
                "\n".join(lines),
                title="[cyan]Sync[/cyan] Profiles",
                border_style="bright_black",
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )

    def _render_support_bundle_result(self, info: SupportBundleInfo) -> None:
        self._console.print()
        self._console.print(f"[green]✓[/green] Bundle created: {info.output_path}")

    def _render_doctor_result(self, info: DoctorInfo) -> None:
        from scc_cli.doctor import render_doctor_results

        render_doctor_results(self._console, info.result)

    def _render(self) -> RenderableType:
        """Render the settings screen."""
        metrics = get_layout_metrics(self._console, max_width=104)
        inner_width = (
            metrics.inner_width(padding_x=1, border=2)
            if metrics.apply
            else self._console.size.width
        )

        header_info = self._view_model.header

        header = Text()
        header.append("Profile", style="dim")
        header.append(": ", style="dim")
        header.append(header_info.profile_name, style="cyan")
        if header_info.org_name:
            header.append(f" {Indicators.get('VERTICAL_LINE')} ", style="dim")
            header.append("Org", style="dim")
            header.append(": ", style="dim")
            header.append(header_info.org_name, style="cyan")
        header.append("\n")

        from rich import box

        # Two-column layout
        layout = Table.grid(padding=(0, 2))
        layout.add_column()  # Categories
        layout.add_column()  # Actions

        # Render category list
        cat_text = Text()
        for cat in Category:
            prefix = Indicators.get("CURSOR") + " " if cat == self._active_category else "  "
            style = "bold cyan" if cat == self._active_category else "dim"
            cat_text.append(prefix, style="cyan" if cat == self._active_category else "")
            cat_text.append(cat.name.title() + "\n", style=style)

        # Render action list for current category
        actions = self._actions_for_category()
        action_text = Text()
        label_width = max((len(action.label) for action in actions), default=0)
        separator_width = max(18, min(36, label_width + 8))

        for i, action in enumerate(actions):
            is_selected = i == self._cursor

            # Add separator before Factory reset (last action in Maintenance)
            if action.id == "factory_reset":
                line = Indicators.get("HORIZONTAL_LINE") * separator_width
                action_text.append(f"  {line}\n", style="dim")

            prefix = Indicators.get("CURSOR") + " " if is_selected else "  "

            action_text.append(prefix, style="cyan" if is_selected else "")
            action_text.append(
                action.label.ljust(label_width),
                style="bold" if is_selected else "",
            )
            action_text.append("  ")
            action_text.append(_get_risk_badge(action.risk_tier))
            action_text.append("\n")
            action_text.append(f"  {action.description}\n", style="dim")

        layout.add_row(
            Panel(
                cat_text,
                title="[dim]Categories[/dim]",
                border_style="bright_black",
                box=box.ROUNDED,
                padding=(0, 1),
            ),
            Panel(
                action_text,
                title="[dim]Actions[/dim]",
                border_style="bright_black",
                box=box.ROUNDED,
                padding=(0, 1),
            ),
        )

        # Receipt line (shows last action result)
        receipt = Text()
        if self._last_result:
            receipt.append("✓ ", style="green")
            receipt.append(self._last_result, style="green")
            receipt.append("\n")

        # Footer hints
        hint_pairs = [
            ("↑↓", "navigate"),
            ("←→/Tab", "switch category"),
            ("Enter", "select"),
            ("i", "info"),
            ("p", "preview"),
            ("?", "help"),
            ("Esc", "back"),
        ]
        hints = Text()
        for i, (key, hint_action) in enumerate(hint_pairs):
            if i > 0:
                hints.append(" · ", style="dim")
            hints.append(key, style="cyan bold")
            hints.append(" ", style="dim")
            hints.append(hint_action, style="dim")

        separator_width = max(32, min(72, inner_width))
        separator = Text(Indicators.get("HORIZONTAL_LINE") * separator_width, style="dim")
        hint_block = Group(separator, hints)

        # Build full screen content
        content = (
            Group(header, layout, receipt, hint_block)
            if self._last_result
            else Group(header, layout, hint_block)
        )

        # Help panel overlay
        if self._show_help:
            help_text = Text()
            help_text.append("Keyboard Shortcuts\n\n", style="bold")
            help_text.append("↑/k  ↓/j    ", style="cyan")
            help_text.append("Navigate actions\n")
            help_text.append("←/h  →/l    ", style="cyan")
            help_text.append("Switch category\n")
            help_text.append("Tab         ", style="cyan")
            help_text.append("Cycle categories\n")
            help_text.append("Enter       ", style="cyan")
            help_text.append("Execute action\n")
            help_text.append("i           ", style="cyan")
            help_text.append("Show action info\n")
            help_text.append("p           ", style="cyan")
            help_text.append("Preview (Tier 1/2)\n")
            help_text.append("Esc/q       ", style="cyan")
            help_text.append("Back to dashboard\n")
            help_text.append("?           ", style="cyan")
            help_text.append("Show this help\n")
            help_panel = Panel(
                help_text,
                title="[cyan]Help[/cyan]",
                border_style="bright_black",
                box=box.ROUNDED,
            )
            dismiss = Text("\n[dim]Press any key to dismiss[/dim]")
            content = Group(header, layout, help_panel, dismiss)

        # Info panel overlay
        elif self._show_info and actions:
            action = actions[self._cursor]
            info_text = Text()
            info_text.append(action.label, style="bold")
            info_text.append(f"\n\n{action.description}\n\nRisk: ")
            info_text.append(_get_risk_badge(action.risk_tier))
            info = Panel(
                info_text,
                title="[cyan]Action Info[/cyan]",
                border_style="bright_black",
                box=box.ROUNDED,
            )
            dismiss = Text("\n[dim]Press any key to dismiss[/dim]")
            content = Group(header, layout, info, dismiss)

        # Preview panel overlay
        elif self._show_preview and actions:
            action = actions[self._cursor]
            validation = app_settings.validate_settings(
                SettingsValidationRequest(
                    action_id=action.id,
                    workspace=self._context.workspace,
                )
            )
            preview_text = Text()
            if validation and isinstance(validation.detail, MaintenancePreview):
                preview = validation.detail
                preview_text.append(f"{action.label}\n\n", style="bold")
                preview_text.append("Risk: ")
                preview_text.append(_get_risk_badge(preview.risk_tier))
                preview_text.append("\n\n")

                if preview.paths:
                    preview_text.append("Affects:\n", style="dim")
                    for path in preview.paths[:5]:
                        preview_text.append(f"  {path}\n")
                    if len(preview.paths) > 5:
                        preview_text.append(f"  (+{len(preview.paths) - 5} more)\n", style="dim")

                if preview.item_count > 0:
                    preview_text.append(f"\nItems: {preview.item_count}\n")

                if preview.bytes_estimate > 0:
                    preview_text.append(f"Size: ~{_format_bytes(preview.bytes_estimate)}\n")

                if preview.backup_will_be_created:
                    preview_text.append("\n[yellow]Backup will be created[/yellow]\n")
            else:
                preview_text.append(f"Unable to preview {action.label}")

            preview_panel = Panel(
                preview_text,
                title="[yellow]Preview[/yellow]",
                border_style="bright_black",
                box=box.ROUNDED,
            )
            dismiss = Text("\n[dim]Press any key to dismiss[/dim]")
            content = Group(header, layout, preview_panel, dismiss)

        title = Text()
        title.append("Settings", style="bold cyan")
        title.append(" & ", style="dim")
        title.append("Maintenance", style="dim")

        panel = Panel(
            content,
            title=title,
            border_style="bright_black",
            box=box.ROUNDED,
            padding=(0, 1),
            width=metrics.content_width if metrics.apply else None,
        )
        return apply_layout(panel, metrics) if metrics.apply else panel


def run_settings_screen(initial_category: str | None = None) -> str | None:
    """Run the settings screen and return result.

    This is the main entry point called from the dashboard orchestrator.

    Args:
        initial_category: Optional category name to start on (e.g., "PROFILES").
                          Defaults to "MAINTENANCE" if not specified or invalid.

    Returns:
        Success message if an action was performed, None if cancelled.
    """
    # Parse category from string if provided
    category: Category | None = None
    if initial_category:
        try:
            category = Category[initial_category.upper()]
        except KeyError:
            pass  # Invalid category, use default

    screen = SettingsScreen(initial_category=category)
    return screen.run()
