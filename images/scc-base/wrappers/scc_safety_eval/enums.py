"""Stripped-down enums for the standalone safety evaluator.

Contains only CommandFamily — the minimal surface needed for
runtime safety classification without any host CLI dependency.
"""

from __future__ import annotations

from enum import Enum


class CommandFamily(str, Enum):
    """High-level command family for safety classification."""

    DESTRUCTIVE_GIT = "destructive-git"
    NETWORK_TOOL = "network-tool"
