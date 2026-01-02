"""Compatibility shim - import from scc_cli.commands.org instead."""

from __future__ import annotations

import os
import warnings

if os.environ.get("SCC_DEBUG") == "1" or os.environ.get("PYTHONWARNINGS"):
    warnings.warn(
        "Importing from scc_cli.cli_org is deprecated. Use scc_cli.commands.org instead.",
        DeprecationWarning,
        stacklevel=2,
    )

from .commands.org import *  # noqa: F401, F403, E402
