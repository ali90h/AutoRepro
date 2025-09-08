"""
Enhanced dataclass-based argument groups for AutoRepro CLI.

This module demonstrates improved argument handling using dataclasses with:
- Centralized validation using the CommonConfigValidator
- Default values from the centralized defaults system
- Better organization and type safety
- Consistent validation patterns
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from autorepro.config.defaults import get_defaults
from autorepro.config.exceptions import CrossFieldValidationError, FieldValidationError
from autorepro.utils.cli_validation import CommonConfigValidator, ConfigValidationMixin


@dataclass
class BaseCommandConfig(ConfigValidationMixin):
    """Base configuration class with common CLI arguments."""

    verbose: int = field(default_factory=lambda: get_defaults().defaults.verbose_level)
    quiet: bool = field(default_factory=lambda: get_defaults().defaults.quiet)
    dry_run: bool = field(default_factory=lambda: get_defaults().defaults.dry_run)

    def validate_base_fields(self) -> None:
        """Validate base configuration fields."""
        errors = self._validate_common_fields(
            verbose=(CommonConfigValidator.validate_non_negative_integer, self.verbose, "verbose"),
        )

        if errors:
            raise FieldValidationError("; ".join(errors), field="base")


@dataclass
class InputConfig(ConfigValidationMixin):
    """Configuration for input arguments (desc/file mutual exclusivity)."""

    desc: str | None = None
    file: str | None = None

    def validate(self) -> None:
        """Validate input configuration."""
        error = CommonConfigValidator.validate_desc_file_mutual_exclusivity(self.desc, self.file)
        if error:
            raise CrossFieldValidationError(error, field="desc,file")


@dataclass
class OutputConfig(ConfigValidationMixin):
    """Configuration for output-related arguments."""

    out: str = field(default_factory=lambda: get_defaults().defaults.default_plan_file)
    format_type: str = field(default_factory=lambda: get_defaults().defaults.format_type)
    force: bool = field(default_factory=lambda: get_defaults().defaults.force)

    def validate(self) -> None:
        """Validate output configuration."""
        errors = self._validate_common_fields(
            format_type=(
                CommonConfigValidator.validate_format_choice,
                self.format_type,
                get_defaults().defaults.valid_formats,
            ),
        )

        if errors:
            raise FieldValidationError("; ".join(errors), field="output")


@dataclass
class RepositoryConfig(ConfigValidationMixin):
    """Configuration for repository-related arguments."""

    repo: str | None = None
    repo_path: Path | None = None

    def validate(self) -> None:
        """Validate repository configuration."""
        from autorepro.utils.cli_validation import ArgumentValidator

        error = ArgumentValidator.validate_repo_path(self.repo)
        if error:
            raise FieldValidationError(error, field="repo")

        # Set repo_path if repo is provided
        if self.repo and not self.repo_path:
            self.repo_path = Path(self.repo).resolve()


@dataclass
class ScoringConfig(ConfigValidationMixin):
    """Configuration for command scoring and filtering."""

    min_score: int = field(default_factory=lambda: get_defaults().defaults.min_score)
    strict: bool = field(default_factory=lambda: get_defaults().defaults.strict)

    def validate(self) -> None:
        """Validate scoring configuration."""
        errors = self._validate_common_fields(
            min_score=(
                CommonConfigValidator.validate_non_negative_integer,
                self.min_score,
                "min_score",
            ),
        )

        if errors:
            raise FieldValidationError("; ".join(errors), field="scoring")


@dataclass
class EnhancedPlanConfig(
    BaseCommandConfig, InputConfig, OutputConfig, RepositoryConfig, ScoringConfig
):
    """Enhanced plan configuration using composition of argument groups."""

    max_commands: int = field(default_factory=lambda: get_defaults().defaults.max_commands)
    print_to_stdout: bool = False

    def validate(self) -> None:
        """Validate all configuration groups."""
        # Validate each group
        self.validate_base_fields()
        InputConfig.validate(self)
        OutputConfig.validate(self)
        RepositoryConfig.validate(self)
        ScoringConfig.validate(self)

        # Additional plan-specific validation
        errors = self._validate_common_fields(
            max_commands=(
                CommonConfigValidator.validate_positive_integer,
                self.max_commands,
                "max_commands",
            ),
        )

        if errors:
            raise FieldValidationError("; ".join(errors), field="plan")

    @classmethod
    def from_args(cls, **kwargs) -> "EnhancedPlanConfig":
        """Create config from CLI arguments with defaults."""
        defaults = get_defaults().get_plan_defaults()
        merged_args = {**defaults, **kwargs}
        return cls(**merged_args)


@dataclass
class ExecutionConfig(ConfigValidationMixin):
    """Configuration for command execution arguments."""

    index: int = field(default_factory=lambda: get_defaults().defaults.exec_index)
    timeout: int = field(default_factory=lambda: get_defaults().defaults.timeout_seconds)
    env_vars: list[str] = field(default_factory=list)
    env_file: str | None = None
    tee_path: str | None = None
    jsonl_path: str | None = None

    def validate(self) -> None:
        """Validate execution configuration."""
        errors = self._validate_common_fields(
            index=(CommonConfigValidator.validate_non_negative_integer, self.index, "index"),
            timeout=(CommonConfigValidator.validate_positive_integer, self.timeout, "timeout"),
        )

        if errors:
            raise FieldValidationError("; ".join(errors), field="execution")


@dataclass
class EnhancedExecConfig(
    BaseCommandConfig, InputConfig, RepositoryConfig, ScoringConfig, ExecutionConfig
):
    """Enhanced exec configuration using composition of argument groups."""

    def validate(self) -> None:
        """Validate all configuration groups."""
        self.validate_base_fields()
        InputConfig.validate(self)
        RepositoryConfig.validate(self)
        ScoringConfig.validate(self)
        ExecutionConfig.validate(self)

    @classmethod
    def from_args(cls, **kwargs) -> "EnhancedExecConfig":
        """Create config from CLI arguments with defaults."""
        defaults = get_defaults().get_exec_defaults()
        merged_args = {**defaults, **kwargs}
        return cls(**merged_args)


@dataclass
class GitHubConfig(ConfigValidationMixin):
    """Configuration for GitHub-related arguments."""

    repo_slug: str | None = None
    title: str | None = None
    body: str | None = None
    ready: bool = field(default_factory=lambda: get_defaults().defaults.pr_ready)
    label: list[str] | None = None
    assignee: list[str] | None = None
    reviewer: list[str] | None = None

    def validate(self) -> None:
        """Validate GitHub configuration."""
        error = CommonConfigValidator.validate_repo_slug_format(self.repo_slug)
        if error:
            raise FieldValidationError(error, field="repo_slug")


@dataclass
class PROperationConfig(ConfigValidationMixin):
    """Configuration for PR operation arguments."""

    update_if_exists: bool = field(default_factory=lambda: get_defaults().defaults.update_if_exists)
    skip_push: bool = field(default_factory=lambda: get_defaults().defaults.skip_push)
    comment: bool = field(default_factory=lambda: get_defaults().defaults.comment)
    update_pr_body: bool = field(default_factory=lambda: get_defaults().defaults.update_pr_body)
    link_issue: int | None = None
    add_labels: str | None = None
    attach_report: bool = field(default_factory=lambda: get_defaults().defaults.attach_report)
    summary: str | None = None
    no_details: bool = field(default_factory=lambda: get_defaults().defaults.no_details)

    def validate(self) -> None:
        """Validate PR operation configuration."""
        if self.link_issue is not None:
            error = CommonConfigValidator.validate_non_negative_integer(
                self.link_issue, "link_issue"
            )
            if error:
                raise FieldValidationError(error, field="link_issue")


@dataclass
class EnhancedPrConfig(
    BaseCommandConfig, InputConfig, OutputConfig, ScoringConfig, GitHubConfig, PROperationConfig
):
    """Enhanced PR configuration using composition of argument groups."""

    def validate(self) -> None:
        """Validate all configuration groups."""
        self.validate_base_fields()
        InputConfig.validate(self)
        OutputConfig.validate(self)
        ScoringConfig.validate(self)
        GitHubConfig.validate(self)
        PROperationConfig.validate(self)

    @classmethod
    def from_args(cls, **kwargs) -> "EnhancedPrConfig":
        """Create config from CLI arguments with defaults."""
        defaults = get_defaults().get_pr_defaults()
        merged_args = {**defaults, **kwargs}
        return cls(**merged_args)


@dataclass
class EnhancedInitConfig(BaseCommandConfig, OutputConfig, RepositoryConfig):
    """Enhanced init configuration using composition of argument groups."""

    def validate(self) -> None:
        """Validate all configuration groups."""
        self.validate_base_fields()
        OutputConfig.validate(self)
        RepositoryConfig.validate(self)

    @classmethod
    def from_args(cls, **kwargs) -> "EnhancedInitConfig":
        """Create config from CLI arguments with defaults."""
        defaults = get_defaults().get_init_defaults()
        merged_args = {**defaults, **kwargs}
        return cls(**merged_args)


# Utility function to demonstrate usage
def create_config_from_args(command: str, **kwargs: Any) -> Any:
    """Factory function to create appropriate config based on command."""
    if command == "plan":
        return EnhancedPlanConfig.from_args(**kwargs)
    elif command == "exec":
        return EnhancedExecConfig.from_args(**kwargs)
    elif command == "pr":
        return EnhancedPrConfig.from_args(**kwargs)
    elif command == "init":
        return EnhancedInitConfig.from_args(**kwargs)
    else:
        raise ValueError(f"Unknown command: {command}")
