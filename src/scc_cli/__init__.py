"""SCC - Sandboxed Code CLI.

Provide a command-line tool for safely running AI coding agents in Docker sandboxes
with team-specific configurations and worktree management.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("scc-cli")
except PackageNotFoundError:
    # Package not installed (e.g., running from source without install)
    __version__ = "0.0.0-dev"

__author__ = "Cagri Cimen"
