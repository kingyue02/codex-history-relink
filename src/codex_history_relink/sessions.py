from __future__ import annotations

import json
from pathlib import Path

from .file_ops import atomic_write_text, read_text_exact
from .models import SessionRecord


def iter_session_files(sessions_dir: Path):
    if not sessions_dir.exists():
        return
    yield from sessions_dir.rglob("rollout-*.jsonl")


def parse_session(path: Path) -> SessionRecord | None:
    try:
        with path.open(
            "r",
            encoding="utf-8",
            newline="",
        ) as handle:
            first = handle.readline()

        if not first:
            return None

        item = json.loads(
            first.rstrip("\r\n")
        )

    except (OSError, json.JSONDecodeError):
        return None

    if item.get("type") != "session_meta":
        return None

    payload = item.get("payload")
    if not isinstance(payload, dict):
        return None

    tid = str(
        payload.get("id") or ""
    ).strip()

    if not tid:
        return None

    provider = str(
        payload.get("model_provider") or ""
    )

    raw_model = payload.get("model")
    model = str(raw_model) if raw_model else None

    return SessionRecord(
        thread_id=tid,
        path=path,
        provider=provider,
        model=model,
    )


def scan_sessions(
    sessions_dir: Path,
) -> list[SessionRecord]:
    records: list[SessionRecord] = []

    for path in iter_session_files(sessions_dir) or []:
        record = parse_session(path)
        if record:
            records.append(record)

    return records


def mismatched_ids(
    records: list[SessionRecord],
    target_provider: str,
) -> set[str]:
    return {
        record.thread_id
        for record in records
        if record.provider != target_provider
    }


def _split_first_line(
    text: str,
) -> tuple[str, str, str]:
    for ending in ("\r\n", "\n", "\r"):
        index = text.find(ending)
        if index >= 0:
            return (
                text[:index],
                ending,
                text[index + len(ending):],
            )

    return text, "", ""


def replace_first_line(
    path: Path,
    first_line: str,
) -> None:
    text = read_text_exact(path)
    _old, ending, remainder = _split_first_line(text)

    if ending:
        new_text = first_line + ending + remainder
    elif text:
        new_text = first_line
    else:
        new_text = first_line + "\n"

    atomic_write_text(path, new_text)


def rewrite_provider(
    records: list[SessionRecord],
    target_provider: str,
) -> int:
    updated = 0

    for record in records:
        if record.provider == target_provider:
            continue

        text = read_text_exact(record.path)
        first, _ending, _remainder = _split_first_line(text)

        item = json.loads(first)
        payload = item.get("payload")

        if (
            item.get("type") != "session_meta"
            or not isinstance(payload, dict)
        ):
            continue

        payload["model_provider"] = target_provider

        new_first = json.dumps(
            item,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        replace_first_line(
            record.path,
            new_first,
        )

        updated += 1

    return updated
