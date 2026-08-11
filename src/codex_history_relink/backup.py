from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .database import restore_database_from_backup
from .file_ops import (
    atomic_write_bytes,
    atomic_write_text,
)
from .models import CodexPaths
from .sessions import (
    iter_session_files,
    replace_first_line,
)

MAX_BACKUPS = 5
BACKUP_MARKER = ".pre-relink."


def session_index_backup_path(
    backup_path: Path,
) -> Path:
    return backup_path.with_name(
        backup_path.name + ".session_index.jsonl"
    )


def session_meta_backup_path(
    backup_path: Path,
) -> Path:
    return backup_path.with_name(
        backup_path.name + ".session_meta.json"
    )


def manifest_backup_path(
    backup_path: Path,
) -> Path:
    return backup_path.with_name(
        backup_path.name + ".manifest.json"
    )


def _sqlite_backup(
    source: Path,
    target: Path,
) -> None:
    src = sqlite3.connect(
        f"file:{source}?mode=ro",
        uri=True,
        timeout=30,
    )
    dst = sqlite3.connect(
        str(target),
        timeout=30,
    )

    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def create_backup(
    paths: CodexPaths,
) -> Path:
    paths.backups_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    stamp = datetime.now().strftime(
        "%Y%m%d-%H%M%S-%f"
    )

    backup = (
        paths.backups_dir
        / f"{paths.database.name}{BACKUP_MARKER}{stamp}.bak"
    )

    _sqlite_backup(
        paths.database,
        backup,
    )

    index_existed = paths.session_index.exists()

    if index_existed:
        atomic_write_bytes(
            session_index_backup_path(backup),
            paths.session_index.read_bytes(),
        )

    metadata: list[dict[str, str]] = []

    for path in iter_session_files(
        paths.sessions_dir
    ) or []:
        try:
            with path.open(
                "r",
                encoding="utf-8",
                newline="",
            ) as handle:
                first = handle.readline().rstrip("\r\n")

            metadata.append(
                {
                    "path": str(
                        path.relative_to(paths.home)
                    ),
                    "first_line": first,
                }
            )

        except OSError:
            continue

    atomic_write_text(
        session_meta_backup_path(backup),
        json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )

    manifest = {
        "database": str(paths.database),
        "session_index_existed": index_existed,
    }

    atomic_write_text(
        manifest_backup_path(backup),
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )

    return backup


def restore_backup(
    paths: CodexPaths,
    backup_path: Path,
) -> dict[str, object]:
    restored_session_files = 0
    restored_index = False

    restore_database_from_backup(
        backup_path,
        paths.database,
    )

    manifest_path = manifest_backup_path(
        backup_path
    )
    manifest = {}

    if manifest_path.exists():
        manifest = json.loads(
            manifest_path.read_text(
                encoding="utf-8"
            )
        )

    index_backup = session_index_backup_path(
        backup_path
    )

    if manifest.get("session_index_existed"):
        if index_backup.exists():
            atomic_write_bytes(
                paths.session_index,
                index_backup.read_bytes(),
            )
            restored_index = True
    else:
        try:
            paths.session_index.unlink()
        except FileNotFoundError:
            pass

    meta_backup = session_meta_backup_path(
        backup_path
    )

    if meta_backup.exists():
        items = json.loads(
            meta_backup.read_text(
                encoding="utf-8"
            )
        )

        for item in items:
            raw = Path(item["path"])
            path = (
                raw
                if raw.is_absolute()
                else paths.home / raw
            )

            if not path.exists():
                continue

            replace_first_line(
                path,
                str(item["first_line"]),
            )
            restored_session_files += 1

    return {
        "database_restored": True,
        "session_index_restored": restored_index,
        "session_files_restored": restored_session_files,
    }


def _primary_backups(
    paths: CodexPaths,
) -> list[Path]:
    if not paths.backups_dir.exists():
        return []

    backups = [
        path
        for path in paths.backups_dir.glob(
            "state_*.sqlite.pre-relink.*.bak"
        )
        if path.is_file()
    ]

    backups.sort(
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )

    return backups


def rotate_backups(
    paths: CodexPaths,
    keep: int = MAX_BACKUPS,
) -> dict[str, object]:
    keep = max(
        int(keep),
        1,
    )

    backups = _primary_backups(paths)
    stale = backups[keep:]

    deleted_sets = 0
    deleted_files = 0

    for primary in stale:
        members = [
            primary,
            session_index_backup_path(primary),
            session_meta_backup_path(primary),
            manifest_backup_path(primary),
        ]

        set_deleted = False

        for member in members:
            try:
                member.unlink()
                deleted_files += 1
                set_deleted = True
            except FileNotFoundError:
                pass

        if set_deleted:
            deleted_sets += 1

    return {
        "keep": keep,
        "remaining_backup_sets": len(
            _primary_backups(paths)
        ),
        "deleted_backup_sets": deleted_sets,
        "deleted_files": deleted_files,
    }
