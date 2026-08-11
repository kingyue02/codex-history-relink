from __future__ import annotations

import json
import traceback
from datetime import datetime
from pathlib import Path

from .file_ops import atomic_write_text
from .models import CodexPaths


def _summary_text(
    payload: dict[str, object],
) -> str:
    if not payload.get("ok"):
        return (
            "Codex History Relink: FAILED\n"
            f"Error: {payload.get('error', 'Unknown error')}\n"
        )

    if not payload.get("changed"):
        status = payload.get("status") or {}

        return (
            "Codex History Relink: OK - no repair needed\n"
            f"Provider: {status.get('current_provider', '')}\n"
            f"Database: {status.get('database', '')}\n"
            f"Mismatched threads: {status.get('mismatched_threads', 0)}\n"
        )

    return (
        "Codex History Relink: "
        + (
            "SUCCESS\n"
            if payload.get("verified")
            else "VERIFY FAILED - ROLLBACK ATTEMPTED\n"
        )
        + f"Target provider: {payload.get('target_provider', '')}\n"
        + f"Database rows updated: {payload.get('updated_rows', 0)}\n"
        + f"Session files updated: {payload.get('updated_session_files', 0)}\n"
        + f"Backup: {payload.get('backup_path', '')}\n"
        + f"Rolled back: {payload.get('rolled_back', False)}\n"
    )


def write_result_log(
    paths: CodexPaths,
    payload: dict[str, object],
) -> Path:
    paths.logs_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    stamp = datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )

    dated = (
        paths.logs_dir
        / f"history-relink-{stamp}.json"
    )

    json_text = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        default=str,
    ) + "\n"

    atomic_write_text(
        dated,
        json_text,
    )

    atomic_write_text(
        paths.logs_dir / "latest.json",
        json_text,
    )

    atomic_write_text(
        paths.logs_dir / "latest.txt",
        _summary_text(payload),
    )

    return dated


def write_fallback_error_log(
    payload: dict[str, object],
) -> Path:
    path = (
        Path.home()
        / "CodexHistoryRelink-error.txt"
    )

    text = (
        "Codex History Relink failed before the normal "
        "Codex log directory could be resolved.\n\n"
        f"Error: {payload.get('error', 'Unknown error')}\n\n"
        f"{payload.get('traceback', '')}"
    )

    atomic_write_text(
        path,
        text,
    )

    return path


def error_payload(
    exc: Exception,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "ok": False,
        "error": str(exc),
        "traceback": traceback.format_exc(),
    }

    rollback_summary = getattr(
        exc,
        "rollback_summary",
        None,
    )
    rollback_error = getattr(
        exc,
        "rollback_error",
        None,
    )

    if rollback_summary is not None:
        payload["rollback"] = rollback_summary

    if rollback_error is not None:
        payload["rollback_error"] = rollback_error

    return payload
