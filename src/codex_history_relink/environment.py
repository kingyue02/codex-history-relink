from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

from .models import CodexPaths

STATE_DB_RE = re.compile(r"^state_(\d+)\.sqlite$", re.IGNORECASE)


def resolve_codex_home() -> Path:
    env_home = os.getenv("CODEX_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


def database_activity_ns(path: Path) -> int:
    activity = 0
    for candidate in (path, Path(f"{path}-wal")):
        try:
            activity = max(activity, candidate.stat().st_mtime_ns)
        except FileNotFoundError:
            pass
    return activity


def _thread_columns(path: Path) -> set[str] | None:
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
        try:
            rows = conn.execute("PRAGMA table_info(threads)").fetchall()
            if not rows:
                return None
            return {str(row[1]) for row in rows}
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def is_compatible_database(path: Path) -> bool:
    cols = _thread_columns(path)
    return bool(cols and {"id", "model_provider"}.issubset(cols))


def _candidate_paths(home: Path) -> list[Path]:
    found: dict[str, Path] = {}
    for base in (home, home / "sqlite"):
        if not base.exists():
            continue
        for path in base.glob("state_*.sqlite"):
            if path.is_file():
                found[str(path.resolve())] = path.resolve()
    return list(found.values())


def discover_database(home: Path) -> Path:
    candidates: list[tuple[int, int, int, Path]] = []

    for path in _candidate_paths(home):
        if not is_compatible_database(path):
            continue

        match = STATE_DB_RE.match(path.name)
        version = int(match.group(1)) if match else -1
        activity = database_activity_ns(path)
        root_preference = 1 if path.parent == home else 0
        candidates.append((activity, version, root_preference, path))

    if not candidates:
        raise RuntimeError(
            "No compatible Codex state database was found under "
            f"{home} or {home / 'sqlite'}."
        )

    candidates.sort(
        key=lambda item: (item[0], item[1], item[2]),
        reverse=True,
    )
    return candidates[0][3]


def resolve_paths() -> CodexPaths:
    home = resolve_codex_home()
    if not home.exists():
        raise RuntimeError(f"Codex home does not exist: {home}")

    config = home / "config.toml"
    if not config.exists():
        raise RuntimeError(f"Codex config.toml was not found: {config}")

    database = discover_database(home)

    return CodexPaths(
        home=home,
        config=config,
        database=database,
        sessions_dir=home / "sessions",
        session_index=home / "session_index.jsonl",
        backups_dir=home / "history_sync_backups",
        logs_dir=home / "history_sync_logs",
        process_lock=home / ".history_relink.lock",
        auth=home / "auth.json",
        profiles_dir=home / "history_relink_profiles",
    )
