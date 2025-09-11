#!/usr/bin/env python3
"""Common plan processing utilities for generating reproduction plans."""

from __future__ import annotations

import os
from pathlib import Path
from typing import NamedTuple

from ..detect import detect_languages
from ..planner import extract_keywords, normalize, suggest_commands


class PlanData(NamedTuple):
    """Data structure containing processed plan components."""

    title: str
    assumptions: list[str]
    suggestions: list[dict]
    needs: list[str]
    next_steps: list[str]
    text: str
    keywords: set[str]
    lang_names: list[str]


def _read_plan_input_content(desc_or_file: str | None, repo_path: Path) -> str:
    """Read input content from description or file."""
    if desc_or_file is None:
        return ""

    if Path(desc_or_file).exists():
        # It's a file
        try:
            with open(desc_or_file, encoding="utf-8") as f:
                return f.read()
        except OSError as e:
            # Try repo-relative path
            repo_file = repo_path / desc_or_file
            if repo_file.exists():
                with open(repo_file, encoding="utf-8") as f:
                    return f.read()
            else:
                raise OSError(f"Cannot read file {desc_or_file}") from e
    else:
        # It's a description
        return desc_or_file or ""


def _process_plan_keywords_and_languages(
    text: str, repo_path: Path
) -> tuple[set[str], list[str]]:
    """Process text to extract keywords and detect languages."""
    original_cwd = Path.cwd()
    try:
        os.chdir(repo_path)
        normalized_text = normalize(text)
        keywords = extract_keywords(normalized_text)
        detected_languages = detect_languages(".")
        lang_names = [lang for lang, _ in detected_languages]
        return keywords, lang_names
    finally:
        os.chdir(original_cwd)


def _generate_plan_command_suggestions(
    keywords: set[str], lang_names: list[str], min_score: int
) -> list:
    """Generate command suggestions from keywords and languages."""
    command_tuples = suggest_commands(keywords, lang_names, min_score)
    # Convert tuples to dictionaries to match PlanData type
    return [
        {"cmd": cmd, "score": score, "rationale": rationale}
        for cmd, score, rationale in command_tuples
    ]


def _build_plan_assumptions(lang_names: list[str], keywords: set[str]) -> list[str]:
    """Build assumptions based on detected languages and keywords."""
    assumptions = []

    if lang_names:
        lang_list = ", ".join(lang_names)
        assumptions.append(f"Project uses {lang_list} based on detected files")
    else:
        assumptions.append("Standard development environment")

    if "test" in keywords or "tests" in keywords or "testing" in keywords:
        assumptions.append("Issue is related to testing")
    if "ci" in keywords:
        assumptions.append("Issue occurs in CI/CD environment")
    if "install" in keywords or "setup" in keywords:
        assumptions.append("Installation or setup may be involved")

    if not assumptions or len(assumptions) == 1:
        assumptions.append("Issue can be reproduced locally")

    return assumptions


def _build_plan_environment_needs(
    lang_names: list[str], repo_path: Path, keywords: set[str]
) -> list[str]:
    """Build environment needs based on detected languages."""
    needs = []

    # Check for devcontainer
    devcontainer_dir = repo_path / ".devcontainer/devcontainer.json"
    devcontainer_root = repo_path / "devcontainer.json"
    if devcontainer_dir.exists() or devcontainer_root.exists():
        needs.append("devcontainer: present")

    for lang in lang_names:
        if lang == "python":
            needs.append("Python 3.7+")
            if "pytest" in keywords:
                needs.append("pytest package")
            if "tox" in keywords:
                needs.append("tox package")
        elif lang in ("node", "javascript"):
            needs.append("Node.js 16+")
            needs.append("npm or yarn")
        elif lang == "go":
            needs.append("Go 1.19+")

    if not needs:
        needs.append("Standard development environment")

    return needs


def _build_plan_title(normalized_text: str) -> str:
    """Build plan title from normalized text."""
    title_words = normalized_text.split()[:8]
    if title_words:
        return " ".join(title_words).title()
    return "Issue Reproduction Plan"


def process_plan_input(
    desc_or_file: str | None, repo_path: Path, min_score: int = 0
) -> PlanData:
    """
    Process plan input and generate common plan components.

    Args:
        desc_or_file: Description text or path to file containing description
        repo_path: Path to repository root
        min_score: Minimum score threshold for command suggestions

    Returns:
        PlanData containing processed plan components

    Raises:
        OSError: If specified file cannot be read
    """
    # Read input content
    text = _read_plan_input_content(desc_or_file, repo_path)
    normalized_text = normalize(text)

    # Process keywords and detect languages
    keywords, lang_names = _process_plan_keywords_and_languages(text, repo_path)

    # Generate suggestions
    suggestions = _generate_plan_command_suggestions(keywords, lang_names, min_score)

    # Build plan components
    title = _build_plan_title(normalized_text)
    assumptions = _build_plan_assumptions(lang_names, keywords)
    needs = _build_plan_environment_needs(lang_names, repo_path, keywords)

    # Generate next steps
    next_steps = [
        "Run the suggested commands in order of priority",
        "Check logs and error messages for patterns",
        "Review environment setup if commands fail",
        "Document any additional reproduction steps found",
    ]

    return PlanData(
        title=title,
        assumptions=assumptions,
        suggestions=suggestions,
        needs=needs,
        next_steps=next_steps,
        text=normalized_text,
        keywords=keywords,
        lang_names=lang_names,
    )
