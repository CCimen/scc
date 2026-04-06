"""Shell command tokenization with bash -c recursion support.

This module provides POSIX-compliant shell tokenization for analyzing
commands before execution. It handles:
- Command splitting on shell operators (;, &&, ||, |)
- POSIX tokenization via shlex.split()
- Wrapper stripping (sudo, env, command)
- Nested bash -c / sh -c command extraction (depth-limited)
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Iterator

# Max recursion depth for nested bash -c commands
MAX_RECURSION_DEPTH = 3

# Wrappers to strip before analysis
WRAPPER_COMMANDS = frozenset({"sudo", "env", "command", "nice", "nohup", "time"})

# Shell interpreters that take -c for command strings
SHELL_INTERPRETERS = frozenset({"bash", "sh", "zsh", "dash", "ksh"})

# Regex for splitting on shell operators (preserves the operators)
SHELL_OPERATOR_PATTERN = re.compile(r"\s*(;|&&|\|\||\|)\s*")


def split_commands(command: str) -> list[str]:
    """Split a command string on shell operators.

    Args:
        command: Full command string that may contain multiple commands

    Returns:
        List of individual command segments (operators discarded)

    Example:
        >>> split_commands("echo foo && git push --force; ls")
        ['echo foo', 'git push --force', 'ls']
    """
    if not command or not command.strip():
        return []

    # Split on operators but keep non-empty segments
    segments = SHELL_OPERATOR_PATTERN.split(command)

    # Filter out operators and empty strings
    return [
        seg.strip() for seg in segments if seg.strip() and seg.strip() not in (";", "&&", "||", "|")
    ]


def tokenize(segment: str) -> list[str]:
    """Tokenize a command segment using POSIX shell rules.

    Args:
        segment: Single command segment (no shell operators)

    Returns:
        List of tokens, or empty list on parse error

    Example:
        >>> tokenize("git push --force origin main")
        ['git', 'push', '--force', 'origin', 'main']
    """
    if not segment or not segment.strip():
        return []

    try:
        return shlex.split(segment)
    except ValueError:
        # Malformed quotes or other parse errors
        return []


def strip_wrappers(tokens: list[str]) -> list[str]:
    """Remove command wrappers that don't affect the underlying command.

    Strips: sudo, env, command, nice, nohup, time

    Args:
        tokens: List of command tokens

    Returns:
        Tokens with wrappers removed from the front

    Example:
        >>> strip_wrappers(['sudo', '-u', 'root', 'git', 'push'])
        ['git', 'push']
        >>> strip_wrappers(['env', 'VAR=val', 'git', 'push'])
        ['git', 'push']
    """
    if not tokens:
        return []

    result = list(tokens)

    while result:
        cmd = result[0].split("/")[-1]  # Handle /usr/bin/sudo

        if cmd not in WRAPPER_COMMANDS:
            break

        # Remove the wrapper command
        result.pop(0)

        # Skip wrapper-specific arguments
        if cmd == "sudo":
            # sudo can have flags like -u user, -E, etc.
            while result and result[0].startswith("-"):
                flag = result.pop(0)
                # Flags that take an argument
                if flag in ("-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-U"):
                    if result:
                        result.pop(0)
        elif cmd == "env":
            # env: skip VAR=val assignments and -i/-u flags
            while result:
                if "=" in result[0]:
                    result.pop(0)
                elif result[0].startswith("-"):
                    flag = result.pop(0)
                    if flag in ("-u",) and result:
                        result.pop(0)
                else:
                    break
        elif cmd == "nice":
            # nice: skip -n adjustment
            if result and result[0] == "-n" and len(result) > 1:
                result.pop(0)
                result.pop(0)
            elif result and result[0].startswith("-"):
                result.pop(0)
        # command, nohup, time: just remove the wrapper itself

    return result


def extract_bash_c(tokens: list[str]) -> str | None:
    """Extract the command string from bash -c 'command' patterns.

    Args:
        tokens: List of command tokens

    Returns:
        The command string passed to -c, or None if not a bash -c pattern

    Example:
        >>> extract_bash_c(['bash', '-c', 'git push --force'])
        'git push --force'
        >>> extract_bash_c(['sh', '-c', 'echo hello'])
        'echo hello'
    """
    if len(tokens) < 3:
        return None

    # Check if first token is a shell interpreter
    cmd = tokens[0].split("/")[-1]
    if cmd not in SHELL_INTERPRETERS:
        return None

    # Look for -c flag
    try:
        c_index = tokens.index("-c")
        if c_index + 1 < len(tokens):
            return tokens[c_index + 1]
    except ValueError:
        pass

    return None


def extract_all_commands(
    command: str,
    _depth: int = 0,
) -> Iterator[list[str]]:
    """Extract all command token lists from a command string.

    Handles shell operators and bash -c nesting recursively.

    Args:
        command: Command string to analyze
        _depth: Internal recursion depth counter (do not set)

    Yields:
        Token lists for each command found

    Example:
        >>> list(extract_all_commands("bash -c 'git push -f'"))
        [['bash', '-c', 'git push -f'], ['git', 'push', '-f']]
    """
    if _depth > MAX_RECURSION_DEPTH:
        return

    for segment in split_commands(command):
        tokens = tokenize(segment)
        if not tokens:
            continue

        # Strip wrappers first
        stripped = strip_wrappers(tokens)
        if not stripped:
            continue

        # Yield the stripped tokens
        yield stripped

        # Check for bash -c patterns and recurse
        nested_cmd = extract_bash_c(stripped)
        if nested_cmd:
            yield from extract_all_commands(nested_cmd, _depth + 1)
