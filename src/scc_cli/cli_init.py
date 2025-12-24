"""
Define the SCC init command for project configuration initialization.

Create a .scc.yaml configuration file in a project directory with
sensible defaults and helpful comments.
"""

from pathlib import Path
from typing import Any

import typer
from rich.panel import Panel

from .cli_common import console, handle_errors
from .cli_helpers import confirm_action, is_interactive
from .exit_codes import EXIT_CONFIG, EXIT_SUCCESS, EXIT_USAGE
from .json_output import build_envelope
from .kinds import Kind
from .output_mode import print_json, set_pretty_mode

# ─────────────────────────────────────────────────────────────────────────────
# Pure Functions (No I/O)
# ─────────────────────────────────────────────────────────────────────────────


def is_git_repo(path: Path) -> bool:
    """Check if path is a git repository.

    Args:
        path: Directory path to check.

    Returns:
        True if .git directory exists, False otherwise.
    """
    git_dir = path / ".git"
    return git_dir.exists() and git_dir.is_dir()


def build_init_data(
    file_path: str,
    created: bool,
    overwritten: bool,
    is_git_repo: bool,
) -> dict[str, Any]:
    """Build init result data for JSON output.

    Args:
        file_path: Path to created .scc.yaml file.
        created: Whether the file was created.
        overwritten: Whether an existing file was overwritten.
        is_git_repo: Whether the target is a git repository.

    Returns:
        Dictionary with init result data.
    """
    return {
        "file_path": file_path,
        "created": created,
        "overwritten": overwritten,
        "is_git_repo": is_git_repo,
    }


def generate_template_content() -> str:
    """Generate .scc.yaml template content with helpful comments.

    Returns:
        YAML template string with comments.
    """
    return """\
# SCC Project Configuration
# ─────────────────────────────────────────────────────────────────────────────
# This file configures SCC (Sandboxed Claude CLI) for this project.
# Place this file in your repository root.
#
# For full documentation, see: https://github.com/sundsvall/scc-cli#configuration
# ─────────────────────────────────────────────────────────────────────────────

# Additional plugins to enable for this project
# These plugins are loaded on top of your team profile's plugins.
# Only plugins allowed by your organization can be added here.
additional_plugins: []
  # - "project-specific-linter"
  # - "custom-formatter"

# Session configuration
session:
  # Session timeout in hours (default: 8)
  timeout_hours: 8

# Optional: MCP servers specific to this project
# mcp_servers: []
#   - name: "project-db"
#     command: "npx"
#     args: ["@project/mcp-server"]

# Optional: Environment variables for the sandbox
# env: {}
#   PROJECT_NAME: "my-project"
"""


# ─────────────────────────────────────────────────────────────────────────────
# CLI Command
# ─────────────────────────────────────────────────────────────────────────────


@handle_errors
def init_cmd(
    path: str | None = typer.Argument(
        None,
        help="Target directory (default: current directory).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing .scc.yaml file without prompting.",
    ),
    yes: bool = typer.Option(
        False,
        "-y",
        "--yes",
        help="Skip confirmation prompts (still requires --force to overwrite).",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output as JSON.",
    ),
    pretty: bool = typer.Option(
        False,
        "--pretty",
        help="Pretty-print JSON (implies --json).",
    ),
) -> None:
    """Initialize SCC project configuration.

    Creates a .scc.yaml file in the target directory with sensible defaults
    and helpful comments explaining each configuration option.

    Three-tier overwrite logic:
      - If file doesn't exist: create it
      - If file exists + --force: overwrite without prompting
      - If file exists + no --force: prompt in interactive mode, or hint to use --force
    """
    # --pretty implies --json
    if pretty:
        json_output = True
        set_pretty_mode(True)

    # Resolve target path
    if path is None:
        target_dir = Path.cwd()
    else:
        target_dir = Path(path).resolve()

    # Validate target directory
    if not target_dir.exists():
        if json_output:
            envelope = build_envelope(
                Kind.INIT_RESULT,
                ok=False,
                errors=[f"Directory does not exist: {target_dir}"],
            )
            print_json(envelope)
            raise typer.Exit(EXIT_CONFIG)
        else:
            console.print(f"[red]Error:[/red] Directory does not exist: {target_dir}")
            raise typer.Exit(EXIT_CONFIG)

    if not target_dir.is_dir():
        if json_output:
            envelope = build_envelope(
                Kind.INIT_RESULT,
                ok=False,
                errors=[f"Path is not a directory: {target_dir}"],
            )
            print_json(envelope)
            raise typer.Exit(EXIT_CONFIG)
        else:
            console.print(f"[red]Error:[/red] Path is not a directory: {target_dir}")
            raise typer.Exit(EXIT_CONFIG)

    # Check for existing file - three-tier overwrite logic
    scc_yaml = target_dir / ".scc.yaml"
    overwritten = False

    if scc_yaml.exists():
        if force:
            # Tier 3: --force → overwrite without prompting
            overwritten = True
        elif json_output:
            # JSON mode: never prompt, just tell user to use --force
            envelope = build_envelope(
                Kind.INIT_RESULT,
                ok=False,
                errors=[f"File already exists: {scc_yaml}. Use --force to overwrite."],
            )
            print_json(envelope)
            raise typer.Exit(EXIT_CONFIG)
        elif yes:
            # Tier 4: --yes without --force → hint that --force is required
            console.print(
                f"[yellow]Warning:[/yellow] File already exists: [cyan]{scc_yaml}[/cyan]\n"
                "[dim]--yes skips prompts but does not allow overwriting.[/dim]\n"
                "Use [yellow]--force[/yellow] to overwrite existing file."
            )
            raise typer.Exit(EXIT_USAGE)
        elif is_interactive():
            # Tier 2: Interactive without --force → prompt for confirmation
            console.print(f"[yellow]Warning:[/yellow] File already exists: [cyan]{scc_yaml}[/cyan]")
            try:
                confirm_action(
                    yes=False,
                    prompt="Overwrite existing .scc.yaml?",
                    non_interactive_requires_yes=False,
                )
                overwritten = True
            except typer.Abort:
                console.print("[dim]Aborted.[/dim]")
                raise typer.Exit(EXIT_SUCCESS)
        else:
            # Tier 3: Non-interactive without --force → exit with usage error
            console.print(
                f"[red]Error:[/red] File already exists: [cyan]{scc_yaml}[/cyan]\n"
                "Use [yellow]--force[/yellow] to overwrite in non-interactive mode."
            )
            raise typer.Exit(EXIT_USAGE)

    # Check if git repo and warn if not
    is_git = is_git_repo(target_dir)
    if not is_git and not json_output:
        console.print(
            "[yellow]Warning:[/yellow] Target directory is not a git repository.\n"
            "SCC works best with git-tracked projects for branch safety and worktree features."
        )

    # Generate and write template
    template_content = generate_template_content()
    scc_yaml.write_text(template_content)

    # Build result data
    result_data = build_init_data(
        file_path=str(scc_yaml),
        created=True,
        overwritten=overwritten,
        is_git_repo=is_git,
    )

    # Output
    if json_output:
        envelope = build_envelope(Kind.INIT_RESULT, data=result_data)
        print_json(envelope)
        raise typer.Exit(EXIT_SUCCESS)
    else:
        action = "Overwrote" if overwritten else "Created"
        console.print(
            Panel(
                f"{action} [cyan]{scc_yaml}[/cyan]\n\n"
                "Edit this file to configure project-specific settings.\n"
                "See the comments in the file for available options.",
                title="[green]SCC Initialized[/green]",
                border_style="green",
            )
        )
        if not is_git:
            console.print(
                "\n[dim]Tip: Initialize a git repository with [cyan]git init[/cyan] "
                "to enable branch safety and worktree features.[/dim]"
            )
        raise typer.Exit(EXIT_SUCCESS)
