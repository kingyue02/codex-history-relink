from __future__ import annotations

import os
import platform
import sys

from . import __version__


def build_info() -> dict[str, str]:
    return {
        "version": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "build_commit": os.getenv("CODEX_HISTORY_RELINK_BUILD_COMMIT", ""),
        "build_tag": os.getenv("CODEX_HISTORY_RELINK_BUILD_TAG", ""),
    }
