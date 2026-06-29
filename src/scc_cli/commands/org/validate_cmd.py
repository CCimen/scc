"""Org validate command for schema and semantic validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, NoReturn, cast

import typer

from ...cli_common import console, handle_errors
from ...core.constants import CURRENT_SCHEMA_VERSION
from ...core.exit_codes import EXIT_CONFIG, EXIT_TOOL
from ...json_output import build_envelope
from ...kinds import Kind
from ...output_mode import json_output_mode, print_json, set_pretty_mode
from ...panels import create_error_panel, create_success_panel, create_warning_panel
from ...source_resolver import ResolveError, resolve_source
from ...validate import validate_org_config
from ._builders import build_validation_data, check_semantic_errors


def _exit_config_load_error(
    *,
    source: str,
    json_output: bool,
    title: str,
    human_message: str,
    schema_error: str | None = None,
) -> NoReturn:
    error = schema_error or human_message
    if json_output:
        with json_output_mode():
            data = build_validation_data(
                source=source,
                schema_errors=[error],
                semantic_errors=[],
            )
            envelope = build_envelope(Kind.ORG_VALIDATION, data=data, ok=False)
            print_json(envelope)
        raise typer.Exit(EXIT_CONFIG)

    console.print(create_error_panel(title, human_message))
    raise typer.Exit(EXIT_CONFIG)


def _load_org_config_file(
    *,
    source: str,
    config_path: Path,
    json_output: bool,
) -> dict[str, Any]:
    if not config_path.exists():
        _exit_config_load_error(
            source=source,
            json_output=json_output,
            title="File Not Found",
            human_message=f"Cannot find config file: {source}",
            schema_error=f"File not found: {source}",
        )

    try:
        return cast(dict[str, Any], json.loads(config_path.read_text()))
    except json.JSONDecodeError as e:
        _exit_config_load_error(
            source=source,
            json_output=json_output,
            title="Invalid JSON",
            human_message=f"Failed to parse JSON: {e}",
            schema_error=f"Invalid JSON: {e}",
        )


def _load_org_config_remote(
    *,
    source: str,
    resolved_url: str,
    json_output: bool,
) -> dict[str, Any]:
    import requests

    try:
        response = requests.get(resolved_url, timeout=30)
    except requests.RequestException as e:
        _exit_config_load_error(
            source=source,
            json_output=json_output,
            title="Network Error",
            human_message=f"Failed to fetch config: {e}",
        )

    if response.status_code == 404:
        error_msg = f"Config not found at {resolved_url}"
        _exit_config_load_error(
            source=source,
            json_output=json_output,
            title="Not Found",
            human_message=error_msg,
        )

    if response.status_code != 200:
        error_msg = f"HTTP {response.status_code} from {resolved_url}"
        _exit_config_load_error(
            source=source,
            json_output=json_output,
            title="HTTP Error",
            human_message=error_msg,
        )

    try:
        return cast(dict[str, Any], response.json())
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON in response: {e}"
        _exit_config_load_error(
            source=source,
            json_output=json_output,
            title="Invalid JSON",
            human_message=error_msg,
        )


def _load_org_config(source: str, *, json_output: bool) -> dict[str, Any]:
    resolved = resolve_source(source)
    if isinstance(resolved, ResolveError):
        error_msg = resolved.message
        if resolved.suggestion:
            error_msg = f"{resolved.message}\n{resolved.suggestion}"
        _exit_config_load_error(
            source=source,
            json_output=json_output,
            title="Invalid Source",
            human_message=error_msg,
        )

    if resolved.is_file:
        return _load_org_config_file(
            source=source,
            config_path=Path(resolved.resolved_url),
            json_output=json_output,
        )

    return _load_org_config_remote(
        source=source,
        resolved_url=resolved.resolved_url,
        json_output=json_output,
    )


def _validate_loaded_config(config: dict[str, Any]) -> tuple[list[str], list[str]]:
    schema_errors = validate_org_config(config)
    semantic_errors: list[str] = []
    if not schema_errors:
        semantic_errors = check_semantic_errors(config)
    return schema_errors, semantic_errors


def _exit_json_validation_result(
    *,
    data: dict[str, Any],
    schema_errors: list[str],
    semantic_errors: list[str],
) -> NoReturn:
    with json_output_mode():
        is_valid = bool(data["valid"])
        all_errors = schema_errors + semantic_errors
        envelope = build_envelope(
            Kind.ORG_VALIDATION,
            data=data,
            ok=is_valid,
            errors=all_errors if not is_valid else None,
        )
        print_json(envelope)
    raise typer.Exit(0 if is_valid else EXIT_TOOL)


def _exit_human_validation_result(
    *,
    source: str,
    data: dict[str, Any],
    schema_errors: list[str],
    semantic_errors: list[str],
) -> NoReturn:
    if data["valid"]:
        console.print(
            create_success_panel(
                "Validation Passed",
                {
                    "Source": source,
                    "Schema Version": CURRENT_SCHEMA_VERSION,
                    "Status": "Valid",
                },
            )
        )
        raise typer.Exit(0)

    if schema_errors:
        console.print(
            create_error_panel(
                "Schema Validation Failed",
                "\n".join(f"• {e}" for e in schema_errors),
            )
        )

    if semantic_errors:
        console.print(
            create_warning_panel(
                "Semantic Issues",
                "\n".join(f"• {e}" for e in semantic_errors),
            )
        )

    raise typer.Exit(EXIT_TOOL)


@handle_errors
def org_validate_cmd(
    source: str = typer.Argument(
        ...,
        help="Config source (file path, HTTPS URL, or shorthand like github:org/repo:path)",
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON (implies --json)"),
) -> None:
    """Validate an organization configuration file.

    Performs both JSON schema validation and semantic checks.

    Examples:
        scc org validate ./org-config.json
        scc org validate ./org-config.json --json
    """
    # --pretty implies --json
    if pretty:
        json_output = True
        set_pretty_mode(True)

    config = _load_org_config(source, json_output=json_output)
    schema_errors, semantic_errors = _validate_loaded_config(config)
    data = build_validation_data(
        source=source,
        schema_errors=schema_errors,
        semantic_errors=semantic_errors,
    )

    if json_output:
        _exit_json_validation_result(
            data=data,
            schema_errors=schema_errors,
            semantic_errors=semantic_errors,
        )

    _exit_human_validation_result(
        source=source,
        data=data,
        schema_errors=schema_errors,
        semantic_errors=semantic_errors,
    )
