"""Configuration models for AutoRepro.

This module provides type-safe configuration with environment variable support
and validation. All defaults match the original hard-coded values to maintain
backward compatibility.
"""

import os
from dataclasses import dataclass, field


@dataclass
class TimeoutConfig:
    """Timeout configuration for various operations."""

    default_seconds: int = 120  # Default subprocess timeout

    @classmethod
    def from_env(cls) -> "TimeoutConfig":
        """Create TimeoutConfig from environment variables."""
        return cls(default_seconds=int(os.getenv("AUTOREPRO_TIMEOUT_DEFAULT", "120")))


@dataclass
class LimitsConfig:
    """Limits and thresholds for various operations."""

    max_plan_suggestions: int = 5  # Maximum commands in plan output
    min_score_threshold: int = 2  # Minimum score for command filtering
    max_display_length: int = 80  # Maximum length for display values

    @classmethod
    def from_env(cls) -> "LimitsConfig":
        """Create LimitsConfig from environment variables."""
        return cls(
            max_plan_suggestions=int(os.getenv("AUTOREPRO_MAX_PLAN_SUGGESTIONS", "5")),
            min_score_threshold=int(os.getenv("AUTOREPRO_MIN_SCORE_THRESHOLD", "2")),
            max_display_length=int(os.getenv("AUTOREPRO_MAX_DISPLAY_LENGTH", "80")),
        )


@dataclass
class PathConfig:
    """File and directory path configuration."""

    devcontainer_dir: str = ".devcontainer"
    devcontainer_file: str = "devcontainer.json"
    default_plan_file: str = "repro.md"
    temp_file_suffix: str = ".tmp"

    @classmethod
    def from_env(cls) -> "PathConfig":
        """Create PathConfig from environment variables."""
        return cls(
            devcontainer_dir=os.getenv("AUTOREPRO_DEVCONTAINER_DIR", ".devcontainer"),
            devcontainer_file=os.getenv("AUTOREPRO_DEVCONTAINER_FILE", "devcontainer.json"),
            default_plan_file=os.getenv("AUTOREPRO_DEFAULT_PLAN_FILE", "repro.md"),
            temp_file_suffix=os.getenv("AUTOREPRO_TEMP_FILE_SUFFIX", ".tmp"),
        )


@dataclass
class DetectionConfig:
    """Language detection algorithm configuration."""

    weights: dict[str, int] = field(
        default_factory=lambda: {
            "lock": 4,  # Lock files have highest weight
            "config": 3,  # Config/manifest files
            "setup": 2,  # Setup/requirements files
            "source": 1,  # Source files have lowest weight
        }
    )

    @classmethod
    def from_env(cls) -> "DetectionConfig":
        """Create DetectionConfig from environment variables."""
        weights = {
            "lock": int(os.getenv("AUTOREPRO_DETECTION_WEIGHT_LOCK", "4")),
            "config": int(os.getenv("AUTOREPRO_DETECTION_WEIGHT_CONFIG", "3")),
            "setup": int(os.getenv("AUTOREPRO_DETECTION_WEIGHT_SETUP", "2")),
            "source": int(os.getenv("AUTOREPRO_DETECTION_WEIGHT_SOURCE", "1")),
        }
        return cls(weights=weights)


@dataclass
class ExitCodeConfig:
    """Exit codes for different scenarios."""

    success: int = 0
    error: int = 1
    invalid_args: int = 2

    @classmethod
    def from_env(cls) -> "ExitCodeConfig":
        """Create ExitCodeConfig from environment variables."""
        return cls(
            success=int(os.getenv("AUTOREPRO_EXIT_CODE_SUCCESS", "0")),
            error=int(os.getenv("AUTOREPRO_EXIT_CODE_ERROR", "1")),
            invalid_args=int(os.getenv("AUTOREPRO_EXIT_CODE_INVALID_ARGS", "2")),
        )


@dataclass
class FileConfig:
    """File extension and format configuration."""

    python_extension: str = ".py"
    javascript_extension: str = ".js"
    typescript_extension: str = ".ts"
    json_extension: str = ".json"
    markdown_extension: str = ".md"
    yaml_extension: str = ".yaml"

    default_format: str = "md"
    supported_formats: tuple = ("md", "json")

    @classmethod
    def from_env(cls) -> "FileConfig":
        """Create FileConfig from environment variables."""
        return cls(
            python_extension=os.getenv("AUTOREPRO_PYTHON_EXT", ".py"),
            javascript_extension=os.getenv("AUTOREPRO_JS_EXT", ".js"),
            typescript_extension=os.getenv("AUTOREPRO_TS_EXT", ".ts"),
            json_extension=os.getenv("AUTOREPRO_JSON_EXT", ".json"),
            markdown_extension=os.getenv("AUTOREPRO_MD_EXT", ".md"),
            yaml_extension=os.getenv("AUTOREPRO_YAML_EXT", ".yaml"),
            default_format=os.getenv("AUTOREPRO_DEFAULT_FORMAT", "md"),
            supported_formats=tuple(os.getenv("AUTOREPRO_SUPPORTED_FORMATS", "md,json").split(",")),
        )


@dataclass
class ExecutableConfig:
    """Executable names and paths configuration."""

    python_names: tuple = ("python3", "python")

    @classmethod
    def from_env(cls) -> "ExecutableConfig":
        """Create ExecutableConfig from environment variables."""
        python_names_str = os.getenv("AUTOREPRO_PYTHON_NAMES", "python3,python")
        return cls(python_names=tuple(python_names_str.split(",")))


@dataclass
class AutoReproConfig:
    """Main configuration container for AutoRepro."""

    timeouts: TimeoutConfig = field(default_factory=TimeoutConfig)
    limits: LimitsConfig = field(default_factory=LimitsConfig)
    paths: PathConfig = field(default_factory=PathConfig)
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    exit_codes: ExitCodeConfig = field(default_factory=ExitCodeConfig)
    files: FileConfig = field(default_factory=FileConfig)
    executables: ExecutableConfig = field(default_factory=ExecutableConfig)

    @classmethod
    def from_env(cls) -> "AutoReproConfig":
        """Create configuration from environment variables."""
        return cls(
            timeouts=TimeoutConfig.from_env(),
            limits=LimitsConfig.from_env(),
            paths=PathConfig.from_env(),
            detection=DetectionConfig.from_env(),
            exit_codes=ExitCodeConfig.from_env(),
            files=FileConfig.from_env(),
            executables=ExecutableConfig.from_env(),
        )

    def validate(self) -> None:
        """Validate configuration values and fail fast if invalid."""
        if self.timeouts.default_seconds <= 0:
            raise ValueError("Timeout must be positive")

        if self.limits.max_plan_suggestions <= 0:
            raise ValueError("Max plan suggestions must be positive")

        if self.limits.min_score_threshold < 0:
            raise ValueError("Min score threshold must be non-negative")

        if self.files.default_format not in self.files.supported_formats:
            raise ValueError(
                f"Default format '{self.files.default_format}' not in supported formats "
                f"{self.files.supported_formats}"
            )


# Global configuration instance
_config_instance: AutoReproConfig | None = None


def get_config() -> AutoReproConfig:
    """Get the global configuration instance, creating it if needed."""
    global _config_instance
    if _config_instance is None:
        _config_instance = AutoReproConfig.from_env()
        _config_instance.validate()
    return _config_instance


def reset_config() -> None:
    """Reset the global configuration instance (mainly for testing)."""
    global _config_instance
    _config_instance = None
