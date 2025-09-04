"""
CLI validation utilities to eliminate duplicate argument validation patterns.

This module provides consistent CLI argument validation with clear error messages,
replacing duplicate patterns found across AutoRepro CLI commands.
"""

from pathlib import Path


class ArgumentValidator:
    """CLI argument validation with consistent error messages."""

    @staticmethod
    def validate_desc_file_exclusive(desc: str | None, file: str | None) -> str | None:
        """Validate mutually exclusive --desc/--file arguments.

        Args:
            desc: Description argument value
            file: File argument value

        Returns:
            Error message if validation fails, None if valid
        """
        if not desc and not file:
            return "Either --desc or --file must be specified"
        if desc and file:
            return "Cannot use both --desc and --file"
        return None

    @staticmethod
    def validate_output_path(out: str | Path | None) -> str | None:
        """Validate output path is not a directory.

        Args:
            out: Output path argument

        Returns:
            Error message if validation fails, None if valid
        """
        if out is None:
            return None

        try:
            out_path = Path(out)
            if out_path.exists() and out_path.is_dir():
                return f"Output path cannot be a directory: {out}"
        except (OSError, ValueError) as e:
            return f"Invalid output path '{out}': {e}"

        return None

    @staticmethod
    def validate_repo_path(repo: str | Path | None) -> str | None:
        """Validate repository path exists and is a directory.

        Args:
            repo: Repository path argument

        Returns:
            Error message if validation fails, None if valid
        """
        if repo is None:
            return None

        try:
            repo_path = Path(repo)
            if not repo_path.exists():
                return f"Repository path does not exist: {repo}"
            if not repo_path.is_dir():
                return f"Repository path is not a directory: {repo}"
        except (OSError, ValueError) as e:
            return f"Invalid repository path '{repo}': {e}"

        return None

    @staticmethod
    def validate_required_arg(value: str | None, arg_name: str) -> str | None:
        """Validate required argument is provided.

        Args:
            value: Argument value
            arg_name: Name of the argument for error message

        Returns:
            Error message if validation fails, None if valid
        """
        if value is None or value == "":
            return f"{arg_name} must be specified"
        return None

    @staticmethod
    def validate_file_exists(file_path: str | Path | None, arg_name: str = "File") -> str | None:
        """Validate file exists and is readable.

        Args:
            file_path: File path to validate
            arg_name: Name of the argument for error message

        Returns:
            Error message if validation fails, None if valid
        """
        if file_path is None:
            return None

        try:
            path = Path(file_path)
            if not path.exists():
                return f"{arg_name} does not exist: {file_path}"
            if not path.is_file():
                return f"{arg_name} is not a file: {file_path}"
            # Test readability
            try:
                path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                return f"Cannot read {arg_name.lower()}: {e}"

        except (OSError, ValueError) as e:
            return f"Invalid file path '{file_path}': {e}"

        return None


class ValidationError(Exception):
    """Raised when CLI argument validation fails."""

    def __init__(self, message: str, exit_code: int = 2):
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


def validate_and_exit(validator_result: str | None, exit_code: int = 2) -> None:
    """Check validator result and raise ValidationError if failed.

    Args:
        validator_result: Result from ArgumentValidator method
        exit_code: Exit code to use if validation fails

    Raises:
        ValidationError: If validator_result contains an error message
    """
    if validator_result is not None:
        raise ValidationError(validator_result, exit_code)


def validate_multiple(*validator_results: str | None, exit_code: int = 2) -> None:
    """Check multiple validator results and raise ValidationError if any failed.

    Args:
        validator_results: Results from multiple ArgumentValidator methods
        exit_code: Exit code to use if validation fails

    Raises:
        ValidationError: If any validator_result contains an error message
    """
    for result in validator_results:
        if result is not None:
            raise ValidationError(result, exit_code)
