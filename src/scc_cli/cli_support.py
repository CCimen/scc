"""Compatibility shim - import from scc_cli.commands.support instead."""

from __future__ import annotations

import os
import warnings

# Only emit deprecation warnings when explicitly enabled
if os.environ.get("SCC_DEBUG") == "1" or os.environ.get("PYTHONWARNINGS"):
    warnings.warn(
        "Importing from scc_cli.cli_support is deprecated. Use scc_cli.commands.support instead.",
        DeprecationWarning,
        stacklevel=2,
    )

from .commands.support import *  # noqa: F401, F403, E402
