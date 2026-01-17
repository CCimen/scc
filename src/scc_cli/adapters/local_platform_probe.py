from __future__ import annotations

from pathlib import Path

from scc_cli import platform as platform_module
from scc_cli.ports.platform_probe import PlatformProbe


class LocalPlatformProbe(PlatformProbe):
    """Platform probe using local system checks."""

    def is_wsl2(self) -> bool:
        """Return True when running inside WSL2."""
        return platform_module.is_wsl2()

    def check_path_performance(self, path: Path) -> tuple[bool, str | None]:
        """Return whether a path is optimal and an optional warning message."""
        return platform_module.check_path_performance(path)
