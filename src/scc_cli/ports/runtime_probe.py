"""Runtime probe port definition."""

from __future__ import annotations

from typing import Protocol

from scc_cli.core.contracts import RuntimeInfo


class RuntimeProbe(Protocol):
    """Probe the local runtime environment and return capability information.

    Invariants:
        - probe() never raises; it returns the truthful detected state.
        - The returned RuntimeInfo reflects the current host environment.
    """

    def probe(self) -> RuntimeInfo:
        """Detect runtime capabilities and return a populated RuntimeInfo.

        Returns:
            RuntimeInfo describing the detected runtime backend.
        """
        ...
