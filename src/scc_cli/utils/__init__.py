"""Utility modules for SCC CLI."""

from scc_cli.utils.fixit import (
    format_block_message,
    format_command_for_terminal,
    generate_policy_exception_command,
    generate_unblock_command,
    get_terminal_width,
)
from scc_cli.utils.ttl import (
    DEFAULT_TTL,
    MAX_TTL,
    calculate_expiration,
    format_expiration,
    format_relative,
    parse_expires_at,
    parse_ttl,
    parse_until,
    validate_ttl_duration,
)

__all__ = [
    # TTL utilities
    "DEFAULT_TTL",
    "MAX_TTL",
    "calculate_expiration",
    "format_expiration",
    "format_relative",
    "parse_expires_at",
    "parse_ttl",
    "parse_until",
    "validate_ttl_duration",
    # Fix-it utilities
    "format_block_message",
    "format_command_for_terminal",
    "generate_policy_exception_command",
    "generate_unblock_command",
    "get_terminal_width",
]
