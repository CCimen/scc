"""
CLI Launch Commands.

Thin wrapper around the start flow implementation.
"""

from __future__ import annotations

import typer

from ...cli_common import handle_errors
from .flow import start as _start

launch_app = typer.Typer(
    name="launch",
    help="Start Claude Code in sandboxes.",
    no_args_is_help=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)

start = handle_errors(_start)
