from __future__ import annotations

from pathlib import Path
from typing import Protocol


class PlatformProbe(Protocol):
    """Probe platform-specific behavior for workspace validation.

    Invariants:
        - Results must reflect the local runtime environment.
        - WSL2 detection remains consistent with CLI warnings.
    """

    def is_wsl2(self) -> bool:
        """Return True when running inside WSL2.

        Returns:
            True when the current runtime is WSL2, otherwise False.
        """
        ...

    def check_path_performance(self, path: Path) -> tuple[bool, str | None]:
        """Return whether a path is optimal and an optional warning message.

        Args:
            path: Workspace path to evaluate.

        Returns:
            Tuple of (is_optimal, warning_message). When is_optimal is False,
            warning_message should describe the performance concern.
        """
        ...
