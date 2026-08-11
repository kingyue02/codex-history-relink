from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from .file_ops import atomic_write_bytes, atomic_write_text
from .models import CodexPaths


def _profile_directory(profiles_dir: Path, provider: str) -> Path:
    readable = re.sub(r"[^A-Za-z0-9._-]+", "-", provider).strip(".-")
    readable = readable[:40] or "provider"
    digest = hashlib.sha256(provider.encode("utf-8")).hexdigest()[:12]
    return profiles_dir / f"{readable}-{digest}"


def profile_auth_path(paths: CodexPaths, provider: str) -> Path:
    return _profile_directory(paths.profiles_dir, provider) / "auth.json"


def _restrict_permissions(path: Path, directory: bool = False) -> None:
    try:
        os.chmod(path, 0o700 if directory else 0o600)
    except OSError:
        pass


def save_profile(paths: CodexPaths, provider: str, data: bytes) -> Path:
    directory = _profile_directory(paths.profiles_dir, provider)
    directory.mkdir(parents=True, exist_ok=True)
    _restrict_permissions(paths.profiles_dir, directory=True)
    _restrict_permissions(directory, directory=True)

    auth_path = directory / "auth.json"
    atomic_write_bytes(auth_path, data)
    _restrict_permissions(auth_path)

    metadata_path = directory / "profile.json"
    atomic_write_text(
        metadata_path,
        json.dumps({"provider": provider}, ensure_ascii=False, indent=2) + "\n",
    )
    _restrict_permissions(metadata_path)
    return auth_path


def capture_active_auth(paths: CodexPaths, provider: str) -> Path | None:
    if not paths.auth.is_file():
        return None
    return save_profile(paths, provider, paths.auth.read_bytes())


def restore_profile(paths: CodexPaths, provider: str) -> bool:
    profile = profile_auth_path(paths, provider)
    if not profile.is_file():
        return False
    atomic_write_bytes(paths.auth, profile.read_bytes())
    _restrict_permissions(paths.auth)
    return True


def active_matches_profile(paths: CodexPaths, provider: str) -> bool:
    profile = profile_auth_path(paths, provider)
    if not paths.auth.is_file() or not profile.is_file():
        return False
    return paths.auth.read_bytes() == profile.read_bytes()


def remove_active_auth(paths: CodexPaths) -> bool:
    try:
        paths.auth.unlink()
        return True
    except FileNotFoundError:
        return False
