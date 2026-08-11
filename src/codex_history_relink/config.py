from __future__ import annotations

from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from .models import ProviderInfo

DEFAULT_PROVIDER = "openai"


def load_config(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def detect_provider(path: Path) -> ProviderInfo:
    config = load_config(path)
    raw = config.get("model_provider")

    if isinstance(raw, str) and raw.strip():
        return ProviderInfo(
            provider=raw.strip(),
            source="config.toml:model_provider",
            explicit=True,
        )

    return ProviderInfo(
        provider=DEFAULT_PROVIDER,
        source="implicit-default",
        explicit=False,
    )
