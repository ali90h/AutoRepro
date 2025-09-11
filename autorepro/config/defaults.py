"""
Centralized default value management for AutoRepro CLI arguments.

This module provides a single source of truth for default values used across CLI
commands, configuration dataclasses, and argument parsing.
"""

from dataclasses import dataclass
from typing import Any

from autorepro.config.models import get_config


@dataclass(frozen=True)
class CLIDefaults:
    """Centralized default values for CLI arguments."""

    # Common argument defaults
    verbose_level: int = 0
    quiet: bool = False
    dry_run: bool = False
    force: bool = False

    # Format and output defaults
    format_type: str = "md"
    valid_formats: tuple[str, ...] = ("md", "json")

    # Plan command defaults
    max_commands: int = 5
    min_score: int = 2
    strict: bool = False

    # Exec command defaults
    exec_index: int = 0
    timeout_seconds: int = 120

    # PR command defaults
    pr_draft: bool = True
    pr_ready: bool = False
    update_if_exists: bool = False
    skip_push: bool = False
    comment: bool = False
    update_pr_body: bool = False
    attach_report: bool = False
    no_details: bool = False

    # Path defaults
    default_plan_file: str = "repro.md"
    devcontainer_dir: str = ".devcontainer"
    devcontainer_file: str = "devcontainer.json"

    @classmethod
    def from_config(cls) -> "CLIDefaults":
        """Create CLIDefaults using values from global configuration."""
        config = get_config()

        return cls(
            # Use config values where available, fall back to class defaults
            max_commands=config.limits.max_plan_suggestions,
            min_score=config.limits.min_score_threshold,
            timeout_seconds=config.timeouts.default_seconds,
            format_type=config.files.default_format,
            valid_formats=config.files.supported_formats,
            default_plan_file=config.paths.default_plan_file,
            devcontainer_dir=config.paths.devcontainer_dir,
            devcontainer_file=config.paths.devcontainer_file,
        )


class DefaultValueProvider:
    """Provides consistent default values for CLI argument groups."""

    def __init__(self, use_config: bool = True):
        """
        Initialize with option to use global config or class defaults.

        Args:
            use_config: If True, use global config values; if False, use class defaults
        """
        self._defaults = CLIDefaults.from_config() if use_config else CLIDefaults()

    @property
    def defaults(self) -> CLIDefaults:
        """Access to the default values."""
        return self._defaults

    def get_plan_defaults(self) -> dict[str, Any]:
        """Get default values for plan command arguments."""
        return {
            "out": self._defaults.default_plan_file,
            "force": self._defaults.force,
            "max_commands": self._defaults.max_commands,
            "format_type": self._defaults.format_type,
            "dry_run": self._defaults.dry_run,
            "strict": self._defaults.strict,
            "min_score": self._defaults.min_score,
        }

    def get_exec_defaults(self) -> dict[str, Any]:
        """Get default values for exec command arguments."""
        return {
            "index": self._defaults.exec_index,
            "timeout": self._defaults.timeout_seconds,
            "env_vars": [],
            "dry_run": self._defaults.dry_run,
            "min_score": self._defaults.min_score,
            "strict": self._defaults.strict,
        }

    def get_pr_defaults(self) -> dict[str, Any]:
        """Get default values for PR command arguments."""
        return {
            "ready": self._defaults.pr_ready,
            "update_if_exists": self._defaults.update_if_exists,
            "comment": self._defaults.comment,
            "update_pr_body": self._defaults.update_pr_body,
            "skip_push": self._defaults.skip_push,
            "attach_report": self._defaults.attach_report,
            "no_details": self._defaults.no_details,
            "format_type": self._defaults.format_type,
            "dry_run": self._defaults.dry_run,
            "min_score": self._defaults.min_score,
            "strict": self._defaults.strict,
        }

    def get_init_defaults(self) -> dict[str, Any]:
        """Get default values for init command arguments."""
        return {
            "force": self._defaults.force,
            "dry_run": self._defaults.dry_run,
        }

    def get_scan_defaults(self) -> dict[str, Any]:
        """Get default values for scan command arguments."""
        return {
            "json_output": False,
            "show_scores": False,
        }

    def get_common_defaults(self) -> dict[str, Any]:
        """Get common default values used across multiple commands."""
        return {
            "verbose": self._defaults.verbose_level,
            "quiet": self._defaults.quiet,
            "dry_run": self._defaults.dry_run,
        }


# Global instance for easy access
_default_provider: DefaultValueProvider | None = None


def get_defaults() -> DefaultValueProvider:
    """Get the global default value provider."""
    global _default_provider
    if _default_provider is None:
        _default_provider = DefaultValueProvider()
    return _default_provider


def reset_defaults() -> None:
    """Reset the global default provider (mainly for testing)."""
    global _default_provider
    _default_provider = None


def with_defaults(
    base_values: dict[str, Any], defaults: dict[str, Any]
) -> dict[str, Any]:
    """
    Merge base values with defaults, giving priority to base values.

    Args:
        base_values: Primary values (e.g., from CLI args)
        defaults: Default values to use if not specified in base_values

    Returns:
        Merged dictionary with base_values taking priority
    """
    result = defaults.copy()
    result.update({k: v for k, v in base_values.items() if v is not None})
    return result
