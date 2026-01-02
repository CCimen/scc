"""Compatibility shim - import from scc_cli.core.errors instead."""

from __future__ import annotations

import os
import warnings

# Only emit deprecation warnings when explicitly enabled
# Avoids surprising users with stderr noise
if os.environ.get("SCC_DEBUG") == "1" or os.environ.get("PYTHONWARNINGS"):
    warnings.warn(
        "Importing from scc_cli.errors is deprecated. "
        "Use scc_cli.core.errors instead.",
        DeprecationWarning,
        stacklevel=2,
    )

from .core.errors import *  # noqa: F401, F403, E402
