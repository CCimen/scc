"""Filesystem port definition for SCC adapters."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Protocol


class Filesystem(Protocol):
    """Filesystem operations required by application use cases."""

    def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:
        """Read text content from a file."""

    def write_text(self, path: Path, content: str, *, encoding: str = "utf-8") -> None:
        """Write text content to a file."""

    def write_text_atomic(self, path: Path, content: str, *, encoding: str = "utf-8") -> None:
        """Write text content atomically within the target directory."""

    def exists(self, path: Path) -> bool:
        """Return True if the path exists."""

    def mkdir(self, path: Path, *, parents: bool = False, exist_ok: bool = False) -> None:
        """Create a directory."""

    def unlink(self, path: Path, *, missing_ok: bool = False) -> None:
        """Remove a file."""

    def iterdir(self, path: Path) -> Iterable[Path]:
        """Iterate directory entries."""
