"""Provide exception store implementations for SCC Phase 2.1.

Define storage backends for time-bounded exceptions:
- UserStore: Personal exceptions in ~/.config/scc/exceptions.json
- RepoStore: Shared repo exceptions in .scc/exceptions.json

Both stores implement the ExceptionStore protocol and handle:
- Reading/writing exception files with proper JSON formatting
- Pruning expired exceptions
- Backup-on-corrupt recovery
- Forward compatibility warnings for newer schema versions
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

import scc_cli.config
from scc_cli.console import err_line
from scc_cli.models.exceptions import ExceptionFile

# Current schema version supported by this implementation
CURRENT_SCHEMA_VERSION = 1


def _get_config_dir() -> Path:
    """Get CONFIG_DIR dynamically to support test patching."""
    return scc_cli.config.CONFIG_DIR


class ExceptionStore(Protocol):
    """Protocol for exception stores.

    All stores must implement these methods for consistent behavior
    across user and repo scopes.
    """

    @property
    def path(self) -> Path:
        """Return the path to the exceptions file."""
        ...

    def read(self) -> ExceptionFile:
        """Read exceptions from storage.

        Returns:
            ExceptionFile with current exceptions.
            Returns empty ExceptionFile if file doesn't exist.
            On corruption, backs up file and returns empty.
            On newer schema, warns and returns empty (fail-open for local).
        """
        ...

    def write(self, file: ExceptionFile) -> None:
        """Write exceptions to storage.

        Creates parent directories if needed.
        Uses deterministic JSON serialization (sorted keys, 2-space indent).
        """
        ...

    def prune_expired(self) -> int:
        """Remove expired exceptions from storage.

        Returns:
            Count of pruned exceptions.
        """
        ...

    def backup(self) -> Path | None:
        """Create a backup of the current file.

        Returns:
            Path to backup file, or None if no file exists.
        """
        ...

    def reset(self) -> None:
        """Remove the exceptions file entirely."""
        ...


class UserStore:
    """User-scoped exception store.

    Stores personal exceptions at ~/.config/scc/exceptions.json.
    These are machine-local and not shared with team.
    """

    @property
    def path(self) -> Path:
        """Return the path to the exceptions file."""
        return _get_config_dir() / "exceptions.json"

    def read(self) -> ExceptionFile:
        """Read exceptions from user store."""
        if not self.path.exists():
            return ExceptionFile()

        try:
            content = self.path.read_text()
            data = json.loads(content)
        except json.JSONDecodeError:
            # Corrupt file - backup and return empty
            self._backup_corrupt()
            return ExceptionFile()

        # Check schema version
        schema_version = data.get("schema_version", 1)
        if schema_version > CURRENT_SCHEMA_VERSION:
            # Newer schema - warn and ignore (fail-open for local stores)
            err_line(
                f"⚠️ {self.path} was created by newer SCC (schema v{schema_version}).\n"
                f"   Local overrides ignored until you upgrade. Run: pip install --upgrade scc"
            )
            return ExceptionFile()

        return ExceptionFile.from_dict(data)

    def write(self, file: ExceptionFile) -> None:
        """Write exceptions to user store."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(file.to_json())

    def prune_expired(self) -> int:
        """Remove expired exceptions from user store."""
        ef = self.read()
        original_count = len(ef.exceptions)

        # Filter to active only
        ef.exceptions = [e for e in ef.exceptions if not e.is_expired()]

        pruned_count = original_count - len(ef.exceptions)
        if pruned_count > 0:
            self.write(ef)

        return pruned_count

    def backup(self) -> Path | None:
        """Create backup of user store."""
        if not self.path.exists():
            return None

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup_path = self.path.parent / f"{self.path.name}.bak-{timestamp}"
        backup_path.write_text(self.path.read_text())
        return backup_path

    def reset(self) -> None:
        """Remove user store file."""
        if self.path.exists():
            self.path.unlink()

    def _backup_corrupt(self) -> None:
        """Backup corrupt file and warn user."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        backup_path = self.path.parent / f"{self.path.name}.bak-{timestamp}"
        backup_path.write_text(self.path.read_text())
        err_line(
            f"⚠️ Local exceptions file corrupted. Backed up to {backup_path}.\n"
            f"   Run `scc doctor` for details."
        )


class RepoStore:
    """Repo-scoped exception store.

    Stores shared exceptions at <repo>/.scc/exceptions.json.
    These can be committed (team-shared) or gitignored (personal repo workarounds).
    """

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root
        self._path = repo_root / ".scc" / "exceptions.json"

    @property
    def path(self) -> Path:
        """Return the path to the exceptions file."""
        return self._path

    def read(self) -> ExceptionFile:
        """Read exceptions from repo store."""
        if not self._path.exists():
            return ExceptionFile()

        try:
            content = self._path.read_text()
            data = json.loads(content)
        except json.JSONDecodeError:
            # Corrupt file - backup and return empty
            self._backup_corrupt()
            return ExceptionFile()

        # Check schema version
        schema_version = data.get("schema_version", 1)
        if schema_version > CURRENT_SCHEMA_VERSION:
            # Newer schema - warn and ignore (fail-open for local stores)
            err_line(
                f"⚠️ {self._path} was created by newer SCC (schema v{schema_version}).\n"
                f"   Local overrides ignored until you upgrade. Run: pip install --upgrade scc"
            )
            return ExceptionFile()

        return ExceptionFile.from_dict(data)

    def write(self, file: ExceptionFile) -> None:
        """Write exceptions to repo store."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(file.to_json())

    def prune_expired(self) -> int:
        """Remove expired exceptions from repo store."""
        ef = self.read()
        original_count = len(ef.exceptions)

        # Filter to active only
        ef.exceptions = [e for e in ef.exceptions if not e.is_expired()]

        pruned_count = original_count - len(ef.exceptions)
        if pruned_count > 0:
            self.write(ef)

        return pruned_count

    def backup(self) -> Path | None:
        """Create backup of repo store."""
        if not self._path.exists():
            return None

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup_path = self._path.with_suffix(f".json.bak-{timestamp}")
        backup_path.write_text(self._path.read_text())
        return backup_path

    def reset(self) -> None:
        """Remove repo store file."""
        if self._path.exists():
            self._path.unlink()

    def _backup_corrupt(self) -> None:
        """Backup corrupt file and warn user."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        backup_path = self._path.with_suffix(f".json.bak-{timestamp}")
        backup_path.write_text(self._path.read_text())
        err_line(
            f"⚠️ Repo exceptions file corrupted. Backed up to {backup_path}.\n"
            f"   Run `scc doctor` for details."
        )
