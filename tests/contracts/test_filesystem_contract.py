"""Contract tests for Filesystem port adapters."""

from __future__ import annotations

from pathlib import Path

from scc_cli.adapters.local_filesystem import LocalFilesystem


def test_write_text_atomic_writes_content(tmp_path: Path) -> None:
    filesystem = LocalFilesystem()
    target = tmp_path / "settings.json"

    filesystem.write_text_atomic(target, "hello")

    assert target.read_text(encoding="utf-8") == "hello"


def test_write_text_atomic_leaves_no_temp_files(tmp_path: Path) -> None:
    filesystem = LocalFilesystem()
    target = tmp_path / "data.txt"

    filesystem.write_text_atomic(target, "content")

    temp_files = [
        path
        for path in target.parent.iterdir()
        if path.name.startswith(f".{target.name}.") and path.suffix == ".tmp"
    ]

    assert temp_files == []


def test_write_text_atomic_overwrites_existing_file(tmp_path: Path) -> None:
    filesystem = LocalFilesystem()
    target = tmp_path / "data.txt"

    filesystem.write_text_atomic(target, "first")
    filesystem.write_text_atomic(target, "second")

    assert target.read_text(encoding="utf-8") == "second"


def test_filesystem_helpers(tmp_path: Path) -> None:
    filesystem = LocalFilesystem()
    directory = tmp_path / "nested" / "dir"

    filesystem.mkdir(directory, parents=True, exist_ok=True)
    assert filesystem.exists(directory)

    file_path = directory / "data.txt"
    filesystem.write_text(file_path, "payload")

    assert filesystem.read_text(file_path) == "payload"
    assert list(filesystem.iterdir(directory)) == [file_path]

    filesystem.unlink(file_path)
    assert not filesystem.exists(file_path)
