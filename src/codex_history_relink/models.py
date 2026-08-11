from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CodexPaths:
    home: Path
    config: Path
    database: Path
    sessions_dir: Path
    session_index: Path
    backups_dir: Path
    logs_dir: Path
    process_lock: Path


@dataclass(frozen=True)
class ProviderInfo:
    provider: str
    source: str
    explicit: bool


@dataclass(frozen=True)
class SessionRecord:
    thread_id: str
    path: Path
    provider: str
    model: str | None
