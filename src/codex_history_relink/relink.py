from __future__ import annotations

from .backup import (
    MAX_BACKUPS,
    create_backup,
    restore_backup,
    rotate_backups,
)
from .config import detect_provider
from .database import (
    mismatched_ids as db_mismatched_ids,
    provider_counts,
    rebuild_index,
    update_provider,
    validate_schema,
)
from .models import CodexPaths
from .sessions import (
    mismatched_ids as session_mismatched_ids,
    rewrite_provider,
    scan_sessions,
)


def inspect(
    paths: CodexPaths,
) -> dict[str, object]:
    validate_schema(
        paths.database
    )

    provider = detect_provider(
        paths.config
    )

    sessions = scan_sessions(
        paths.sessions_dir
    )

    db_mismatch = db_mismatched_ids(
        paths.database,
        provider.provider,
    )

    session_mismatch = session_mismatched_ids(
        sessions,
        provider.provider,
    )

    return {
        "current_provider": provider.provider,
        "provider_source": provider.source,
        "provider_explicit": provider.explicit,
        "database": str(paths.database),
        "database_provider_counts": provider_counts(
            paths.database
        ),
        "session_file_count": len(sessions),
        "mismatched_database_threads": len(
            db_mismatch
        ),
        "mismatched_session_threads": len(
            session_mismatch
        ),
        "mismatched_threads": len(
            db_mismatch | session_mismatch
        ),
    }


def relink(
    paths: CodexPaths,
) -> dict[str, object]:
    before = inspect(paths)

    if int(before["mismatched_threads"]) == 0:
        return {
            "changed": False,
            "verified": True,
            "message": (
                "Local Codex history already matches "
                "the active provider."
            ),
            "status": before,
        }

    backup = create_backup(paths)
    target = str(before["current_provider"])

    try:
        updated_rows = update_provider(
            paths.database,
            target,
        )

        sessions = scan_sessions(
            paths.sessions_dir
        )

        updated_sessions = rewrite_provider(
            sessions,
            target,
        )

        index_summary = rebuild_index(
            paths.database,
            paths.session_index,
        )

        after = inspect(paths)
        verified = (
            int(after["mismatched_threads"]) == 0
        )

        if not verified:
            rollback = restore_backup(
                paths,
                backup,
            )

            return {
                "changed": True,
                "verified": False,
                "rolled_back": True,
                "target_provider": target,
                "backup_path": str(backup),
                "updated_rows": updated_rows,
                "updated_session_files": updated_sessions,
                "index": index_summary,
                "rollback": rollback,
                "status": inspect(paths),
            }

        rotation = rotate_backups(
            paths,
            keep=MAX_BACKUPS,
        )

        return {
            "changed": True,
            "verified": True,
            "rolled_back": False,
            "target_provider": target,
            "backup_path": str(backup),
            "updated_rows": updated_rows,
            "updated_session_files": updated_sessions,
            "index": index_summary,
            "backup_rotation": rotation,
            "status": after,
        }

    except Exception as repair_error:
        rollback_error = None
        rollback_summary = None

        try:
            rollback_summary = restore_backup(
                paths,
                backup,
            )
        except Exception as exc:
            rollback_error = str(exc)

        message = (
            f"Repair failed: {repair_error}. "
            "Automatic rollback was attempted."
        )

        if rollback_error:
            message += (
                f" Rollback also failed: {rollback_error}"
            )

        error = RuntimeError(message)
        error.rollback_summary = rollback_summary
        error.rollback_error = rollback_error
        raise error from repair_error
