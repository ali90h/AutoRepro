"""
Plan generation service for AutoRepro.

This module provides a clean, organized approach to plan generation by separating
concerns into focused service classes that handle specific aspects of the workflow.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from autorepro.cli import (
    PlanConfig,
    PlanData,
    build_repro_json,
    build_repro_md,
    ensure_trailing_newline,
    extract_keywords,
    normalize,
    safe_truncate_60,
    suggest_commands,
    temp_chdir,
)
from autorepro.detect import detect_languages
from autorepro.utils.file_ops import FileOperations
from autorepro.utils.validation_helpers import (
    has_ci_keywords,
    has_installation_keywords,
    has_test_keywords,
)


class PlanInputHandler:
    """Handles input reading and validation for plan generation."""

    @staticmethod
    def read_input_text(config: PlanConfig) -> str:
        """Read input text from description or file with clean error handling."""
        if config.desc is not None:
            return config.desc

        if config.file is not None:
            return PlanInputHandler._read_from_file(config.file, config.repo_path)

        raise ValueError("Either --desc or --file must be specified")

    @staticmethod
    def _read_from_file(file_path: str, repo_path: Path | None) -> str:
        """Read content from file with fallback logic."""
        path = Path(file_path)

        # Try absolute path first
        if path.is_absolute():
            return PlanInputHandler._safe_read_file(path)

        # Try current working directory
        try:
            return PlanInputHandler._safe_read_file(path)
        except OSError:
            # Fallback to repo-relative path if available
            if repo_path:
                repo_file_path = repo_path / file_path
                return PlanInputHandler._safe_read_file(repo_file_path)
            raise

    @staticmethod
    def _safe_read_file(file_path: Path) -> str:
        """Safely read file content with proper error handling."""
        try:
            with open(file_path, encoding="utf-8") as f:
                return f.read()
        except OSError as e:
            log = logging.getLogger("autorepro")
            log.error(f"Error reading file {file_path}: {e}")
            raise OSError(f"Error reading file {file_path}: {e}") from e


class PlanConfigurationManager:
    """Manages plan configuration preparation and validation."""

    @staticmethod
    def prepare_config(config: PlanConfig) -> PlanConfig:
        """Prepare and validate plan configuration."""
        # Validate configuration
        config.validate()
        PlanConfigurationManager._validate_input_exclusivity(config)
        PlanConfigurationManager._resolve_repo_path(config)
        PlanConfigurationManager._configure_output_settings(config)

        return config

    @staticmethod
    def _validate_input_exclusivity(config: PlanConfig) -> None:
        """Validate that desc and file are mutually exclusive."""
        if config.desc and config.file:
            raise ValueError("Cannot specify both --desc and --file")
        if not config.desc and not config.file:
            raise ValueError("Must specify either --desc or --file")

    @staticmethod
    def _resolve_repo_path(config: PlanConfig) -> None:
        """Resolve and validate repository path."""
        import sys

        if config.repo is None:
            return

        try:
            config.repo_path = Path(config.repo).resolve()
            if not config.repo_path.is_dir():
                print(
                    f"Error: --repo path does not exist or is not a directory: {config.repo}",
                    file=sys.stderr,
                )
                raise ValueError("Invalid repo path")
        except (OSError, ValueError):
            print(
                f"Error: --repo path does not exist or is not a directory: {config.repo}",
                file=sys.stderr,
            )
            raise ValueError("Invalid repo path") from None

    @staticmethod
    def _configure_output_settings(config: PlanConfig) -> None:
        """Configure output path and stdout settings."""
        # Handle stdout output
        config.print_to_stdout = config.out == "-"

        # Update output path to be repo-relative if needed
        if (
            config.repo_path
            and not Path(config.out).is_absolute()
            and not config.print_to_stdout
        ):
            config.out = str(config.repo_path / config.out)

        # Handle dry-run mode
        if config.dry_run:
            config.print_to_stdout = True


class PlanContentGenerator:
    """Generates plan content including suggestions, assumptions, and environment
    needs."""

    def __init__(self, config: PlanConfig):
        self.config = config
        self.log = logging.getLogger("autorepro")

    def generate_suggestions(
        self, text: str
    ) -> tuple[set[str], list[str], list[Any], int]:
        """Generate command suggestions from input text."""
        # Process the text
        normalized_text = normalize(text)
        keywords = extract_keywords(normalized_text)

        # Get detected languages
        lang_names = self._detect_languages()

        # Generate and filter suggestions
        suggestions = suggest_commands(keywords, lang_names, self.config.min_score)
        self._validate_strict_mode(suggestions)

        # Calculate filtering stats
        total_commands = len(suggest_commands(keywords, lang_names, min_score=0))
        filtered_count = total_commands - len(suggestions)
        self._log_filtering_info(filtered_count)

        return keywords, lang_names, suggestions, filtered_count

    def generate_assumptions(
        self, lang_names: list[str], keywords: set[str], filtered_count: int
    ) -> list[str]:
        """Generate plan assumptions based on context."""
        assumptions = []

        # Language-based assumptions
        if lang_names:
            lang_list = ", ".join(lang_names)
            assumptions.append(f"Project uses {lang_list} based on detected files")
        else:
            assumptions.append("Standard development environment")

        # Keyword-based assumptions
        assumptions.extend(self._generate_keyword_assumptions(keywords))

        # Add filtering information if relevant
        self._add_filtering_assumptions(assumptions, filtered_count)

        return assumptions if assumptions else ["Issue can be reproduced locally"]

    def generate_environment_needs(
        self, lang_names: list[str], keywords: set[str]
    ) -> list[str]:
        """Generate environment requirements based on detected languages."""
        needs = []

        # Check for devcontainer
        if self._has_devcontainer():
            needs.append("devcontainer: present")

        # Add language-specific needs
        for lang in lang_names:
            needs.extend(self._get_language_needs(lang, keywords))

        return needs if needs else ["Standard development environment"]

    def _detect_languages(self) -> list[str]:
        """Detect languages in the project directory."""
        if self.config.repo_path:
            with temp_chdir(self.config.repo_path):
                detected_languages = detect_languages(".")
        else:
            detected_languages = detect_languages(".")
        return [lang for lang, _ in detected_languages]

    def _validate_strict_mode(self, suggestions: list[Any]) -> None:
        """Validate strict mode requirements."""
        if self.config.strict and not suggestions:
            error_msg = f"no candidate commands above min-score={self.config.min_score}"
            self.log.error(error_msg)
            raise ValueError(error_msg)

    def _log_filtering_info(self, filtered_count: int) -> None:
        """Log information about filtered suggestions."""
        if filtered_count > 0:
            self.log.info(f"filtered {filtered_count} low-score suggestions")

    def _generate_keyword_assumptions(self, keywords: set[str]) -> list[str]:
        """Generate assumptions based on keywords."""
        assumptions = []
        if has_test_keywords(keywords):
            assumptions.append("Issue is related to testing")
        if has_ci_keywords(keywords):
            assumptions.append("Issue occurs in CI/CD environment")
        if has_installation_keywords(keywords):
            assumptions.append("Installation or setup may be involved")
        return assumptions

    def _add_filtering_assumptions(
        self, assumptions: list[str], filtered_count: int
    ) -> None:
        """Add filtering information to assumptions if relevant."""
        if filtered_count > 0 and self._should_show_filtering_note():
            assumptions.append(
                f"Filtered {filtered_count} low-scoring command suggestions "
                f"(min-score={self.config.min_score})"
            )

    def _should_show_filtering_note(self) -> bool:
        """Determine if filtering note should be shown."""
        from autorepro.config import config as autorepro_config

        min_score_explicit = (
            self.config.min_score != autorepro_config.limits.min_score_threshold
        )
        return min_score_explicit or self.config.strict

    def _has_devcontainer(self) -> bool:
        """Check if devcontainer configuration exists."""
        if self.config.repo_path:
            devcontainer_dir = self.config.repo_path / ".devcontainer/devcontainer.json"
            devcontainer_root = self.config.repo_path / "devcontainer.json"
        else:
            devcontainer_dir = Path(".devcontainer/devcontainer.json")
            devcontainer_root = Path("devcontainer.json")

        return devcontainer_dir.exists() or devcontainer_root.exists()

    def _get_language_needs(self, lang: str, keywords: set[str]) -> list[str]:
        """Get environment needs for a specific language."""
        needs = []

        if lang == "python":
            needs.append("Python 3.7+")
            if "pytest" in keywords:
                needs.append("pytest package")
            if "tox" in keywords:
                needs.append("tox package")
        elif lang in ("node", "javascript"):
            needs.extend(["Node.js 16+", "npm or yarn"])
        elif lang == "go":
            needs.append("Go 1.19+")

        return needs


class PlanOutputHandler:
    """Handles plan output formatting and writing."""

    @staticmethod
    def output_plan(plan_data: PlanData, config: PlanConfig) -> int:
        """Output plan in the requested format and location."""
        # Validate output path
        if error_code := PlanOutputHandler._validate_output_path(config):
            return error_code

        # Check for existing files
        if not config.print_to_stdout and PlanOutputHandler._should_skip_existing_file(
            config
        ):
            print(f"{config.out} exists; use --force to overwrite")
            return 0

        # Generate and write content
        content = PlanOutputHandler._generate_content(plan_data, config)
        return PlanOutputHandler._write_output(content, config)

    @staticmethod
    def _validate_output_path(config: PlanConfig) -> int | None:
        """Validate output path and return error code if invalid."""
        if not config.print_to_stdout and config.out and os.path.isdir(config.out):
            print(f"Error: Output path is a directory: {config.out}")
            return 2
        return None

    @staticmethod
    def _should_skip_existing_file(config: PlanConfig) -> bool:
        """Check if we should skip writing due to existing file."""
        return os.path.exists(config.out) and not config.force

    @staticmethod
    def _generate_content(plan_data: PlanData, config: PlanConfig) -> str:
        """Generate content in the requested format."""
        if config.format_type == "json":
            return PlanOutputHandler._generate_json_content(plan_data)
        return PlanOutputHandler._generate_markdown_content(plan_data)

    @staticmethod
    def _generate_json_content(plan_data: PlanData) -> str:
        """Generate JSON format content."""
        import json

        json_output = build_repro_json(
            title=safe_truncate_60(plan_data.title),
            assumptions=plan_data.assumptions or ["Standard development environment"],
            commands=plan_data.suggestions,
            needs=plan_data.needs or ["Standard development environment"],
            next_steps=plan_data.next_steps
            or [
                "Run the highest-score command",
                "If it fails: switch to the second",
                "Record brief logs in report.md",
            ],
        )
        return json.dumps(json_output, indent=2)

    @staticmethod
    def _generate_markdown_content(plan_data: PlanData) -> str:
        """Generate Markdown format content."""
        return build_repro_md(
            plan_data.title,
            plan_data.assumptions,
            plan_data.suggestions,
            plan_data.needs,
            plan_data.next_steps,
        )

    @staticmethod
    def _write_output(content: str, config: PlanConfig) -> int:
        """Write output content to destination."""
        content = ensure_trailing_newline(content)

        if config.print_to_stdout:
            print(content, end="")
            return 0

        try:
            out_path = Path(config.out).resolve()
            FileOperations.atomic_write(out_path, content)
            print(f"Wrote repro to {out_path}")
            return 0
        except OSError as e:
            log = logging.getLogger("autorepro")
            log.error(f"Error writing file {config.out}: {e}")
            return 1


class PlanService:
    """Main service for plan generation operations."""

    def __init__(self, config: PlanConfig):
        self.raw_config = config
        self.input_handler = PlanInputHandler()
        self.output_handler = PlanOutputHandler()

    def generate_plan(self) -> int:
        """Generate a complete reproduction plan."""
        try:
            # Prepare and validate configuration
            self.config = PlanConfigurationManager.prepare_config(self.raw_config)
            self.content_generator = PlanContentGenerator(self.config)

            # Read input
            text = self.input_handler.read_input_text(self.config)

            # Generate content
            plan_data = self._create_plan_data(text)

            # Output result
            return self.output_handler.output_plan(plan_data, self.config)

        except ValueError as e:
            if "min-score" in str(e):
                return 1  # Strict mode failure
            return 2  # Configuration error
        except OSError:
            return 1  # File I/O error

    def _create_plan_data(self, text: str) -> PlanData:
        """Create plan data from input text."""
        # Process text and generate suggestions
        keywords, lang_names, suggestions, filtered_count = (
            self.content_generator.generate_suggestions(text)
        )

        # Limit suggestions
        limited_suggestions = suggestions[: self.config.max_commands]

        # Generate plan components
        normalized_text = normalize(text)
        title = self._generate_plan_title(normalized_text)
        assumptions = self.content_generator.generate_assumptions(
            lang_names, keywords, filtered_count
        )
        needs = self.content_generator.generate_environment_needs(lang_names, keywords)
        next_steps = self._generate_next_steps()

        return PlanData(
            title=title,
            assumptions=assumptions,
            suggestions=limited_suggestions,
            needs=needs,
            next_steps=next_steps,
            normalized_text=normalized_text,
            keywords=keywords,
            lang_names=lang_names,
        )

    @staticmethod
    def _generate_plan_title(normalized_text: str) -> str:
        """Generate plan title from normalized text."""
        title_words = normalized_text.split()[:8]
        if title_words:
            return " ".join(title_words).title()
        return "Issue Reproduction Plan"

    @staticmethod
    def _generate_next_steps() -> list[str]:
        """Generate standard next steps for the plan."""
        return [
            "Run the suggested commands in order of priority",
            "Check logs and error messages for patterns",
            "Review environment setup if commands fail",
            "Document any additional reproduction steps found",
        ]
