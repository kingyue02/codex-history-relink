from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .file_ops import atomic_write_text

WRITE_RETRIES = 40
WRITE_TIMEOUT_SECONDS = 0.5
WRITE_RETRY_SECONDS = 0.25


@contextmanager
def connect(
    path: Path,
    readonly: bool = False,
    timeout_seconds: float = 30.0,
) -> Iterator[sqlite3.Connection]:
    if readonly:
        conn = sqlite3.connect(
            f"file:{path}?mode=ro",
            uri=True,
            timeout=timeout_seconds,
        )
    else:
        conn = sqlite3.connect(
            str(path),
            timeout=timeout_seconds,
        )

    try:
        conn.row_factory = sqlite3.Row
        conn.execute(
            f"PRAGMA busy_timeout = {max(1, int(timeout_seconds * 1000))}"
        )
        yield conn
    finally:
        conn.close()


def thread_columns(conn: sqlite3.Connection) -> set[str]:
    return {
        str(row["name"])
        for row in conn.execute("PRAGMA table_info(threads)")
    }


def validate_schema(path: Path) -> set[str]:
    with connect(path, readonly=True) as conn:
        cols = thread_columns(conn)

    required = {"id", "model_provider"}
    missing = required - cols

    if missing:
        raise RuntimeError(
            f"Unsupported Codex database schema; missing columns: {sorted(missing)}"
        )

    return cols


def provider_counts(path: Path) -> list[dict[str, object]]:
    with connect(path, readonly=True) as conn:
        rows = conn.execute(
            """
            SELECT COALESCE(model_provider, '(empty)') AS provider, COUNT(*) AS count
            FROM threads
            GROUP BY model_provider
            ORDER BY COUNT(*) DESC, provider ASC
            """
        ).fetchall()

    return [
        {
            "provider": str(row["provider"]),
            "count": int(row["count"]),
        }
        for row in rows
    ]


def mismatched_ids(path: Path, target_provider: str) -> set[str]:
    with connect(path, readonly=True) as conn:
        return {
            str(row["id"])
            for row in conn.execute(
                """
                SELECT id
                FROM threads
                WHERE model_provider IS NULL OR model_provider <> ?
                """,
                (target_provider,),
            )
        }


def update_provider(path: Path, target_provider: str) -> int:
    last_error: Exception | None = None

    for attempt in range(WRITE_RETRIES):
        try:
            with connect(
                path,
                readonly=False,
                timeout_seconds=WRITE_TIMEOUT_SECONDS,
            ) as conn:
                conn.execute("BEGIN IMMEDIATE")
                updated = conn.execute(
                    """
                    UPDATE threads
                    SET model_provider = ?
                    WHERE model_provider IS NULL OR model_provider <> ?
                    """,
                    (target_provider, target_provider),
                ).rowcount
                conn.commit()

                try:
                    conn.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
                except sqlite3.Error:
                    pass

                return int(updated)

        except sqlite3.OperationalError as exc:
            last_error = exc
            lowered = str(exc).lower()

            if "locked" not in lowered and "busy" not in lowered:
                raise

            if attempt < WRITE_RETRIES - 1:
                time.sleep(WRITE_RETRY_SECONDS)

    raise RuntimeError(
        "Codex state database stayed locked/busy. "
        "Close Codex or leave it idle, then run CodexHistoryRelink again."
    ) from last_error


def restore_database_from_backup(
    backup_path: Path,
    target_path: Path,
) -> None:
    last_error: Exception | None = None

    for attempt in range(WRITE_RETRIES):
        source = None
        target = None
        try:
            source = sqlite3.connect(
                f"file:{backup_path}?mode=ro",
                uri=True,
                timeout=WRITE_TIMEOUT_SECONDS,
            )
            target = sqlite3.connect(
                str(target_path),
                timeout=WRITE_TIMEOUT_SECONDS,
            )

            target.execute(
                f"PRAGMA busy_timeout = {int(WRITE_TIMEOUT_SECONDS * 1000)}"
            )
            source.backup(target)
            target.commit()

            try:
                target.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
            except sqlite3.Error:
                pass

            return

        except sqlite3.OperationalError as exc:
            last_error = exc
            lowered = str(exc).lower()

            if "locked" not in lowered and "busy" not in lowered:
                raise

            if attempt < WRITE_RETRIES - 1:
                time.sleep(WRITE_RETRY_SECONDS)

        finally:
            if target is not None:
                target.close()
            if source is not None:
                source.close()

    raise RuntimeError(
        "Could not restore the Codex database because it stayed locked/busy."
    ) from last_error


def read_index(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}

    entries: dict[str, dict[str, str]] = {}

    for line in path.read_text(
        encoding="utf-8",
    ).splitlines():
        if not line.strip():
            continue

        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue

        tid = str(item.get("id") or "").strip()
        if not tid:
            continue

        entries[tid] = {
            "id": tid,
            "thread_name": str(item.get("thread_name") or tid),
            "updated_at": str(item.get("updated_at") or ""),
        }

    return entries


def _iso_timestamp(value: object) -> str:
    if value is None:
        return ""

    try:
        raw = int(value)
    except (TypeError, ValueError):
        return str(value)

    return datetime.fromtimestamp(
        raw,
        tz=timezone.utc,
    ).isoformat().replace("+00:00", "Z")


def rebuild_index(
    db_path: Path,
    index_path: Path,
) -> dict[str, int]:
    existing = read_index(index_path)

    with connect(db_path, readonly=True) as conn:
        cols = thread_columns(conn)

        select = ["id"]
        if "title" in cols:
            select.append("title")
        if "updated_at" in cols:
            select.append("updated_at")

        where = "WHERE archived = 0" if "archived" in cols else ""

        rows = conn.execute(
            f"SELECT {', '.join(select)} FROM threads {where} ORDER BY id ASC"
        ).fetchall()

    db_ids = {
        str(row["id"])
        for row in rows
    }

    merged: list[dict[str, str]] = []

    for row in rows:
        tid = str(row["id"])
        prior = existing.get(tid, {})

        title = (
            str(row["title"])
            if "title" in row.keys() and row["title"]
            else tid
        )

        updated = (
            _iso_timestamp(row["updated_at"])
            if "updated_at" in row.keys()
            else ""
        )

        merged.append(
            {
                "id": tid,
                "thread_name": str(prior.get("thread_name") or title),
                "updated_at": str(prior.get("updated_at") or updated),
            }
        )

    for tid, entry in existing.items():
        if tid not in db_ids:
            merged.append(entry)

    merged.sort(
        key=lambda item: (
            item.get("updated_at", ""),
            item.get("id", ""),
        )
    )

    content = "\n".join(
        json.dumps(
            item,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        for item in merged
    )

    if content:
        content += "\n"

    atomic_write_text(index_path, content)

    return {
        "rewritten_entries": len(merged),
        "preserved_index_only_entries": len(set(existing) - db_ids),
    }
