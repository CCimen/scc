"""Bounded subprocess runner for approved dev-environment commands."""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from typing import IO

from scc_cli.application.dev_environment_bridge import (
    CapturedStream,
    CommandExecutionResult,
    CommandExecutionSpec,
)

STREAM_CHUNK_SIZE = 4096


class _TailBuffer:
    def __init__(self, limit: int) -> None:
        self._limit = max(limit, 0)
        self._tail = bytearray()
        self._total = 0

    def append(self, chunk: bytes) -> None:
        self._total += len(chunk)
        if self._limit == 0:
            self._tail.clear()
            return
        self._tail.extend(chunk)
        if len(self._tail) > self._limit:
            del self._tail[: len(self._tail) - self._limit]

    def captured(self) -> CapturedStream:
        return CapturedStream(
            tail=self._tail.decode("utf-8", errors="replace"),
            total_bytes=self._total,
            truncated=self._total > self._limit,
        )


def run_subprocess_bounded(spec: CommandExecutionSpec) -> CommandExecutionResult:
    """Run a subprocess with bounded stdout/stderr memory."""
    stdout_buffer = _TailBuffer(spec.output_limit_bytes)
    stderr_buffer = _TailBuffer(spec.output_limit_bytes)

    started = time.monotonic()
    try:
        if os.name != "nt":
            process = subprocess.Popen(
                spec.argv,
                cwd=spec.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
                start_new_session=True,
            )
        else:  # pragma: no cover - Windows-specific fallback
            process = subprocess.Popen(
                spec.argv,
                cwd=spec.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
            )
    except OSError as exc:
        stderr_buffer.append(str(exc).encode("utf-8", errors="replace"))
        return CommandExecutionResult(
            exit_code=None,
            timed_out=False,
            stdout=stdout_buffer.captured(),
            stderr=stderr_buffer.captured(),
            duration_ms=int((time.monotonic() - started) * 1000),
        )
    stdout_thread = _drain_stream_thread(process.stdout, stdout_buffer)
    stderr_thread = _drain_stream_thread(process.stderr, stderr_buffer)
    timed_out = False
    exit_code: int | None

    try:
        exit_code = process.wait(timeout=spec.timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        _terminate_process(process)
        exit_code = None

    stdout_thread.join(timeout=1)
    stderr_thread.join(timeout=1)
    duration_ms = int((time.monotonic() - started) * 1000)

    return CommandExecutionResult(
        exit_code=exit_code,
        timed_out=timed_out,
        stdout=stdout_buffer.captured(),
        stderr=stderr_buffer.captured(),
        duration_ms=duration_ms,
    )


def _drain_stream_thread(
    stream: IO[bytes] | None,
    buffer: _TailBuffer,
) -> threading.Thread:
    def drain() -> None:
        if stream is None:
            return
        while True:
            chunk = stream.read(STREAM_CHUNK_SIZE)
            if not chunk:
                break
            buffer.append(chunk)

    thread = threading.Thread(target=drain, daemon=True)
    thread.start()
    return thread


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    if os.name != "nt":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            process.kill()
    else:  # pragma: no cover - Windows-specific fallback
        process.kill()
    process.wait(timeout=1)
