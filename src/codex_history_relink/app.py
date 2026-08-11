from __future__ import annotations

import sys

from .build_info import build_info
from .environment import resolve_paths
from .logging_utils import (
    error_payload,
    write_fallback_error_log,
    write_result_log,
)
from .process_lock import single_instance
from .relink import relink


def _console_print(
    text: str,
) -> None:
    stream = getattr(
        sys,
        "stdout",
        None,
    )

    if stream is None:
        return

    try:
        print(
            text,
            file=stream,
            flush=True,
        )
    except Exception:
        pass


def main() -> int:
    paths = None

    try:
        paths = resolve_paths()

        with single_instance(
            paths.process_lock
        ):
            result = relink(
                paths
            )

        payload = {
            "ok": True,
            "build": build_info(),
            **result,
        }

        write_result_log(
            paths,
            payload,
        )

        if (
            result.get("changed")
            and not result.get("verified", False)
        ):
            _console_print(
                "Repair failed verification; rollback was attempted."
            )
            return 2

        if result.get("login_required"):
            _console_print(
                str(result.get("message", "Target login required."))
            )
            return 3

        if result.get("changed"):
            _console_print(
                "Codex history relink completed successfully."
            )
        else:
            _console_print(
                "No repair was needed."
            )

        return 0

    except Exception as exc:
        payload = error_payload(
            exc
        )
        payload["build"] = build_info()

        logged = False

        if paths is not None:
            try:
                write_result_log(
                    paths,
                    payload,
                )
                logged = True
            except Exception:
                pass

        if not logged:
            try:
                write_fallback_error_log(
                    payload
                )
            except Exception:
                pass

        _console_print(
            f"Codex history relink failed: {exc}"
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
