"""
Org package - Typer app definitions and command wiring.

This module contains the Typer app definitions and wires commands from:
- validate_cmd.py: Schema and semantic validation
- update_cmd.py: Organization and team config refresh
- schema_cmd.py: Print bundled schema
- status_cmd.py: Current organization status
- import_cmd.py: Import organization config from URL
- init_cmd.py: Generate config skeleton from templates
"""

from __future__ import annotations

import typer

from .import_cmd import org_import_cmd
from .init_cmd import org_init_cmd
from .schema_cmd import org_schema_cmd
from .status_cmd import org_status_cmd
from .update_cmd import org_update_cmd
from .validate_cmd import org_validate_cmd

# ─────────────────────────────────────────────────────────────────────────────
# Org App
# ─────────────────────────────────────────────────────────────────────────────

org_app = typer.Typer(
    name="org",
    help="Organization configuration management and validation.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Wire org commands
org_app.command("validate")(org_validate_cmd)
org_app.command("update")(org_update_cmd)
org_app.command("schema")(org_schema_cmd)
org_app.command("status")(org_status_cmd)
org_app.command("import")(org_import_cmd)
org_app.command("init")(org_init_cmd)
