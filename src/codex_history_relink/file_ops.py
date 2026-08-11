from __future__ import annotations

import errno
import os
import time
from pathlib import Path

FILE_REPLACE_RETRY_LIMIT = 20
FILE_REPLACE_RETRY_DELAY_SECONDS = 0.15


def read_text_exact(path: Path) -> str:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def _is_retryable_replace_error(exc: OSError) -> bool:
    if isinstance(exc, PermissionError):
        return True

    if getattr(exc, "winerror", None) in (5, 32, 33):
        return True

    return getattr(exc, "errno", None) in (
        errno.EACCES,
        errno.EBUSY,
        errno.EPERM,
    )


def replace_file_with_retry(source: Path, target: Path) -> None:
    last_error: OSError | None = None

    for attempt in range(FILE_REPLACE_RETRY_LIMIT):
        try:
            os.replace(source, target)
            return
        except OSError as exc:
            if not _is_retryable_replace_error(exc):
                raise
            last_error = exc

        if attempt < FILE_REPLACE_RETRY_LIMIT - 1:
            time.sleep(FILE_REPLACE_RETRY_DELAY_SECONDS)

    raise RuntimeError(
        f"File stayed busy and could not be atomically replaced: {target}"
    ) from last_error


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(
        f".{path.name}.history-relink-{os.getpid()}-{time.time_ns()}.tmp"
    )

    try:
        with temp.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())

        replace_file_with_retry(temp, path)

    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))
