"""
JSON command decorator for first-class JSON output support.

Provide a decorator that wraps command output in JSON envelopes.

IMPORTANT: Commands using this decorator MUST explicitly declare these parameters:
    json_output: bool = typer.Option(False, "--json", help="Output as JSON")
    pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON")

Usage:
    from scc_cli.json_command import json_command
    from scc_cli.kinds import Kind

    @team_app.command("list")
    @json_command(Kind.TEAM_LIST)
    def team_list(
        json_output: bool = typer.Option(False, "--json"),
        pretty: bool = typer.Option(False, "--pretty"),
    ) -> dict:
        # Return data dict, decorator handles envelope
        return {"teams": [...]}
"""

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

import typer

from .core.error_mapping import to_exit_code, to_json_payload
from .core.exit_codes import EXIT_CANCELLED, EXIT_SUCCESS
from .json_output import build_envelope
from .kinds import Kind
from .output_mode import _pretty_mode, json_command_mode, json_output_mode, print_json

# Type variable for decorated functions
F = TypeVar("F", bound=Callable[..., Any])


# ═══════════════════════════════════════════════════════════════════════════════
# JSON Command Decorator
# ═══════════════════════════════════════════════════════════════════════════════


def json_command(kind: Kind) -> Callable[[F], F]:
    """Decorator for commands with --json support.

    This decorator:
    1. Checks for json_output and pretty parameters in kwargs
    2. Enters json_output_mode() when json_output=True
    3. Builds the envelope with the correct kind
    4. Catches exceptions and maps to exit codes
    5. Prints JSON output and exits with appropriate code

    IMPORTANT: The decorated function MUST explicitly declare these parameters:
        json_output: bool = typer.Option(False, "--json", help="Output as JSON")
        pretty: bool = typer.Option(False, "--pretty", help="Pretty-print JSON")

    Args:
        kind: The JSON envelope kind for this command

    Returns:
        A decorator function

    Usage:
        @team_app.command("list")
        @json_command(Kind.TEAM_LIST)
        def team_list(
            json_output: bool = typer.Option(False, "--json"),
            pretty: bool = typer.Option(False, "--pretty"),
        ) -> dict:
            return {"teams": [...]}

    Note:
        The decorated function should return a dict that becomes
        the "data" field in the JSON envelope. When not in JSON mode,
        the function runs normally (for human-readable output).
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(**kwargs: Any) -> Any:
            # Extract json_output and pretty from kwargs
            json_output = kwargs.pop("json_output", False)
            pretty = kwargs.pop("pretty", False)

            # --pretty implies --json
            if pretty:
                json_output = True
                _pretty_mode.set(True)

            if json_output:
                with json_output_mode(), json_command_mode():
                    try:
                        # Call the wrapped function
                        result = func(**kwargs)

                        # Build and print success envelope
                        envelope = build_envelope(kind, data=result or {})
                        print_json(envelope)
                        raise typer.Exit(EXIT_SUCCESS)

                    except typer.Exit:
                        # Re-raise typer exits (including our own)
                        raise

                    except KeyboardInterrupt:
                        payload = to_json_payload(Exception("Cancelled"))
                        envelope = build_envelope(
                            kind,
                            data={},
                            ok=False,
                            errors=payload["errors"],
                        )
                        print_json(envelope)
                        raise typer.Exit(EXIT_CANCELLED)

                    except Exception as e:
                        exit_code = to_exit_code(e)
                        payload = to_json_payload(e)

                        envelope = build_envelope(
                            kind,
                            data={},
                            ok=False,
                            errors=payload["errors"],
                        )
                        print_json(envelope)
                        raise typer.Exit(exit_code)
            else:
                # Normal human-readable mode
                return func(**kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
