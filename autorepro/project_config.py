"""
Project-level configuration loader for AutoRepro.

Supports reading `.autorepro.toml` from a repository root, with optional
named profiles. Provides a minimal API so CLI can merge settings with
precedence: CLI > environment > config file > built-in defaults.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ProjectSettings:
    """Resolved project settings for the active profile."""

    min_score: int | None = None
    strict: bool | None = None
    plugins: list[str] | None = None
    verbosity: str | None = None  # quiet|normal|verbose


def load_config(repo: Path) -> dict[str, Any]:
    """
    Load `.autorepro.toml` from repository root if present.

    Returns an empty dict if file not found or unreadable.
    """
    cfg_path = Path(repo) / ".autorepro.toml"
    try:
        if not cfg_path.exists():
            return {}
        with cfg_path.open("rb") as f:
            return tomllib.load(f) or {}
    except OSError:
        return {}


def _as_bool(val: Any) -> bool | None:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        lower = val.strip().lower()
        if lower in {"1", "true", "yes", "on"}:
            return True
        if lower in {"0", "false", "no", "off"}:
            return False
    return None


def _normalize_settings(raw: dict[str, Any]) -> ProjectSettings:
    min_score = raw.get("min_score")
    if isinstance(min_score, str) and min_score.isdigit():
        min_score = int(min_score)
    elif not isinstance(min_score, int):
        min_score = None

    strict = _as_bool(raw.get("strict"))

    plugins = raw.get("plugins")
    if isinstance(plugins, list):
        plugins = [str(p) for p in plugins]
    else:
        plugins = None

    verbosity = raw.get("verbosity")
    if isinstance(verbosity, str):
        v = verbosity.strip().lower()
        if v not in {"quiet", "normal", "verbose"}:
            verbosity = None
        else:
            verbosity = v
    else:
        verbosity = None

    return ProjectSettings(
        min_score=min_score, strict=strict, plugins=plugins, verbosity=verbosity
    )


def resolve_profile(cfg: dict[str, Any], name: str | None) -> ProjectSettings:
    """
    Resolve defaults + optional profile into a ProjectSettings instance.

    - Base is `[defaults]` table
    - If `name` is provided and exists under `[profiles.NAME]`, overlay it.
    """
    defaults = cfg.get("defaults", {}) if isinstance(cfg.get("defaults"), dict) else {}
    resolved: dict[str, Any] = dict(defaults)

    if name and isinstance(cfg.get("profiles"), dict):
        profiles = cfg["profiles"]
        if isinstance(profiles.get(name), dict):
            resolved.update(profiles[name])

    return _normalize_settings(resolved)
