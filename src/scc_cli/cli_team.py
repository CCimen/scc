"""Compatibility shim - import from scc_cli.commands.team instead."""

from __future__ import annotations

import os
import warnings

if os.environ.get("SCC_DEBUG") == "1" or os.environ.get("PYTHONWARNINGS"):
    warnings.warn(
        "Importing from scc_cli.cli_team is deprecated. Use scc_cli.commands.team instead.",
        DeprecationWarning,
        stacklevel=2,
    )

from .commands.team import *  # noqa: F401, F403, E402
