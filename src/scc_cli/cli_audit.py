"""Compatibility shim - import from scc_cli.commands.audit instead."""

from __future__ import annotations

import os
import warnings

if os.environ.get("SCC_DEBUG") == "1" or os.environ.get("PYTHONWARNINGS"):
    warnings.warn(
        "Importing from scc_cli.cli_audit is deprecated. Use scc_cli.commands.audit instead.",
        DeprecationWarning,
        stacklevel=2,
    )

from .commands.audit import *  # noqa: F401, F403, E402
