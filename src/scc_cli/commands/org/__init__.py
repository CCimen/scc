"""
Org package - organization configuration management commands.

This package contains the decomposed org functionality:
- app.py: Typer app definitions and command wiring
- validate_cmd.py: Schema and semantic validation
- update_cmd.py: Organization and team config refresh
- schema_cmd.py: Print bundled schema
- status_cmd.py: Current organization status
- import_cmd.py: Import organization config from URL
- init_cmd.py: Generate config skeleton from templates
- _builders.py: Pure builder functions

Public API re-exports for backward compatibility.
"""

# Re-export pure builders for testing
from ._builders import (
    build_import_preview_data,
    build_status_data,
    build_update_data,
    build_validation_data,
    check_semantic_errors,
)
from .app import org_app
from .import_cmd import org_import_cmd
from .init_cmd import org_init_cmd
from .schema_cmd import org_schema_cmd
from .status_cmd import org_status_cmd
from .update_cmd import org_update_cmd
from .validate_cmd import org_validate_cmd

__all__ = [
    # Typer app
    "org_app",
    # Commands
    "org_validate_cmd",
    "org_update_cmd",
    "org_schema_cmd",
    "org_status_cmd",
    "org_import_cmd",
    "org_init_cmd",
    # Pure builders
    "build_validation_data",
    "check_semantic_errors",
    "build_import_preview_data",
    "build_status_data",
    "build_update_data",
]
