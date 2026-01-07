"""Personal profile commands.

Manage per-project personal settings layered on top of team config.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import typer
from rich.table import Table

from .. import config as config_module
from .. import docker as docker_module
from ..cli_common import console, handle_errors
from ..confirm import Confirm
from ..core.exit_codes import EXIT_USAGE
from ..core.personal_profiles import (
    build_diff_text,
    compute_fingerprints,
    compute_sandbox_import_candidates,
    detect_drift,
    export_profiles_to_repo,
    extract_personal_plugins,
    get_repo_profile_dir,
    import_profiles_from_repo,
    list_personal_profiles,
    load_applied_state,
    load_personal_profile_with_status,
    load_workspace_mcp_with_status,
    load_workspace_settings_with_status,
    merge_personal_mcp,
    merge_personal_settings,
    merge_sandbox_imports,
    save_applied_state,
    save_personal_profile,
    write_workspace_mcp,
    write_workspace_settings,
)
from ..subprocess_utils import run_command
from ..ui.gate import is_interactive_allowed

profile_app = typer.Typer(
    name="profile",
    help="Manage personal project profiles.",
    no_args_is_help=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


def _resolve_workspace(workspace: str | None) -> Path:
    return Path(workspace) if workspace else Path.cwd()


def _print_stack_summary(workspace: Path, profile_id: str | None) -> None:
    team = config_module.get_selected_profile() or "none"
    personal = profile_id or "none"
    console.print(
        f"[dim]Active stack: team={team} | personal={personal} | workspace={workspace}[/dim]"
    )


def _format_preview(items: list[str], limit: int = 5) -> str:
    if len(items) <= limit:
        return ", ".join(items)
    return ", ".join(items[:limit]) + f" (+{len(items) - limit} more)"


def _resolve_repo_path(repo: str) -> Path:
    path = Path(repo).expanduser()
    try:
        return path.resolve()
    except FileNotFoundError:
        return path


def _ensure_repo_dir(repo_path: Path) -> None:
    if repo_path.exists():
        if not repo_path.is_dir():
            console.print("[red]Repo path exists but is not a directory.[/red]")
            raise typer.Exit(EXIT_USAGE)
        return

    if is_interactive_allowed():
        if not Confirm.ask(f"Create directory {repo_path}?", default=True):
            raise typer.Exit(EXIT_USAGE)
    try:
        repo_path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        console.print(f"[red]Failed to create repo directory: {exc}[/red]")
        raise typer.Exit(EXIT_USAGE)


def _is_git_repo(repo_path: Path) -> bool:
    result = run_command(["git", "-C", str(repo_path), "rev-parse", "--is-inside-work-tree"])
    return result == "true"


def _run_git(repo_path: Path, args: list[str], label: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        console.print(f"[red]{label} failed.[/red]")
        if result.stderr:
            console.print(result.stderr.strip())
        raise typer.Exit(EXIT_USAGE)
    return result.stdout.strip()


def _ensure_git_repo(repo_path: Path, commit_requested: bool) -> bool:
    if _is_git_repo(repo_path):
        return True
    if not commit_requested:
        console.print(
            "[yellow]Repo is not a git repository; export will skip commit/push.[/yellow]"
        )
        console.print("[dim]Tip: run git init if you want to version these files.[/dim]")
        return False

    if is_interactive_allowed():
        if not Confirm.ask("This directory is not a git repo. Initialize now?", default=True):
            console.print("[red]Cannot commit without a git repository.[/red]")
            raise typer.Exit(EXIT_USAGE)
    else:
        console.print("[red]Cannot initialize git repo in non-interactive mode.[/red]")
        raise typer.Exit(EXIT_USAGE)
    _run_git(repo_path, ["init"], "git init")
    return True


def _status_paths(lines: list[str]) -> list[str]:
    paths: list[str] = []
    for line in lines:
        if len(line) < 4:
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path)
    return paths


def _git_status(repo_path: Path, paths: list[str] | None = None) -> list[str]:
    cmd = ["git", "-C", str(repo_path), "status", "--porcelain"]
    if paths:
        cmd.append("--")
        cmd.extend(paths)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def _ensure_commit_allowed(repo_path: Path, force: bool) -> None:
    all_changes = _git_status(repo_path)
    if not all_changes:
        return

    profile_root = str(get_repo_profile_dir(repo_path).relative_to(repo_path))
    profile_changes = _status_paths(_git_status(repo_path, [profile_root]))
    other_changes = [
        path for path in _status_paths(all_changes) if not path.startswith(profile_root)
    ]

    if other_changes and not force:
        console.print("[red]Repo has uncommitted changes outside .scc/profiles.[/red]")
        console.print("Use --force to continue and commit only profile updates.")
        raise typer.Exit(EXIT_USAGE)

    if not profile_changes:
        console.print("[yellow]No profile changes to commit.[/yellow]")
        raise typer.Exit(EXIT_USAGE)

    if not force and is_interactive_allowed():
        console.print("[yellow]About to commit profile changes.[/yellow]")
        if not Confirm.ask("Continue with commit?", default=True):
            raise typer.Exit(EXIT_USAGE)


@handle_errors
def list_cmd(
    workspace: str | None = typer.Option(None, "--workspace", help="Filter to a workspace"),
) -> None:
    """List saved personal profiles."""
    if workspace:
        ws_path = _resolve_workspace(workspace)
        profile, corrupt = load_personal_profile_with_status(ws_path)
        if corrupt:
            console.print("[red]Personal profile file is invalid JSON.[/red]")
            raise typer.Exit(EXIT_USAGE)
        if profile is None:
            console.print("[yellow]No personal profile found for this project.[/yellow]")
            console.print("[dim]Run: scc profile save[/dim]")
            return
        profiles = [profile]
    else:
        profiles = list_personal_profiles()

    if not profiles:
        console.print("[dim]No personal profiles saved yet.[/dim]")
        return

    table = Table(title="Personal Profiles")
    table.add_column("Repo ID")
    table.add_column("Saved At")
    table.add_column("Plugins")
    for profile in profiles:
        plugins = extract_personal_plugins(profile)
        table.add_row(
            profile.repo_id,
            profile.saved_at or "-",
            str(len(plugins)),
        )
    console.print(table)


@handle_errors
def save_cmd(
    workspace: str | None = typer.Option(None, "--workspace", help="Workspace path"),
) -> None:
    """Save current workspace settings as a personal profile."""
    ws_path = _resolve_workspace(workspace)
    settings, settings_invalid = load_workspace_settings_with_status(ws_path)
    mcp, mcp_invalid = load_workspace_mcp_with_status(ws_path)

    if settings_invalid:
        console.print("[red]Invalid JSON in .claude/settings.local.json[/red]")
        raise typer.Exit(EXIT_USAGE)
    if mcp_invalid:
        console.print("[red]Invalid JSON in .mcp.json[/red]")
        raise typer.Exit(EXIT_USAGE)

    sandbox_settings = docker_module.get_sandbox_settings()
    missing_plugins, missing_marketplaces = compute_sandbox_import_candidates(
        settings or {}, sandbox_settings
    )

    if missing_plugins or missing_marketplaces:
        console.print(
            "[yellow]Detected plugin changes in sandbox global settings that are not in this workspace.[/yellow]"
        )
        if missing_plugins:
            console.print(f"[dim]Plugins: {_format_preview(missing_plugins)}[/dim]")
        if missing_marketplaces:
            console.print(
                f"[dim]Marketplaces: {_format_preview(sorted(missing_marketplaces.keys()))}[/dim]"
            )

        if is_interactive_allowed():
            if Confirm.ask(
                "Import these into .claude/settings.local.json before saving?",
                default=True,
            ):
                workspace_settings = merge_sandbox_imports(
                    settings or {}, missing_plugins, missing_marketplaces
                )
                write_workspace_settings(ws_path, workspace_settings)
                settings = workspace_settings
                console.print("[green]Imported sandbox settings into workspace.[/green]")
        else:
            console.print("[dim]Run this command interactively to import them before saving.[/dim]")

    if settings is None and mcp is None:
        console.print("[yellow]No workspace settings found to save.[/yellow]")
        raise typer.Exit(EXIT_USAGE)

    existing_profile, _ = load_personal_profile_with_status(ws_path)
    profile = save_personal_profile(ws_path, settings or {}, mcp or {})
    save_applied_state(ws_path, profile.profile_id, compute_fingerprints(ws_path))
    _print_stack_summary(ws_path, profile.repo_id)
    console.print("[dim]Scope: personal profile (project only)[/dim]")
    console.print(f"[green]Saved personal profile[/green] for [cyan]{profile.repo_id}[/cyan]")
    console.print(f"[dim]{profile.path}[/dim]")
    if existing_profile is None:
        console.print("[dim]Tip: this profile auto-applies on scc start for this project.[/dim]")


@handle_errors
def apply_cmd(
    workspace: str | None = typer.Option(None, "--workspace", help="Workspace path"),
    preview: bool = typer.Option(False, "--preview", help="Show diff without writing"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Alias for --preview"),
    force: bool = typer.Option(False, "--force", help="Apply even if drift detected"),
) -> None:
    """Apply personal profile to the workspace."""
    ws_path = _resolve_workspace(workspace)
    profile, corrupt = load_personal_profile_with_status(ws_path)
    if corrupt:
        console.print("[red]Personal profile file is invalid JSON.[/red]")
        raise typer.Exit(EXIT_USAGE)
    if profile is None:
        console.print("[yellow]No personal profile found for this project.[/yellow]")
        console.print("[dim]Run: scc profile save[/dim]")
        return

    existing_settings, settings_invalid = load_workspace_settings_with_status(ws_path)
    existing_mcp, mcp_invalid = load_workspace_mcp_with_status(ws_path)
    if settings_invalid:
        console.print("[red]Invalid JSON in .claude/settings.local.json[/red]")
        raise typer.Exit(EXIT_USAGE)
    if mcp_invalid:
        console.print("[red]Invalid JSON in .mcp.json[/red]")
        raise typer.Exit(EXIT_USAGE)

    existing_settings = existing_settings or {}
    existing_mcp = existing_mcp or {}

    missing_plugins, missing_marketplaces = compute_sandbox_import_candidates(
        existing_settings, docker_module.get_sandbox_settings()
    )
    if missing_plugins or missing_marketplaces:
        console.print(
            "[yellow]Sandbox has plugin changes not yet in the workspace settings.[/yellow]"
        )
        if missing_plugins:
            console.print(f"[dim]Plugins: {_format_preview(missing_plugins)}[/dim]")
        if missing_marketplaces:
            console.print(
                f"[dim]Marketplaces: {_format_preview(sorted(missing_marketplaces.keys()))}[/dim]"
            )
        console.print("[dim]Run scc profile save to import these changes.[/dim]")

    if detect_drift(ws_path) and not force:
        if is_interactive_allowed():
            console.print("[yellow]Workspace overrides detected since last apply.[/yellow]")
            if Confirm.ask("Preview changes before applying?", default=True):
                diff_settings = build_diff_text(
                    f"settings.local.json ({profile.repo_id})",
                    existing_settings,
                    merge_personal_settings(ws_path, existing_settings, profile.settings or {}),
                )
                if diff_settings:
                    console.print(diff_settings)
                if profile.mcp:
                    diff_mcp = build_diff_text(
                        f".mcp.json ({profile.repo_id})",
                        existing_mcp,
                        merge_personal_mcp(existing_mcp, profile.mcp or {}),
                    )
                    if diff_mcp:
                        console.print(diff_mcp)
            if not Confirm.ask("Apply personal profile anyway?", default=False):
                return
        else:
            console.print(
                "[red]Workspace drift detected.[/red] Use --force to apply in non-interactive mode."
            )
            raise typer.Exit(EXIT_USAGE)

    merged_settings = merge_personal_settings(ws_path, existing_settings, profile.settings or {})
    merged_mcp = merge_personal_mcp(existing_mcp, profile.mcp or {})

    if merged_settings == existing_settings and merged_mcp == existing_mcp:
        _print_stack_summary(ws_path, profile.repo_id)
        console.print("[dim]Scope: personal profile (project only)[/dim]")
        console.print("[dim]Workspace already matches the saved profile.[/dim]")
        return

    if preview or dry_run:
        any_diff = False
        diff_settings = build_diff_text("settings.local.json", existing_settings, merged_settings)
        if diff_settings:
            console.print(diff_settings)
            any_diff = True

        if profile.mcp:
            diff_mcp = build_diff_text(".mcp.json", existing_mcp, merged_mcp)
            if diff_mcp:
                console.print(diff_mcp)
                any_diff = True
        if not any_diff:
            console.print("[dim]No changes to apply.[/dim]")
        return

    write_workspace_settings(ws_path, merged_settings)
    if profile.mcp:
        write_workspace_mcp(ws_path, merged_mcp)

    save_applied_state(ws_path, profile.profile_id, compute_fingerprints(ws_path))
    _print_stack_summary(ws_path, profile.repo_id)
    console.print("[dim]Scope: personal profile (project only)[/dim]")
    console.print(f"[green]Applied personal profile[/green] for {profile.repo_id}")


@handle_errors
def diff_cmd(
    workspace: str | None = typer.Option(None, "--workspace", help="Workspace path"),
) -> None:
    """Show diff between personal profile and current workspace settings."""
    ws_path = _resolve_workspace(workspace)
    profile, corrupt = load_personal_profile_with_status(ws_path)
    if corrupt:
        console.print("[red]Personal profile file is invalid JSON.[/red]")
        raise typer.Exit(EXIT_USAGE)
    if profile is None:
        console.print("[yellow]No personal profile found for this project.[/yellow]")
        console.print("[dim]Run: scc profile save[/dim]")
        return

    existing_settings, settings_invalid = load_workspace_settings_with_status(ws_path)
    existing_mcp, mcp_invalid = load_workspace_mcp_with_status(ws_path)
    if settings_invalid:
        console.print("[red]Invalid JSON in .claude/settings.local.json[/red]")
        raise typer.Exit(EXIT_USAGE)
    if mcp_invalid:
        console.print("[red]Invalid JSON in .mcp.json[/red]")
        raise typer.Exit(EXIT_USAGE)

    existing_settings = existing_settings or {}
    existing_mcp = existing_mcp or {}

    diff_settings = build_diff_text(
        f"settings.local.json ({profile.repo_id})",
        existing_settings,
        profile.settings or {},
    )
    any_diff = False
    if diff_settings:
        console.print(diff_settings)
        any_diff = True

    if profile.mcp:
        diff_mcp = build_diff_text(
            f".mcp.json ({profile.repo_id})",
            existing_mcp,
            profile.mcp or {},
        )
        if diff_mcp:
            console.print(diff_mcp)
            any_diff = True

    if not any_diff:
        console.print("[dim]Workspace already matches the saved profile.[/dim]")


@handle_errors
def status_cmd(
    workspace: str | None = typer.Option(None, "--workspace", help="Workspace path"),
) -> None:
    """Show personal profile status for this workspace."""
    ws_path = _resolve_workspace(workspace)
    profile, corrupt = load_personal_profile_with_status(ws_path)
    if corrupt:
        console.print("[red]Personal profile file is invalid JSON.[/red]")
        raise typer.Exit(EXIT_USAGE)

    settings, settings_invalid = load_workspace_settings_with_status(ws_path)
    if settings_invalid:
        console.print("[red]Invalid JSON in .claude/settings.local.json[/red]")
        raise typer.Exit(EXIT_USAGE)

    applied = load_applied_state(ws_path)
    drift = detect_drift(ws_path) if applied else False

    missing_plugins, missing_marketplaces = compute_sandbox_import_candidates(
        settings or {}, docker_module.get_sandbox_settings()
    )

    if missing_plugins or missing_marketplaces:
        console.print(
            "[yellow]Sandbox has plugin changes not yet in the workspace settings.[/yellow]"
        )
        if missing_plugins:
            console.print(f"[dim]Plugins: {_format_preview(missing_plugins)}[/dim]")
        if missing_marketplaces:
            console.print(
                f"[dim]Marketplaces: {_format_preview(sorted(missing_marketplaces.keys()))}[/dim]"
            )
        if is_interactive_allowed():
            if Confirm.ask(
                "Import sandbox settings into .claude/settings.local.json now?",
                default=False,
            ):
                workspace_settings = merge_sandbox_imports(
                    settings or {}, missing_plugins, missing_marketplaces
                )
                write_workspace_settings(ws_path, workspace_settings)
                console.print("[green]Imported sandbox settings into workspace.[/green]")
                if profile is not None and is_interactive_allowed():
                    if Confirm.ask(
                        "Save these changes to your personal profile now?",
                        default=True,
                    ):
                        updated_profile = save_personal_profile(
                            ws_path,
                            workspace_settings,
                            load_workspace_mcp_with_status(ws_path)[0] or {},
                        )
                        save_applied_state(
                            ws_path,
                            updated_profile.profile_id,
                            compute_fingerprints(ws_path),
                        )
                        console.print("[green]Personal profile updated.[/green]")
                drift = detect_drift(ws_path) if applied else False
        else:
            console.print("[dim]Run scc profile save interactively to import these changes.[/dim]")

    _print_stack_summary(ws_path, profile.repo_id if profile else None)
    console.print(f"[dim]Profile: {profile.repo_id if profile else 'none'}[/dim]")
    console.print(f"[dim]Applied: {applied.applied_at if applied else 'never'}[/dim]")
    console.print(f"[dim]Drift: {'yes' if drift else 'no'}[/dim]")


@handle_errors
def export_cmd(
    repo: str = typer.Option(..., "--repo", help="Path to repo for export"),
    workspace: str | None = typer.Option(None, "--workspace", help="Export only this workspace"),
    commit: bool = typer.Option(False, "--commit", help="Commit exported profiles"),
    push: bool = typer.Option(False, "--push", help="Push after commit"),
    force: bool = typer.Option(False, "--force", help="Commit even with other changes"),
) -> None:
    """Export personal profiles to a local repo path."""
    repo_path = _resolve_repo_path(repo)
    _ensure_repo_dir(repo_path)

    if push:
        commit = True

    is_repo = _ensure_git_repo(repo_path, commit)

    profiles = None
    if workspace:
        ws_path = _resolve_workspace(workspace)
        profile, corrupt = load_personal_profile_with_status(ws_path)
        if corrupt:
            console.print("[red]Personal profile file is invalid JSON.[/red]")
            raise typer.Exit(EXIT_USAGE)
        if profile is None:
            console.print("[yellow]No personal profile found for this project.[/yellow]")
            raise typer.Exit(EXIT_USAGE)
        profiles = [profile]
    else:
        if is_interactive_allowed():
            if not Confirm.ask("Export all saved personal profiles?", default=True):
                raise typer.Exit(EXIT_USAGE)

    result = export_profiles_to_repo(repo_path, profiles)

    for warning in result.warnings:
        console.print(f"[yellow]{warning}[/yellow]")

    if result.exported == 0:
        console.print("[yellow]No profiles exported.[/yellow]")
        return

    console.print(f"[green]Exported {result.exported} profile(s).[/green]")
    console.print(f"[dim]Profiles: {result.profile_dir}[/dim]")
    console.print(f"[dim]Index: {result.index_path}[/dim]")

    if commit:
        if not is_repo:
            console.print("[red]Cannot commit without a git repository.[/red]")
            raise typer.Exit(EXIT_USAGE)
        _ensure_commit_allowed(repo_path, force)
        profile_root = str(get_repo_profile_dir(repo_path).relative_to(repo_path))
        _run_git(repo_path, ["add", "--", profile_root], "git add")
        _run_git(
            repo_path,
            ["commit", "-m", "scc: update personal profiles", "--", profile_root],
            "git commit",
        )
        console.print("[green]Committed profile updates.[/green]")

    if push:
        if not is_repo:
            console.print("[red]Cannot push without a git repository.[/red]")
            raise typer.Exit(EXIT_USAGE)
        _run_git(repo_path, ["push"], "git push")
        console.print("[green]Pushed profile updates.[/green]")


@handle_errors
def import_cmd(
    repo: str = typer.Option(..., "--repo", help="Path to repo for import"),
    force: bool = typer.Option(False, "--force", help="Overwrite local profiles"),
    preview: bool = typer.Option(False, "--preview", help="Show changes without writing"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Alias for --preview"),
) -> None:
    """Import personal profiles from a local repo path."""
    repo_path = _resolve_repo_path(repo)
    if not repo_path.exists() or not repo_path.is_dir():
        console.print("[red]Repo path does not exist or is not a directory.[/red]")
        raise typer.Exit(EXIT_USAGE)

    if not get_repo_profile_dir(repo_path).exists():
        console.print("[yellow]No .scc/profiles directory found in repo.[/yellow]")
        console.print("Run: scc profile export --repo <path> to create one.")
        raise typer.Exit(EXIT_USAGE)

    if not force and is_interactive_allowed():
        console.print("[yellow]Import will overwrite local profiles if different.[/yellow]")
        if not Confirm.ask("Continue importing profiles?", default=True):
            return

    result = import_profiles_from_repo(repo_path, force=force, dry_run=preview or dry_run)

    for warning in result.warnings:
        console.print(f"[yellow]{warning}[/yellow]")

    if preview or dry_run:
        console.print(
            f"[green]Preview:[/green] would import {result.imported} profile(s)."
            f" Skipped {result.skipped}."
        )
        console.print("[dim]No files were written.[/dim]")
        return

    console.print(
        f"[green]Imported {result.imported} profile(s).[/green] Skipped {result.skipped}."
    )


@handle_errors
def sync_cmd(
    repo: str = typer.Option(..., "--repo", help="Path to repo for sync"),
    pull: bool = typer.Option(False, "--pull", help="Pull and import before export"),
    commit: bool = typer.Option(False, "--commit", help="Commit exported profiles"),
    push: bool = typer.Option(False, "--push", help="Push after commit"),
    force: bool = typer.Option(False, "--force", help="Allow overwrites and commit with changes"),
) -> None:
    """Sync personal profiles with a local repo path."""
    repo_path = _resolve_repo_path(repo)
    _ensure_repo_dir(repo_path)

    if push:
        commit = True

    if not pull and not commit and not push and is_interactive_allowed():
        console.print("[yellow]Sync will export profiles to the repo directory.[/yellow]")
        if not Confirm.ask("Continue?", default=True):
            raise typer.Exit(EXIT_USAGE)

    if pull:
        if _ensure_git_repo(repo_path, commit_requested=True):
            _run_git(repo_path, ["pull", "--ff-only"], "git pull")
        import_result = import_profiles_from_repo(repo_path, force=force)
        for warning in import_result.warnings:
            console.print(f"[yellow]{warning}[/yellow]")
        console.print(
            f"[green]Imported {import_result.imported} profile(s).[/green]"
            f" Skipped {import_result.skipped}."
        )

    export_result = export_profiles_to_repo(repo_path)
    for warning in export_result.warnings:
        console.print(f"[yellow]{warning}[/yellow]")
    console.print(f"[green]Exported {export_result.exported} profile(s).[/green]")

    if commit:
        if not _ensure_git_repo(repo_path, commit_requested=True):
            console.print("[red]Cannot commit without a git repository.[/red]")
            raise typer.Exit(EXIT_USAGE)
        _ensure_commit_allowed(repo_path, force)
        profile_root = str(get_repo_profile_dir(repo_path).relative_to(repo_path))
        _run_git(repo_path, ["add", "--", profile_root], "git add")
        _run_git(
            repo_path,
            ["commit", "-m", "scc: sync personal profiles", "--", profile_root],
            "git commit",
        )
        console.print("[green]Committed profile updates.[/green]")

    if push:
        if not _is_git_repo(repo_path):
            console.print("[red]Cannot push without a git repository.[/red]")
            raise typer.Exit(EXIT_USAGE)
        _run_git(repo_path, ["push"], "git push")
        console.print("[green]Pushed profile updates.[/green]")


profile_app.command("list")(list_cmd)
profile_app.command("save")(save_cmd)
profile_app.command("apply")(apply_cmd)
profile_app.command("diff")(diff_cmd)
profile_app.command("status")(status_cmd)
profile_app.command("export")(export_cmd)
profile_app.command("import")(import_cmd)
profile_app.command("sync")(sync_cmd)
