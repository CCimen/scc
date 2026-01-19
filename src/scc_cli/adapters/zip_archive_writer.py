"""Archive writer adapter using zipfile."""

from __future__ import annotations

import zipfile

from scc_cli.ports.archive_writer import ArchiveWriter


class ZipArchiveWriter(ArchiveWriter):
    """Archive writer implementation backed by zipfile."""

    def write_manifest(self, output_path: str, manifest_json: str) -> None:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr("manifest.json", manifest_json)
