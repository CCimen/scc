"""Network tool detection rules for command safety analysis.

V1 defense-in-depth layer: detects commands that invoke tools capable of
external network access. This is supplementary to topology+proxy enforcement —
it provides denial UX and audit signals when an agent attempts to shell out
to curl, wget, ssh, etc.

References: D014, D015 in DECISIONS.md.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from .contracts import SafetyVerdict
from .enums import CommandFamily

# Tools that access external network
NETWORK_TOOLS: frozenset[str] = frozenset({"curl", "wget", "ssh", "scp", "sftp", "rsync"})


def analyze_network_tool(tokens: list[str]) -> SafetyVerdict | None:
    """Check if the command invokes a known network access tool.

    Detects both bare names (curl) and path-qualified binaries
    (/usr/bin/curl). The check applies to the first token only —
    network tool names appearing as arguments are ignored.

    Args:
        tokens: Command tokens (after wrapper stripping).

    Returns:
        SafetyVerdict blocking the command if a network tool is detected,
        None if the command is not a network tool.
    """
    if not tokens or not tokens[0]:
        return None

    # Strip path to get the bare binary name
    tool_name = PurePosixPath(tokens[0]).name

    if tool_name in NETWORK_TOOLS:
        return SafetyVerdict(
            allowed=False,
            reason=(
                f"BLOCKED: {tool_name} may access external network. "
                f"Network access is controlled by the egress proxy."
            ),
            matched_rule=f"network.{tool_name}",
            command_family=CommandFamily.NETWORK_TOOL,
        )

    return None
