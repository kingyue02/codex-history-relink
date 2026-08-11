from __future__ import annotations

from .auth_profiles import (
    active_matches_profile,
    capture_active_auth,
    profile_auth_path,
    remove_active_auth,
    restore_profile,
)
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
    target = str(before["current_provider"])

    if int(before["mismatched_threads"]) == 0:
        captured = capture_active_auth(paths, target)
        return {
            "changed": False,
            "verified": True,
            "auth_profile": "captured" if captured else "auth_missing",
            "message": (
                "Local Codex history already matches "
                "the active provider."
            ),
            "status": before,
        }

    counts = list(before["database_provider_counts"])
    source = str(counts[0]["provider"]) if counts else ""
    target_profile = profile_auth_path(paths, target)
    source_profile = profile_auth_path(paths, source) if source else None

    auth_management_active = (
        paths.auth.is_file() or paths.profiles_dir.exists()
    )

    if (
        auth_management_active
        and source
        and source != target
        and target_profile.is_file()
        and source_profile is not None
        and not source_profile.is_file()
        and paths.auth.is_file()
        and not active_matches_profile(paths, target)
    ):
        capture_active_auth(paths, source)

    if (
        auth_management_active
        and source
        and source != target
        and not target_profile.is_file()
    ):
        if source_profile is not None and not source_profile.is_file():
            captured = capture_active_auth(paths, source)

            if captured is None:
                return {
                    "changed": False,
                    "verified": False,
                    "login_required": True,
                    "source_provider": source,
                    "target_provider": target,
                    "auth_profile": "active_auth_missing",
                    "message": (
                        "No active authentication file was found. "
                        "Sign in to the target provider, then run this utility again."
                    ),
                    "status": before,
                }

            remove_active_auth(paths)

            return {
                "changed": False,
                "verified": False,
                "login_required": True,
                "source_provider": source,
                "target_provider": target,
                "auth_profile": "source_captured",
                "message": (
                    "Authentication for the source provider was saved locally. "
                    "Sign in to the target provider, then run this utility again."
                ),
                "status": before,
            }

        if not paths.auth.is_file() or active_matches_profile(paths, source):
            return {
                "changed": False,
                "verified": False,
                "login_required": True,
                "source_provider": source,
                "target_provider": target,
                "auth_profile": "target_missing",
                "message": (
                    "No saved authentication profile exists for the target provider. "
                    "Sign in to the target provider, then run this utility again."
                ),
                "status": before,
            }

        capture_active_auth(paths, target)

    backup = create_backup(paths)

    try:
        auth_restored = restore_profile(paths, target)
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
            "auth_profile": "restored" if auth_restored else "unchanged",
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
