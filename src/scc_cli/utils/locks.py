"""Simple cross-platform file locking utilities."""

from __future__ import annotations

import errno
import hashlib
import os
import time
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None

try:
    import msvcrt  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover - non-Windows fallback
    msvcrt = None

LOCK_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "scc" / "locks"
DEFAULT_TIMEOUT = 5.0


def _normalize_key(key: str | Path) -> str:
    path = Path(key).expanduser()
    try:
        return str(path.resolve(strict=False))
    except OSError:
        return str(path.absolute())


def lock_path(namespace: str, key: str | Path | None = None) -> Path:
    """Return a stable lock file path for a namespace/key pair."""
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    if key is None:
        filename = f"{namespace}.lock"
    else:
        digest = hashlib.sha256(_normalize_key(key).encode()).hexdigest()[:16]
        filename = f"{namespace}-{digest}.lock"
    return LOCK_DIR / filename


def _acquire_lock(lock_file: os.PathLike[str] | os.PathLike[bytes] | int) -> None:
    if fcntl is not None:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return
    if msvcrt is not None:
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
        return


def _release_lock(lock_file: os.PathLike[str] | os.PathLike[bytes] | int) -> None:
    if fcntl is not None:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        return
    if msvcrt is not None:
        try:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass


@contextmanager
def file_lock(path: Path, *, timeout: float = DEFAULT_TIMEOUT, poll: float = 0.1):
    """Acquire an exclusive file lock with a timeout."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_file = path.open("a+")
    acquired = False
    start = time.monotonic()

    try:
        while True:
            try:
                _acquire_lock(lock_file)
                acquired = True
                break
            except OSError as e:
                if e.errno not in (errno.EACCES, errno.EAGAIN):
                    raise
            except BlockingIOError:
                pass

            if time.monotonic() - start >= timeout:
                raise TimeoutError(f"Timed out waiting for lock: {path}")
            time.sleep(poll)

        try:
            lock_file.seek(0)
            lock_file.truncate()
            lock_file.write(str(os.getpid()))
            lock_file.flush()
        except OSError:
            pass

        yield
    finally:
        if acquired:
            _release_lock(lock_file)
        lock_file.close()
