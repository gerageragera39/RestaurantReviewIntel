"""Small, strict JSON configuration; CLI overrides are applied by cli.py."""

import json
from dataclasses import dataclass, fields
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ScrapeConfig:
    limit: int = 50
    headed: bool = True
    timeout_ms: int = 30_000
    collection_timeout_ms: int = 180_000
    max_scroll_iterations: int = 100
    max_idle_iterations: int = 5
    scroll_wait_ms: int = 1_500
    debug: bool = False
    debug_dir: Path = Path("data/debug")
    export_dir: Path = Path("data/exports")
    profile_dir: Path | None = None
    report_dir: Path = Path("data/reports")

    def __post_init__(self) -> None:
        if type(self.limit) is not int or self.limit < 0:
            raise ValueError("limit must be a non-negative integer (0 means unlimited)")
        for name in ("timeout_ms", "collection_timeout_ms", "max_scroll_iterations", "max_idle_iterations", "scroll_wait_ms"):
            value = getattr(self, name)
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        for name in ("headed", "debug"):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be a boolean")
        for name in ("export_dir", "debug_dir", "report_dir"):
            if not isinstance(getattr(self, name), Path):
                raise ValueError(f"{name} must be a Path")
        if self.profile_dir is not None and not isinstance(self.profile_dir, Path):
            raise ValueError("profile_dir must be a Path or None")


def load_config(path: Path | None) -> ScrapeConfig:
    if path is None:
        return ScrapeConfig()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"Cannot read config {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("config must be a JSON object")
    unknown = data.keys() - {field.name for field in fields(ScrapeConfig)}
    if unknown:
        raise ValueError(f"Unknown config keys: {', '.join(sorted(unknown))}")
    for name in ("export_dir", "debug_dir", "report_dir", "profile_dir"):
        if name in data:
            if name == "profile_dir" and data[name] is None:
                continue
            if not isinstance(data[name], str) or not data[name].strip():
                raise ValueError(f"{name} must be a non-empty path string")
            data[name] = Path(data[name])
    return ScrapeConfig(**data)
