"""Helper functions for common validation patterns and complex condition checking."""

from typing import Any


def has_any_keyword_variant(keywords: set[str], variants: list[str]) -> bool:
    """Check if any keyword variant exists in the keywords set.

    Args:
        keywords: Set of keywords to check
        variants: List of keyword variants to look for

    Returns:
        True if any variant is found in keywords

    Example:
        >>> keywords = {"pytest", "unit", "ci"}
        >>> has_any_keyword_variant(keywords, ["test", "tests", "testing"])
        False
        >>> has_any_keyword_variant(keywords, ["pytest", "unittest"])
        True
    """
    return any(variant in keywords for variant in variants)


def has_test_keywords(keywords: set[str]) -> bool:
    """Check if keywords contain test-related terms."""
    TEST_KEYWORDS = ["test", "tests", "testing"]
    return has_any_keyword_variant(keywords, TEST_KEYWORDS)


def has_installation_keywords(keywords: set[str]) -> bool:
    """Check if keywords contain installation-related terms."""
    INSTALL_KEYWORDS = ["install", "setup"]
    return has_any_keyword_variant(keywords, INSTALL_KEYWORDS)


def has_ci_keywords(keywords: set[str]) -> bool:
    """Check if keywords contain CI-related terms."""
    CI_KEYWORDS = ["ci"]
    return has_any_keyword_variant(keywords, CI_KEYWORDS)


def determine_rule_source(ecosystem: str, rule: Any, builtin_rules: dict) -> str:
    """Determine if a rule is from builtin or plugin source.

    Args:
        ecosystem: The ecosystem name
        rule: The rule object to check
        builtin_rules: Dictionary of builtin rules by ecosystem

    Returns:
        "builtin" if rule is from builtin rules, "plugin" otherwise
    """
    is_builtin = ecosystem in builtin_rules and rule in builtin_rules[ecosystem]
    return "builtin" if is_builtin else "plugin"


def should_apply_repo_relative_path(repo_path: Any, out_path: str, print_to_stdout: bool) -> bool:
    """Determine if output path should be made relative to repository path.

    Args:
        repo_path: Repository path (may be None)
        out_path: Output path string
        print_to_stdout: Whether output goes to stdout

    Returns:
        True if path should be made repo-relative
    """
    from pathlib import Path

    has_repo_path = repo_path is not None
    is_relative_path = not Path(out_path).is_absolute()

    return has_repo_path and is_relative_path and not print_to_stdout


def needs_pr_update_operation(pr_config: Any) -> bool:
    """Check if any PR update operation is requested.

    Args:
        pr_config: PR configuration object with boolean flags

    Returns:
        True if any update operation is requested
    """
    return (
        pr_config.update_if_exists
        or pr_config.comment
        or pr_config.update_pr_body
        or pr_config.add_labels
        or pr_config.link_issue
    )


def is_safe_to_write_file(print_to_stdout: bool, output_path: str, force_overwrite: bool) -> bool:
    """Check if it's safe to write to the output file.

    Args:
        print_to_stdout: Whether output goes to stdout
        output_path: Path to output file
        force_overwrite: Whether to force overwrite existing files

    Returns:
        True if safe to write, False if file exists and force not specified
    """
    import os

    if print_to_stdout:
        return True

    if not output_path:
        return True

    if os.path.isdir(output_path):
        return False  # Cannot write to directory

    if os.path.exists(output_path) and not force_overwrite:
        return False  # File exists and no force flag

    return True
