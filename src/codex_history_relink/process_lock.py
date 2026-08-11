from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path


def _lock_windows(handle) -> None:
    import msvcrt

    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError as exc:
        raise RuntimeError(
            "Another CodexHistoryRelink instance is already running."
        ) from exc


def _unlock_windows(handle) -> None:
    import msvcrt

    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass


def _lock_unix(handle) -> None:
    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        raise RuntimeError(
            "Another CodexHistoryRelink instance is already running."
        ) from exc


def _unlock_unix(handle) -> None:
    import fcntl

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass


@contextmanager
def single_instance(lock_path: Path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    handle = lock_path.open("a+b")
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()

        if os.name == "nt":
            _lock_windows(handle)
        else:
            _lock_unix(handle)

        handle.seek(0)
        handle.truncate()
        handle.write(str(os.getpid()).encode("ascii", errors="ignore"))
        handle.flush()

        yield

    finally:
        if os.name == "nt":
            _unlock_windows(handle)
        else:
            _unlock_unix(handle)

        handle.close()

        try:
            lock_path.unlink()
        except OSError:
            pass
