"""Contract tests for the Filesystem port."""

from __future__ import annotations

from pathlib import Path

from scc_cli.adapters.local_filesystem import LocalFilesystem


def test_write_text_creates_parent_directories(tmp_path: Path) -> None:
    """write_text creates parents before writing content."""
    filesystem = LocalFilesystem()
    target = tmp_path / "nested" / "file.txt"

    filesystem.write_text(target, "hello")

    assert target.exists()
    assert target.read_text(encoding="utf-8") == "hello"


def test_write_text_atomic_overwrites_content(tmp_path: Path) -> None:
    """write_text_atomic overwrites existing content atomically."""
    filesystem = LocalFilesystem()
    target = tmp_path / "atomic" / "file.txt"

    filesystem.write_text_atomic(target, "first")
    filesystem.write_text_atomic(target, "second")

    assert target.read_text(encoding="utf-8") == "second"


def test_write_text_atomic_cleans_temp_files(tmp_path: Path) -> None:
    """write_text_atomic does not leave temp files behind."""
    filesystem = LocalFilesystem()
    target = tmp_path / "atomic" / "notes.txt"

    filesystem.write_text_atomic(target, "content")

    temp_prefix = f".{target.name}."
    temp_files = [path for path in target.parent.iterdir() if path.name.startswith(temp_prefix)]
    assert temp_files == []


def test_read_text_utf8_roundtrip(tmp_path: Path) -> None:
    """read_text returns UTF-8 content unchanged."""
    filesystem = LocalFilesystem()
    target = tmp_path / "utf8.txt"
    content = "café ✓"

    filesystem.write_text(target, content)

    assert filesystem.read_text(target) == content


def test_newline_roundtrip(tmp_path: Path) -> None:
    """Newline content is preserved across write/read."""
    filesystem = LocalFilesystem()
    target = tmp_path / "lines.txt"
    content = "first\nsecond\n"

    filesystem.write_text(target, content)

    assert filesystem.read_text(target) == content


def test_mkdir_parents_and_exist_ok(tmp_path: Path) -> None:
    """mkdir honors parents/exist_ok contract."""
    filesystem = LocalFilesystem()
    target = tmp_path / "one" / "two"

    filesystem.mkdir(target, parents=True, exist_ok=True)
    filesystem.mkdir(target, parents=True, exist_ok=True)

    assert target.exists()
    assert target.is_dir()
