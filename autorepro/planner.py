"""
AutoRepro planner module for generating reproduction plans from issue descriptions.

This module provides a legacy compatibility layer. The actual implementations have been
moved to the layered architecture in core/, render/, and utils/.
"""

from typing import TypedDict

# Import all functions from the new layered architecture
from .core.planning import (
    KEYWORD_PATTERNS,
    extract_keywords,
    normalize,
    safe_truncate_60,
    suggest_commands,
)
from .render.formats import build_repro_json, build_repro_md


class CommandCandidate(TypedDict):
    """Type for command candidate with scoring metadata."""

    cmd: str
    score: int
    matched_keywords: list[str]
    detected_langs: list[str]
    bonuses: list[str]
    source: str


# Re-export all functions for backward compatibility
__all__ = [
    "KEYWORD_PATTERNS",
    "CommandCandidate",
    "extract_keywords",
    "normalize",
    "safe_truncate_60",
    "suggest_commands",
    "build_repro_json",
    "build_repro_md",
]
