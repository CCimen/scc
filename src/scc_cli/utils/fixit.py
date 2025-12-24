"""Provide fix-it command generation utilities.

Generate ready-to-copy commands for blocked or denied items,
helping users quickly unblock themselves.

Two types of fix-it commands:
- Unblock commands: For delegation denials (local override)
- Policy exception commands: For security blocks (requires PR)
"""

from __future__ import annotations

import re
import shutil
from typing import Literal


def get_terminal_width() -> int:
    """Get current terminal width.

    Returns:
        Terminal width in columns. Defaults to 80 if not detectable.
    """
    try:
        size = shutil.get_terminal_size(fallback=(80, 24))
        return max(40, min(size.columns, 500))  # Clamp to reasonable range
    except Exception:
        return 80


def _needs_quoting(value: str) -> bool:
    """Check if a value needs shell quoting.

    Args:
        value: The string to check

    Returns:
        True if the value contains special characters requiring quoting
    """
    # Simple alphanumeric with dashes, underscores, dots, colons, slashes
    safe_pattern = r"^[a-zA-Z0-9_.\-:/]+$"
    return not re.match(safe_pattern, value)


def _shell_quote(value: str) -> str:
    """Quote a value for safe shell usage.

    Uses single quotes to prevent variable expansion.

    Args:
        value: The string to quote

    Returns:
        Safely quoted string
    """
    if not _needs_quoting(value):
        return value

    # Use single quotes, escape any existing single quotes
    escaped = value.replace("'", "'\"'\"'")
    return f"'{escaped}'"


def _target_type_to_flag(target_type: str) -> str:
    """Convert target type to CLI flag name.

    Args:
        target_type: One of "plugin", "mcp_server", "base_image"

    Returns:
        CLI flag name like "--allow-plugin"
    """
    type_map = {
        "plugin": "--allow-plugin",
        "mcp_server": "--allow-mcp",
        "base_image": "--allow-image",
    }
    return type_map.get(target_type, f"--allow-{target_type}")


def generate_unblock_command(
    target: str,
    target_type: str,
    ttl: str = "8h",
) -> str:
    """Generate an unblock command for a delegation denial.

    Args:
        target: The denied item (plugin name, server name, image ref)
        target_type: One of "plugin", "mcp_server", "base_image"
        ttl: Time-to-live for the override (default 8h)

    Returns:
        Ready-to-copy unblock command
    """
    quoted_target = _shell_quote(target)
    return f'scc unblock {quoted_target} --ttl {ttl} --reason "..."'


def generate_policy_exception_command(
    target: str,
    target_type: str,
    ttl: str = "8h",
) -> str:
    """Generate a policy exception command for a security block.

    Args:
        target: The blocked item (plugin name, server name, image ref)
        target_type: One of "plugin", "mcp_server", "base_image"
        ttl: Time-to-live for the exception (default 8h)

    Returns:
        Ready-to-copy policy exception command
    """
    flag = _target_type_to_flag(target_type)
    quoted_target = _shell_quote(target)

    return f'scc exceptions create --policy --id INC-... {flag} {quoted_target} --ttl {ttl} --reason "..."'


def format_command_for_terminal(
    command: str,
    max_width: int | None = None,
    indent: str = "    ",
) -> str:
    """Format a command to fit within terminal width.

    For very long commands, breaks at logical points with backslash continuations.

    Args:
        command: The command to format
        max_width: Maximum line width (defaults to terminal width)
        indent: Indentation for continuation lines

    Returns:
        Formatted command (possibly multi-line)
    """
    if max_width is None:
        max_width = get_terminal_width()

    # If command fits, return as-is
    if len(command) <= max_width:
        return command

    # Try to break at flag boundaries
    parts = []
    current_part = ""

    # Split by spaces, keeping quoted strings together
    tokens = _tokenize_command(command)

    for token in tokens:
        test_line = current_part + (" " if current_part else "") + token

        if len(test_line) > max_width - 2 and current_part:  # -2 for " \"
            parts.append(current_part + " \\")
            current_part = indent + token
        else:
            current_part = test_line

    if current_part:
        parts.append(current_part)

    return "\n".join(parts)


def _tokenize_command(command: str) -> list[str]:
    """Split a command into tokens, respecting quoted strings.

    Args:
        command: The command string

    Returns:
        List of tokens
    """
    tokens = []
    current = ""
    in_quotes = False
    quote_char = ""

    for char in command:
        if char in "\"'" and not in_quotes:
            in_quotes = True
            quote_char = char
            current += char
        elif char == quote_char and in_quotes:
            in_quotes = False
            current += char
        elif char == " " and not in_quotes:
            if current:
                tokens.append(current)
                current = ""
        else:
            current += char

    if current:
        tokens.append(current)

    return tokens


def format_block_message(
    target: str,
    target_type: str,
    block_type: Literal["security", "delegation"],
    blocked_by: str | None = None,
    reason: str | None = None,
) -> str:
    """Format a complete block/denial message with fix-it command.

    Args:
        target: The blocked/denied item
        target_type: One of "plugin", "mcp_server", "base_image"
        block_type: "security" for blocks, "delegation" for denials
        blocked_by: Pattern that caused the block (for security blocks)
        reason: Reason for denial (for delegation denials)

    Returns:
        Formatted message with fix-it command
    """
    lines = []

    if block_type == "security":
        # Security block message
        type_display = _format_target_type(target_type)
        lines.append(f'✗ {type_display} "{target}" blocked by org security policy')

        if blocked_by:
            lines.append(f"  Blocked by: {blocked_by}")

        lines.append("")
        lines.append("  To request policy exception (requires PR approval):")
        cmd = generate_policy_exception_command(target, target_type)
        lines.append(f"    {cmd}")

    else:  # delegation
        # Delegation denial message
        type_display = _format_target_type(target_type)
        denial_reason = reason or "team not delegated for additions"
        lines.append(f'✗ {type_display} "{target}" denied: {denial_reason}')

        lines.append("")
        lines.append("  To unblock locally for 8h:")
        cmd = generate_unblock_command(target, target_type)
        lines.append(f"    {cmd}")

    return "\n".join(lines)


def _format_target_type(target_type: str) -> str:
    """Format target type for display.

    Args:
        target_type: The internal target type

    Returns:
        Human-readable display name
    """
    type_map = {
        "plugin": "Plugin",
        "mcp_server": "MCP server",
        "base_image": "Base image",
    }
    return type_map.get(target_type, target_type.replace("_", " ").title())
