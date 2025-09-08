"""
GitHub operations configuration for AutoRepro.

This module provides configuration dataclasses for GitHub operations to reduce
function parameter counts and improve maintainability.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class GitHubOperationConfig:
    """Configuration for GitHub operations like comments and PR updates."""

    gh_path: str = "gh"
    dry_run: bool = False
    replace_block: bool = True

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.gh_path:
            raise ValueError("gh_path cannot be empty")


@dataclass
class PlanGenerationConfig:
    """Configuration for plan generation operations."""

    format_type: str = "md"
    min_score: int = 2
    max_commands: int = 5
    repo_path: Path | None = None

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.format_type not in ("md", "json"):
            raise ValueError(f"format_type must be 'md' or 'json', got: {self.format_type}")
        if self.min_score < 0:
            raise ValueError(f"min_score must be non-negative, got: {self.min_score}")
        if self.max_commands <= 0:
            raise ValueError(f"max_commands must be positive, got: {self.max_commands}")


@dataclass
class CommentOperationRequest:
    """Request object for comment operations (create/update)."""

    target_id: int  # PR number or issue number
    body: str
    config: GitHubOperationConfig

    def __post_init__(self) -> None:
        """Validate request after initialization."""
        if self.target_id <= 0:
            raise ValueError(f"target_id must be positive, got: {self.target_id}")
        if not self.body.strip():
            raise ValueError("body cannot be empty")


@dataclass
class PlanGenerationRequest:
    """Request object for plan generation operations."""

    desc_or_file: str | None
    config: PlanGenerationConfig

    def __post_init__(self) -> None:
        """Validate request after initialization."""
        if not self.desc_or_file:
            raise ValueError("desc_or_file cannot be empty")
