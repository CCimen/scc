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

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

import readchar
from rich.console import Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.text import Text

from ..config import get_organization_name, get_selected_profile
from ..console import get_err_console
from ..core.maintenance import (
    RiskTier,
    clear_cache,
    clear_contexts,
    delete_all_sessions,
    factory_reset,
    get_paths,
    get_total_size,
    preview_operation,
    prune_containers,
    prune_sessions,
    reset_config,
    reset_exceptions,
)
from ..theme import Indicators

if TYPE_CHECKING:
    from pathlib import Path


class Category(Enum):
    """Categories for the settings screen."""

    MAINTENANCE = auto()
    PROFILES = auto()
    DIAGNOSTICS = auto()
    ABOUT = auto()


@dataclass
class SettingsAction:
    """Represents a settings action with its metadata.

    Attributes:
        id: Unique identifier for the action.
        label: Display label for the action.
        description: Brief description of what the action does.
        risk_tier: Risk level (affects confirmation behavior).
        category: Which category this action belongs to.
    """

    id: str
    label: str
    description: str
    risk_tier: RiskTier
    category: Category


# Define all available settings actions
SETTINGS_ACTIONS: list[SettingsAction] = [
    # Maintenance actions (Tier 0 = Safe)
    SettingsAction(
        id="clear_cache",
        label="Clear cache",
        description="Remove regenerable cache files",
        risk_tier=RiskTier.SAFE,
        category=Category.MAINTENANCE,
    ),
    # Tier 1 = Changes State
    SettingsAction(
        id="clear_contexts",
        label="Clear contexts",
        description="Clear recent work contexts",
        risk_tier=RiskTier.CHANGES_STATE,
        category=Category.MAINTENANCE,
    ),
    SettingsAction(
        id="prune_containers",
        label="Prune containers",
        description="Remove stopped Docker containers",
        risk_tier=RiskTier.CHANGES_STATE,
        category=Category.MAINTENANCE,
    ),
    SettingsAction(
        id="prune_sessions",
        label="Prune sessions",
        description="Remove old sessions (keeps recent)",
        risk_tier=RiskTier.CHANGES_STATE,
        category=Category.MAINTENANCE,
    ),
    # Tier 2 = Destructive
    SettingsAction(
        id="reset_exceptions",
        label="Reset exceptions",
        description="Clear all policy exceptions",
        risk_tier=RiskTier.DESTRUCTIVE,
        category=Category.MAINTENANCE,
    ),
    SettingsAction(
        id="delete_sessions",
        label="Delete all sessions",
        description="Remove entire session history",
        risk_tier=RiskTier.DESTRUCTIVE,
        category=Category.MAINTENANCE,
    ),
    SettingsAction(
        id="reset_config",
        label="Reset configuration",
        description="Reset to defaults (requires setup)",
        risk_tier=RiskTier.DESTRUCTIVE,
        category=Category.MAINTENANCE,
    ),
    # Tier 3 = Factory Reset
    SettingsAction(
        id="factory_reset",
        label="Factory reset",
        description="Remove all SCC data",
        risk_tier=RiskTier.FACTORY_RESET,
        category=Category.MAINTENANCE,
    ),
    # Profiles (Tier 0 = Safe for read-only, Tier 1 for state changes)
    SettingsAction(
        id="profile_save",
        label="Save profile",
        description="Capture current workspace settings",
        risk_tier=RiskTier.SAFE,
        category=Category.PROFILES,
    ),
    SettingsAction(
        id="profile_apply",
        label="Apply profile",
        description="Restore saved settings to workspace",
        risk_tier=RiskTier.CHANGES_STATE,
        category=Category.PROFILES,
    ),
    SettingsAction(
        id="profile_diff",
        label="Show diff",
        description="Compare profile vs workspace",
        risk_tier=RiskTier.SAFE,
        category=Category.PROFILES,
    ),
    SettingsAction(
        id="profile_sync",
        label="Sync profiles",
        description="Export/import via repo",
        risk_tier=RiskTier.SAFE,  # Opens picker with internal confirmations
        category=Category.PROFILES,
    ),
    # Diagnostics
    SettingsAction(
        id="run_doctor",
        label="Run doctor",
        description="Check prerequisites and system health",
        risk_tier=RiskTier.SAFE,
        category=Category.DIAGNOSTICS,
    ),
    SettingsAction(
        id="generate_support_bundle",
        label="Generate support bundle",
        description="Create diagnostic bundle for troubleshooting",
        risk_tier=RiskTier.SAFE,
        category=Category.DIAGNOSTICS,
    ),
    # About
    SettingsAction(
        id="show_paths",
        label="Show paths",
        description="Show SCC file locations",
        risk_tier=RiskTier.SAFE,
        category=Category.ABOUT,
    ),
    SettingsAction(
        id="show_version",
        label="Show version",
        description="Show build info and CLI version",
        risk_tier=RiskTier.SAFE,
        category=Category.ABOUT,
    ),
]


def _get_risk_badge(tier: RiskTier) -> Text:
    """Get a color-coded risk badge for display.

    Uses both color and text/symbols for accessibility.
    Returns a Text object (not markup string) for proper rendering.
    """
    match tier:
        case RiskTier.SAFE:
            return Text.from_markup("[green]SAFE [dim]✓[/dim][/green]")
        case RiskTier.CHANGES_STATE:
            return Text.from_markup("[yellow]CHANGES STATE [dim]![/dim][/yellow]")
        case RiskTier.DESTRUCTIVE:
            return Text.from_markup("[red]DESTRUCTIVE [dim]!![/dim][/red]")
        case RiskTier.FACTORY_RESET:
            return Text.from_markup("[bold red]VERY DESTRUCTIVE [dim]☠[/dim][/bold red]")
        case _:
            return Text("UNKNOWN")


def _get_actions_for_category(category: Category) -> list[SettingsAction]:
    """Get all actions for a given category."""
    return [a for a in SETTINGS_ACTIONS if a.category == category]


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
        self._active_category = initial_category or Category.MAINTENANCE
        self._cursor = 0
        self._last_result: str | None = None  # Last action result (receipt line)
        self._show_info = False  # Info panel for current action
        self._show_help = False  # Help panel showing keybindings
        self._show_preview = False  # Preview panel for Tier 1/2 actions
        self._live: Live | None = None  # Reference to Live context

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
        actions = _get_actions_for_category(self._active_category)

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
        """Execute a settings action with appropriate confirmation.

        Returns:
            Success message if action was performed, None if cancelled.
        """
        # Exit Live context for confirmation prompts
        self._console.print()

        # Tier 0 (Safe) - no confirmation needed
        if action.risk_tier == RiskTier.SAFE:
            return self._run_action(action)

        # Tier 1-2 - Y/N confirmation with affected paths from data
        if action.risk_tier in (RiskTier.CHANGES_STATE, RiskTier.DESTRUCTIVE):
            # Get preview data to show affected paths
            try:
                preview = preview_operation(action.id)
                self._console.print(f"[yellow]{action.label}[/yellow]: {action.description}")
                if preview.paths:
                    self._console.print("[dim]Affects:[/dim]")
                    for path in preview.paths[:3]:  # Limit to 3 paths
                        self._console.print(f"  {path}")
                    if len(preview.paths) > 3:
                        self._console.print(f"  [dim](+{len(preview.paths) - 3} more)[/dim]")
                if preview.item_count > 0:
                    self._console.print(f"[dim]Items:[/dim] {preview.item_count}")
                if preview.bytes_estimate > 0:
                    self._console.print(
                        f"[dim]Size:[/dim] ~{_format_bytes(preview.bytes_estimate)}"
                    )
                if preview.backup_will_be_created:
                    self._console.print("[yellow]Backup will be created[/yellow]")
            except Exception:
                # Fall back to simple confirmation
                self._console.print(f"[yellow]{action.label}[/yellow]: {action.description}")

            if not Confirm.ask("Proceed?"):
                return None
            return self._run_action(action)

        # Tier 3 (Factory Reset) - type to confirm with full impact from data
        if action.risk_tier == RiskTier.FACTORY_RESET:
            try:
                preview = preview_operation(action.id)
                paths_list = "\n".join(f"  {p}" for p in preview.paths)
                size_info = (
                    f"\nTotal size: ~{_format_bytes(preview.bytes_estimate)}"
                    if preview.bytes_estimate > 0
                    else ""
                )
                content = (
                    "[bold red]WARNING: Factory Reset[/bold red]\n\n"
                    "This will remove ALL SCC data:\n"
                    f"{paths_list}{size_info}\n\n"
                    "This action cannot be undone."
                )
            except Exception:
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
            confirm = Prompt.ask(
                "Type [bold red]RESET[/bold red] to confirm",
                default="",
            )
            if confirm.upper() != "RESET":
                self._console.print("[dim]Cancelled[/dim]")
                return None
            return self._run_action(action)

        return None

    def _run_action(self, action: SettingsAction) -> str | None:
        """Execute the actual action and return result message."""
        try:
            match action.id:
                case "clear_cache":
                    result = clear_cache()
                    return f"Cache cleared: {result.bytes_freed_human}"

                case "clear_contexts":
                    result = clear_contexts()
                    return f"Cleared {result.removed_count} contexts"

                case "prune_containers":
                    result = prune_containers(dry_run=False)
                    return f"Pruned {result.removed_count} containers"

                case "prune_sessions":
                    result = prune_sessions(older_than_days=30, keep_n=20, dry_run=False)
                    return f"Pruned {result.removed_count} sessions"

                case "reset_exceptions":
                    result = reset_exceptions(scope="all")
                    return f"Reset {result.removed_count} exceptions"

                case "delete_sessions":
                    result = delete_all_sessions()
                    return f"Deleted {result.removed_count} sessions"

                case "reset_config":
                    result = reset_config()
                    return "Configuration reset. Run 'scc setup' to reconfigure."

                case "factory_reset":
                    _results = factory_reset()  # Returns list[ResetResult]
                    return "Factory reset complete. Run 'scc setup' to reconfigure."

                case "profile_save":
                    return self._profile_save()

                case "profile_apply":
                    return self._profile_apply()

                case "profile_diff":
                    return self._profile_diff()

                case "profile_sync":
                    return self._profile_sync()

                case "run_doctor":
                    # Run doctor using core function (not Typer command)
                    from pathlib import Path

                    from ..doctor.render import run_doctor as core_run_doctor

                    self._console.print()
                    _doctor_result = core_run_doctor(workspace=Path.cwd())
                    Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
                    return None  # No toast, doctor has its own output

                case "generate_support_bundle":
                    return self._generate_support_bundle()

                case "show_paths":
                    self._show_paths_info()
                    return None  # No toast

                case "show_version":
                    self._show_version_info()
                    return None  # No toast

                case _:
                    return None

        except Exception as e:
            self._console.print(f"[red]Error: {e}[/red]")
            return None

    def _show_paths_info(self) -> None:
        """Display SCC file paths information."""
        paths = get_paths()
        total = get_total_size()

        self._console.print()
        table = Table(title="SCC File Locations", box=None)
        table.add_column("Location", style="cyan")
        table.add_column("Path")
        table.add_column("Size", justify="right")
        table.add_column("Status")

        for p in paths:
            exists = "✓" if p.exists else "✗"
            perms = p.permissions if p.exists else "-"
            table.add_row(
                p.name,
                str(p.path),
                p.size_human if p.exists else "-",
                f"{exists} {perms}",
            )

        table.add_section()
        table.add_row("Total", "", str(total), "")

        self._console.print(table)
        self._console.print()
        Prompt.ask("[dim]Press Enter to continue[/dim]", default="")

    def _generate_support_bundle(self) -> str | None:
        """Generate a support bundle for troubleshooting.

        Prompts for destination path, shows warning about sensitive data,
        and creates the bundle.

        Returns:
            Success message with bundle path, or None if cancelled.
        """
        from pathlib import Path

        from ..commands.support import create_bundle, get_default_bundle_path

        self._console.print()
        self._console.print("[bold]Generate Support Bundle[/bold]")
        self._console.print()
        self._console.print(
            "[yellow]Note:[/yellow] The bundle contains diagnostic information with "
            "secrets redacted,\nbut may include file paths and configuration details."
        )
        self._console.print()

        # Get default path
        default_path = get_default_bundle_path()

        # Prompt for path
        path_str = Prompt.ask(
            "Save bundle to",
            default=str(default_path),
        )

        if not path_str:
            self._console.print("[dim]Cancelled[/dim]")
            return None

        output_path = Path(path_str)

        # Create the bundle
        self._console.print("[cyan]Generating bundle...[/cyan]")
        try:
            create_bundle(output_path=output_path)
            self._console.print()
            self._console.print(f"[green]✓[/green] Bundle created: {output_path}")
            Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
            return f"Support bundle saved to {output_path.name}"
        except Exception as e:
            self._console.print(f"[red]Error creating bundle: {e}[/red]")
            Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
            return None

    def _show_version_info(self) -> None:
        """Display version information."""
        from importlib.metadata import PackageNotFoundError
        from importlib.metadata import version as get_version

        self._console.print()
        try:
            version = get_version("scc-cli")
        except PackageNotFoundError:
            version = "unknown"

        self._console.print(f"[bold cyan]SCC CLI[/bold cyan] version {version}")
        self._console.print()
        Prompt.ask("[dim]Press Enter to continue[/dim]", default="")

    def _profile_save(self) -> str | None:
        """Save current workspace settings as a personal profile."""
        from pathlib import Path

        from ..core.personal_profiles import (
            compute_fingerprints,
            load_workspace_mcp,
            load_workspace_settings,
            save_applied_state,
            save_personal_profile,
        )

        workspace = Path.cwd()
        self._console.print()
        self._console.print("[bold]Save Personal Profile[/bold]")
        self._console.print()

        # Load current workspace settings
        settings = load_workspace_settings(workspace)
        mcp = load_workspace_mcp(workspace)

        if not settings and not mcp:
            self._console.print("[yellow]No workspace settings found to save.[/yellow]")
            self._console.print("[dim]Create .claude/settings.local.json or .mcp.json first.[/dim]")
            Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
            return None

        # Save the profile
        profile = save_personal_profile(workspace, settings, mcp)

        # Save applied state for drift detection
        fingerprints = compute_fingerprints(workspace)
        save_applied_state(workspace, profile.profile_id, fingerprints)

        self._console.print(f"[green]✓[/green] Profile saved: {profile.path.name}")
        Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
        return "Profile saved"

    def _profile_apply(self) -> str | None:
        """Apply saved profile to current workspace."""
        from pathlib import Path

        from ..core.personal_profiles import (
            compute_fingerprints,
            load_personal_profile,
            load_workspace_mcp,
            load_workspace_settings,
            merge_personal_mcp,
            merge_personal_settings,
            save_applied_state,
            write_workspace_mcp,
            write_workspace_settings,
        )

        workspace = Path.cwd()
        self._console.print()
        self._console.print("[bold]Apply Personal Profile[/bold]")
        self._console.print()

        # Load profile
        profile = load_personal_profile(workspace)
        if not profile:
            self._console.print("[yellow]No profile saved for this workspace.[/yellow]")
            self._console.print("[dim]Use 'Save profile' first.[/dim]")
            Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
            return None

        # Load current workspace settings
        current_settings = load_workspace_settings(workspace) or {}
        current_mcp = load_workspace_mcp(workspace) or {}

        # Merge profile into workspace
        if profile.settings:
            merged_settings = merge_personal_settings(workspace, current_settings, profile.settings)
            write_workspace_settings(workspace, merged_settings)

        if profile.mcp:
            merged_mcp = merge_personal_mcp(current_mcp, profile.mcp)
            write_workspace_mcp(workspace, merged_mcp)

        # Update applied state
        fingerprints = compute_fingerprints(workspace)
        save_applied_state(workspace, profile.profile_id, fingerprints)

        self._console.print("[green]✓[/green] Profile applied to workspace")
        Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
        return "Profile applied"

    def _profile_diff(self) -> str | None:
        """Show diff between profile and workspace settings with visual overlay."""
        from pathlib import Path

        from rich import box

        from ..core.personal_profiles import (
            compute_structured_diff,
            load_personal_profile,
            load_workspace_mcp,
            load_workspace_settings,
        )

        workspace = Path.cwd()

        # Load profile
        profile = load_personal_profile(workspace)
        if not profile:
            self._console.print()
            self._console.print("[yellow]No profile saved for this workspace.[/yellow]")
            Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
            return None

        # Load current workspace settings
        current_settings = load_workspace_settings(workspace) or {}
        current_mcp = load_workspace_mcp(workspace) or {}

        # Compute structured diff
        diff = compute_structured_diff(
            workspace_settings=current_settings,
            profile_settings=profile.settings,
            workspace_mcp=current_mcp,
            profile_mcp=profile.mcp,
        )

        if diff.is_empty:
            self._console.print()
            self._console.print("[green]✓ Profile is in sync with workspace[/green]")
            Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
            return None

        # Build diff content grouped by section
        lines: list[str] = []
        current_section = ""
        rendered_lines = 0
        max_lines = 12  # Smart fallback threshold
        truncated = False

        # Status indicators
        indicators = {
            "added": "[green]+[/green]",
            "removed": "[red]−[/red]",
            "modified": "[yellow]~[/yellow]",
        }

        # Section display names
        section_names = {
            "plugins": "plugins",
            "mcp_servers": "mcp_servers",
            "marketplaces": "marketplaces",
        }

        for item in diff.items:
            # Check if we need to truncate
            if rendered_lines >= max_lines and not truncated:
                truncated = True
                break

            # Add section header if new section
            if item.section != current_section:
                if current_section:
                    lines.append("")  # Blank line between sections
                    rendered_lines += 1
                lines.append(f"  [bold]{section_names.get(item.section, item.section)}[/bold]")
                rendered_lines += 1
                current_section = item.section

            # Add item with indicator
            indicator = indicators.get(item.status, " ")
            modifier = "(modified)" if item.status == "modified" else ""
            if modifier:
                lines.append(f"    {indicator} {item.name}  [dim]{modifier}[/dim]")
            else:
                lines.append(f"    {indicator} {item.name}")
            rendered_lines += 1

        # Add truncation indicator if needed
        if truncated:
            remaining = diff.total_count - (
                rendered_lines - len(set(i.section for i in diff.items))
            )
            lines.append("")
            lines.append(f"  [dim]+ {remaining} more items...[/dim]")

        # Add footer
        lines.append("")
        lines.append(f"  [dim]{diff.total_count} difference(s) · Esc close[/dim]")

        # Create panel content
        content = "\n".join(lines)

        # Render the diff overlay
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

        Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
        return None

    def _profile_sync(self) -> str | None:
        """Sync profiles with a repository using overlay picker."""
        from pathlib import Path

        from .list_screen import ListItem, ListScreen

        # Get default/last-used repo path
        default_path = self._get_sync_repo_path()

        # Build picker items: path row + operations
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

    def _get_sync_repo_path(self) -> str:
        """Get the default/last-used sync repository path."""
        from .. import config as scc_config

        # Try to get from user config
        try:
            cfg = scc_config.load_user_config()
            last_repo = cfg.get("sync", {}).get("last_repo")
            if last_repo:
                return str(last_repo)
        except Exception:
            pass

        # Default path
        return "~/dotfiles/scc-profiles"

    def _save_sync_repo_path(self, path: str) -> None:
        """Save the sync repository path to user config."""
        from .. import config as scc_config

        try:
            cfg = scc_config.load_user_config()
            if "sync" not in cfg:
                cfg["sync"] = {}
            cfg["sync"]["last_repo"] = path
            scc_config.save_user_config(cfg)
        except Exception:
            pass  # Non-critical, ignore errors

    def _sync_change_path(self, current_path: str) -> str | None:
        """Handle path editing for sync."""
        from rich import box

        # Show styled panel for path input
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
            self._save_sync_repo_path(new_path)
            self._console.print(f"\n[green]✓[/green] Path updated to: {new_path}")
            Prompt.ask("[dim]Press Enter to continue[/dim]", default="")

        # Return to sync picker with new path
        return self._profile_sync()

    def _sync_export(self, repo_path: Path) -> str | None:
        """Export profiles to repository."""

        from rich import box

        from ..core.personal_profiles import (
            export_profiles_to_repo,
            list_personal_profiles,
        )

        self._console.print()

        # Check if we have profiles to export
        profiles = list_personal_profiles()
        if not profiles:
            self._console.print(
                Panel(
                    "[yellow]✗ No profiles to export[/yellow]\n\n"
                    "Save a profile first with 'Save profile' action.",
                    title="[cyan]Sync[/cyan] Profiles",
                    border_style="bright_black",
                    box=box.ROUNDED,
                    padding=(1, 2),
                )
            )
            Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
            return None

        # Check if directory exists, offer to create
        if not repo_path.exists():
            self._console.print()
            self._console.print(
                Panel(
                    f"[yellow]Path does not exist:[/yellow]\n  {repo_path}",
                    title="[cyan]Create[/cyan] Directory",
                    border_style="yellow",
                    box=box.ROUNDED,
                    padding=(1, 2),
                )
            )
            create = Confirm.ask("[cyan]Create directory?[/cyan]", default=True)
            if not create:
                return None
            repo_path.mkdir(parents=True, exist_ok=True)
            self._console.print(f"[green]✓[/green] Created {repo_path}")

        # Export
        self._console.print(f"[dim]Exporting to {repo_path}...[/dim]")
        result = export_profiles_to_repo(repo_path, profiles)

        # Show result
        lines = [f"[green]✓ Exported {result.exported} profile(s)[/green]"]
        for profile in profiles:
            lines.append(f"  [green]+[/green] {profile.repo_id}")

        if result.warnings:
            lines.append("")
            for warning in result.warnings:
                lines.append(f"  [yellow]![/yellow] {warning}")

        # Add hint about local-only operation
        lines.append("")
        lines.append("[dim]Files written locally · no git commit/push[/dim]")
        lines.append("[dim]For git: scc profile export --repo PATH --commit --push[/dim]")

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

        # Save path for next time
        self._save_sync_repo_path(str(repo_path))

        Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
        return f"Exported {result.exported} profile(s)"

    def _sync_import(self, repo_path: Path) -> str | None:
        """Import profiles from repository with preview."""

        from rich import box

        from ..core.personal_profiles import import_profiles_from_repo

        self._console.print()

        # Check if repo exists
        if not repo_path.exists():
            self._console.print(
                Panel(
                    f"[yellow]✗ Path not found[/yellow]\n\n{repo_path}",
                    title="[cyan]Sync[/cyan] Profiles",
                    border_style="bright_black",
                    box=box.ROUNDED,
                    padding=(1, 2),
                )
            )
            Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
            return None

        # Preview (dry-run)
        self._console.print(f"[dim]Checking {repo_path}...[/dim]")
        preview = import_profiles_from_repo(repo_path, dry_run=True)

        if preview.imported == 0 and preview.skipped == 0:
            self._console.print()
            self._console.print(
                Panel(
                    "[dim]No profiles found in repository.[/dim]",
                    title="[cyan]Sync[/cyan] Profiles",
                    border_style="bright_black",
                    box=box.ROUNDED,
                    padding=(1, 2),
                )
            )
            Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
            return None

        # Show preview and ask for confirmation
        lines = [f"[cyan]Import preview from {repo_path}[/cyan]", ""]
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

        # Confirm import
        if not Confirm.ask("Import now?", default=True):
            return None

        # Actually import
        result = import_profiles_from_repo(repo_path, dry_run=False)

        # Show result panel
        lines = [f"[green]✓ Imported {result.imported} profile(s)[/green]"]
        lines.append("")
        lines.append("[dim]Profiles copied locally · no git pull[/dim]")
        lines.append("[dim]For git: scc profile import --repo PATH --pull[/dim]")

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

        # Save path for next time
        self._save_sync_repo_path(str(repo_path))

        Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
        return f"Imported {result.imported} profile(s)"

    def _sync_full(self, repo_path: Path) -> str | None:
        """Full sync: import then export."""

        from rich import box

        from ..core.personal_profiles import (
            export_profiles_to_repo,
            import_profiles_from_repo,
            list_personal_profiles,
        )

        self._console.print()
        self._console.print(f"[dim]Full sync with {repo_path}...[/dim]")

        # Check if repo exists for import
        imported = 0
        if repo_path.exists():
            self._console.print("[dim]Step 1: Importing...[/dim]")
            import_result = import_profiles_from_repo(repo_path, dry_run=False)
            imported = import_result.imported
        else:
            self._console.print("[dim]Step 1: Skipped (repo not found)[/dim]")
            repo_path.mkdir(parents=True, exist_ok=True)

        # Export
        self._console.print("[dim]Step 2: Exporting...[/dim]")
        profiles = list_personal_profiles()
        exported = 0
        if profiles:
            export_result = export_profiles_to_repo(repo_path, profiles)
            exported = export_result.exported

        # Show result
        self._console.print()
        self._console.print(
            Panel(
                f"[green]✓ Sync complete[/green]\n\n"
                f"  Imported: {imported} profile(s)\n"
                f"  Exported: {exported} profile(s)\n\n"
                f"[dim]Files synced locally · no git operations[/dim]\n"
                f"[dim]For git: scc profile sync --repo PATH --pull --commit --push[/dim]",
                title="[cyan]Sync[/cyan] Profiles",
                border_style="bright_black",
                box=box.ROUNDED,
                padding=(1, 2),
            )
        )

        # Save path for next time
        self._save_sync_repo_path(str(repo_path))

        Prompt.ask("[dim]Press Enter to continue[/dim]", default="")
        return f"Synced: {imported} imported, {exported} exported"

    def _render(self) -> RenderableType:
        """Render the settings screen."""
        # Profile header
        profile = get_selected_profile()
        org = get_organization_name()
        header = Text()
        header.append("Profile: ", style="dim")
        header.append(profile or "standalone", style="cyan")
        if org:
            header.append("  Org: ", style="dim")
            header.append(org, style="cyan")
        header.append("\n")

        # Two-column layout
        layout = Table.grid(padding=1)
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
        actions = _get_actions_for_category(self._active_category)
        action_text = Text()

        for i, action in enumerate(actions):
            is_selected = i == self._cursor

            # Add separator before Factory reset (last action in Maintenance)
            if action.id == "factory_reset":
                action_text.append("  ───────────────────────────\n", style="dim")

            prefix = Indicators.get("CURSOR") + " " if is_selected else "  "

            action_text.append(prefix, style="cyan" if is_selected else "")
            action_text.append(
                action.label,
                style="bold" if is_selected else "",
            )
            action_text.append("  ")
            action_text.append(_get_risk_badge(action.risk_tier))
            action_text.append("\n")
            action_text.append(f"  {action.description}\n", style="dim")

        layout.add_row(
            Panel(cat_text, title="Categories", border_style="dim"),
            Panel(action_text, title="Actions", border_style="dim"),
        )

        # Receipt line (shows last action result)
        receipt = Text()
        if self._last_result:
            receipt.append("✓ ", style="green")
            receipt.append(self._last_result, style="green")
            receipt.append("\n\n")

        # Footer hints
        hints = Text()
        hints.append("↑↓ ", style="dim")
        hints.append("navigate", style="dim")
        hints.append(" │ ", style="dim")
        hints.append("←→/Tab ", style="dim")
        hints.append("switch category", style="dim")
        hints.append(" │ ", style="dim")
        hints.append("Enter ", style="dim")
        hints.append("select", style="dim")
        hints.append(" │ ", style="dim")
        hints.append("i ", style="dim")
        hints.append("info", style="dim")
        hints.append(" │ ", style="dim")
        hints.append("p ", style="dim")
        hints.append("preview", style="dim")
        hints.append(" │ ", style="dim")
        hints.append("? ", style="dim")
        hints.append("help", style="dim")
        hints.append(" │ ", style="dim")
        hints.append("Esc ", style="dim")
        hints.append("back", style="dim")

        # Build full screen content
        content = (
            Group(header, layout, receipt, hints)
            if self._last_result
            else Group(header, layout, hints)
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
                title="Help",
                border_style="cyan",
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
                title="Action Info",
                border_style="cyan",
            )
            dismiss = Text("\n[dim]Press any key to dismiss[/dim]")
            content = Group(header, layout, info, dismiss)

        # Preview panel overlay
        elif self._show_preview and actions:
            action = actions[self._cursor]
            try:
                preview = preview_operation(action.id)
                preview_text = Text()
                preview_text.append(f"{action.label}\n\n", style="bold")
                preview_text.append("Risk: ")
                preview_text.append(_get_risk_badge(preview.risk_tier))
                preview_text.append("\n\n")

                if preview.paths:
                    preview_text.append("Affects:\n", style="dim")
                    for path in preview.paths[:5]:  # Limit to 5 paths
                        preview_text.append(f"  {path}\n")
                    if len(preview.paths) > 5:
                        preview_text.append(f"  (+{len(preview.paths) - 5} more)\n", style="dim")

                if preview.item_count > 0:
                    preview_text.append(f"\nItems: {preview.item_count}\n")

                if preview.bytes_estimate > 0:
                    preview_text.append(f"Size: ~{_format_bytes(preview.bytes_estimate)}\n")

                if preview.backup_will_be_created:
                    preview_text.append("\n[yellow]Backup will be created[/yellow]\n")

            except Exception:
                preview_text = Text(f"Unable to preview {action.label}")

            preview_panel = Panel(
                preview_text,
                title="Preview",
                border_style="yellow",
            )
            dismiss = Text("\n[dim]Press any key to dismiss[/dim]")
            content = Group(header, layout, preview_panel, dismiss)

        return Panel(
            content,
            title="[bold cyan]Settings & Maintenance[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )


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
