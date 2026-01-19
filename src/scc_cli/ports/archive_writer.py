"""Archive writer port definition."""

from __future__ import annotations

from typing import Protocol


class ArchiveWriter(Protocol):
    """Write support bundles to an archive destination."""

    def write_manifest(self, output_path: str, manifest_json: str) -> None:
        """Write a manifest JSON file into the archive."""
