"""Local filesystem adapter for Filesystem port."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from scc_cli.ports.filesystem import Filesystem


class LocalFilesystem(Filesystem):
    """Filesystem adapter using the host OS."""

    def read_text(self, path: Path, *, encoding: str = "utf-8") -> str:
        return path.read_text(encoding=encoding)

    def write_text(self, path: Path, content: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding=encoding)

    def write_text_atomic(self, path: Path, content: str, *, encoding: str = "utf-8") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._write_temp_file(path, content, encoding=encoding)
        try:
            temp_path.replace(path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise

    def exists(self, path: Path) -> bool:
        return path.exists()

    def mkdir(self, path: Path, *, parents: bool = False, exist_ok: bool = False) -> None:
        path.mkdir(parents=parents, exist_ok=exist_ok)

    def unlink(self, path: Path, *, missing_ok: bool = False) -> None:
        path.unlink(missing_ok=missing_ok)

    def iterdir(self, path: Path) -> list[Path]:
        return list(path.iterdir())

    def _write_temp_file(self, path: Path, content: str, *, encoding: str) -> Path:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            delete=False,
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        ) as temp_file:
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())
            return Path(temp_file.name)
