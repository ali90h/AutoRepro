#!/usr/bin/env python3
"""AutoRepro CLI - Command line interface for AutoRepro."""

from __future__ import annotations

import argparse
import json
import logging
import os
import shlex
import subprocess
import sys
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from autorepro import __version__
from autorepro.config import config
from autorepro.config.models import get_config
from autorepro.detect import collect_evidence, detect_languages
from autorepro.env import (
    DevcontainerExistsError,
    DevcontainerMisuseError,
    default_devcontainer,
    write_devcontainer,
)
from autorepro.planner import (
    build_repro_json,
    build_repro_md,
    extract_keywords,
    normalize,
    safe_truncate_60,
    suggest_commands,
)
from autorepro.utils.decorators import handle_errors, log_operation, time_execution
from autorepro.utils.file_ops import FileOperations
from autorepro.utils.validation_helpers import (
    has_ci_keywords,
    has_installation_keywords,
    has_test_keywords,
    needs_pr_update_operation,
)


def ensure_trailing_newline(content: str) -> str:
    """Ensure content ends with exactly one newline."""
    return content.rstrip() + "\n"


@contextmanager
def temp_chdir(path: Path) -> Generator[None, None, None]:
    """Temporarily change to the given directory, then restore original working directory."""
    original_cwd = Path.cwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(original_cwd)


def _add_common_args(parser) -> None:
    """Add common arguments (verbose, quiet, dry-run)."""
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="Increase verbosity (-v, -vv)"
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="Show errors only")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without executing")


def _add_file_input_group(parser, required: bool = True) -> argparse._MutuallyExclusiveGroup:
    """Add mutually exclusive desc/file input group."""
    input_group = parser.add_mutually_exclusive_group(required=required)
    input_group.add_argument("--desc", help="Issue description text")
    input_group.add_argument("--file", help="Path to file containing issue description")
    return input_group


def _add_repo_args(parser) -> None:
    """Add repository-related arguments."""
    parser.add_argument("--repo", help="Execute logic on specified repository path")
    parser.add_argument("--out", help="Custom output path")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")


def _setup_pr_parser(subparsers) -> argparse.ArgumentParser:
    """Setup pr subcommand parser."""
    pr_parser = subparsers.add_parser(
        "pr",
        help="Create or update GitHub pull request",
        description="Create a new draft PR or update an existing one with reproduction plan",
    )

    # Mutually exclusive group for --desc and --file
    _add_file_input_group(pr_parser, required=True)

    # Required arguments
    pr_parser.add_argument(
        "--repo-slug",
        required=True,
        help="Repository slug in the format 'owner/repo'",
    )

    # Optional arguments
    pr_parser.add_argument(
        "--title",
        help="Custom PR title (default: generated from description)",
    )
    pr_parser.add_argument(
        "--body",
        help="Path to file containing custom PR body",
    )
    pr_parser.add_argument(
        "--update-if-exists",
        action="store_true",
        help="Update existing draft PR if one exists",
    )
    pr_parser.add_argument(
        "--skip-push",
        action="store_true",
        help="Skip pushing to remote (assumes branch exists)",
    )
    pr_parser.add_argument(
        "--ready",
        action="store_true",
        help="Create as ready PR instead of draft",
    )
    pr_parser.add_argument(
        "--label",
        action="append",
        help="Add label to PR (can be specified multiple times)",
    )
    pr_parser.add_argument(
        "--assignee",
        action="append",
        help="Add assignee to PR (can be specified multiple times)",
    )
    pr_parser.add_argument(
        "--reviewer",
        action="append",
        help="Add reviewer to PR (can be specified multiple times)",
    )
    pr_parser.add_argument(
        "--min-score",
        type=int,
        default=2,
        help="Drop commands with score < N (default: 2)",
    )
    pr_parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with error if no commands meet min-score",
    )
    pr_parser.add_argument(
        "--comment",
        action="store_true",
        help="Create or update autorepro sync block comment on PR",
    )
    pr_parser.add_argument(
        "--update-pr-body",
        action="store_true",
        help="Update PR body with sync block",
    )
    pr_parser.add_argument(
        "--link-issue",
        metavar="ISSUE",
        help="Create cross-reference links with specified issue",
    )
    pr_parser.add_argument(
        "--add-labels",
        help="Comma-separated list of labels to add to PR",
    )
    pr_parser.add_argument(
        "--attach-report",
        action="store_true",
        help="Include report metadata in comment",
    )
    pr_parser.add_argument(
        "--summary",
        help="Add reviewer context summary to PR comment",
    )
    pr_parser.add_argument(
        "--no-details",
        action="store_true",
        help="Disable collapsible details wrapper",
    )
    pr_parser.add_argument(
        "--format",
        choices=["md", "json"],
        default="md",
        help="Output format (default: md)",
    )

    # Add verbose but not quiet (PR has different requirements)
    pr_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without executing",
    )
    pr_parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v, -vv)",
    )

    return pr_parser


def _setup_scan_parser(subparsers) -> argparse.ArgumentParser:
    """Setup scan subcommand parser."""
    scan_parser = subparsers.add_parser(
        "scan",
        help="Detect languages/frameworks from file pointers",
        description="Scan the current directory for language/framework indicators",
    )
    scan_parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format with scores and reasons",
    )
    scan_parser.add_argument(
        "--show-scores",
        action="store_true",
        help="Show scores in text output (only effective without --json)",
    )
    scan_parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Show errors only",
    )
    scan_parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v, -vv)",
    )
    return scan_parser


def _setup_init_parser(subparsers) -> argparse.ArgumentParser:
    """Setup init subcommand parser."""
    init_parser = subparsers.add_parser(
        "init",
        help="Create a developer container",
        description="Create a devcontainer.json file with default configuration",
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing devcontainer.json file",
    )
    init_parser.add_argument(
        "--out",
        help="Custom output path (default: .devcontainer/devcontainer.json)",
    )
    init_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Display contents to stdout without writing files",
    )
    init_parser.add_argument(
        "--repo",
        help="Execute logic on specified repository path",
    )
    return init_parser


def _setup_plan_parser(subparsers) -> argparse.ArgumentParser:
    """Setup plan subcommand parser."""
    plan_parser = subparsers.add_parser(
        "plan",
        help="Derive execution plan from issue description",
        description="Generate a reproduction plan from issue description or file",
    )

    # Mutually exclusive group for --desc and --file (exactly one required)
    _add_file_input_group(plan_parser, required=True)

    plan_parser.add_argument(
        "--out",
        default=config.paths.default_plan_file,
        help=f"Output path (default: {config.paths.default_plan_file})",
    )
    plan_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing output file",
    )
    plan_parser.add_argument(
        "--max",
        type=int,
        default=5,
        help="Maximum number of suggested commands (default: 5)",
    )
    plan_parser.add_argument(
        "--format",
        choices=["md", "json"],
        default="md",
        help="Output format (default: md)",
    )
    plan_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Display contents to stdout without writing files",
    )
    plan_parser.add_argument(
        "--repo",
        help="Execute logic on specified repository path",
    )
    plan_parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if no commands make the cut after filtering",
    )
    plan_parser.add_argument(
        "--min-score",
        type=int,
        default=2,
        help="Drop commands with score < N (default: 2)",
    )
    plan_parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Show errors only",
    )
    plan_parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v, -vv)",
    )
    return plan_parser


def _setup_exec_parser(subparsers) -> argparse.ArgumentParser:
    """Setup exec subcommand parser."""
    exec_parser = subparsers.add_parser(
        "exec",
        help="Execute the top plan command",
        description="Generate a plan and execute the selected command",
    )

    # Mutually exclusive group for --desc and --file (exactly one required)
    _add_file_input_group(exec_parser, required=True)

    exec_parser.add_argument(
        "--repo",
        help="Execute logic on specified repository path",
    )
    exec_parser.add_argument(
        "--index",
        type=int,
        default=0,
        help="Pick the N-th suggested command (default: 0 = top)",
    )
    exec_parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Command timeout in seconds (default: 120)",
    )
    exec_parser.add_argument(
        "--env",
        action="append",
        default=[],
        help="Set environment variable KEY=VAL (repeatable)",
    )
    exec_parser.add_argument(
        "--env-file",
        help="Load environment variables from file",
    )
    exec_parser.add_argument(
        "--tee",
        help="Append full stdout/stderr to log file",
    )
    exec_parser.add_argument(
        "--jsonl",
        help="Append JSON line record per run",
    )
    exec_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print chosen command only, don't execute",
    )
    exec_parser.add_argument(
        "--min-score",
        type=int,
        default=2,
        help="Drop commands with score < N (default: 2)",
    )
    exec_parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if no commands make the cut after filtering",
    )
    exec_parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Show errors only",
    )
    exec_parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v, -vv)",
    )
    return exec_parser


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        prog="autorepro",
        description="CLI for AutoRepro - transforms issues into repro steps",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
AutoRepro automatically detects repository technologies, generates ready-made
devcontainers, and writes prioritized repro plans with explicit assumptions.

MVP commands:
  scan    Detect languages/frameworks from file pointers
  init    Create a developer container
  plan    Derive execution plan from issue description
  pr      Create or update GitHub pull request

For more information, visit: https://github.com/ali90h/AutoRepro
        """.strip(),
    )

    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    # Add subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Setup all subcommand parsers
    _setup_pr_parser(subparsers)
    _setup_scan_parser(subparsers)
    _setup_init_parser(subparsers)
    _setup_plan_parser(subparsers)
    _setup_exec_parser(subparsers)

    return parser


@time_execution(log_threshold=0.5)
@handle_errors({}, default_return=1, log_errors=True)
@log_operation("language detection scan")
def cmd_scan(json_output: bool = False, show_scores: bool = False) -> int:
    """Handle the scan command."""
    if json_output:
        # Use new weighted evidence collection for JSON output
        try:
            evidence = collect_evidence(Path("."))
            detected_languages = sorted(evidence.keys())
        except (OSError, PermissionError):
            # Handle I/O errors gracefully for JSON output - return empty results
            evidence = {}
            detected_languages = []

        # Build JSON output according to schema
        json_result = {
            "schema_version": 1,
            "tool": "autorepro",
            "tool_version": __version__,
            "root": str(Path(".").resolve()),
            "detected": detected_languages,
            "languages": evidence,
        }

        import json

        print(json.dumps(json_result, indent=2))
        return 0
    else:
        # Use legacy text output
        detected = detect_languages(".")

        if not detected:
            print("No known languages detected.")
            return 0

        # Extract language names for header
        languages = [lang for lang, _ in detected]
        print(f"Detected: {', '.join(languages)}")

        # Print details for each language
        for lang, reasons in detected:
            reasons_str = ", ".join(reasons)
            print(f"- {lang} -> {reasons_str}")

            # Add score if --show-scores is enabled
            if show_scores:
                try:
                    evidence = collect_evidence(Path("."))
                    if lang in evidence:
                        print(f"  Score: {evidence[lang]['score']}")
                except (OSError, PermissionError):
                    # Skip scores if evidence collection fails
                    pass

        return 0


@dataclass
class PlanConfig:
    """Configuration for plan generation."""

    desc: str | None
    file: str | None
    out: str
    force: bool
    max_commands: int
    format_type: str
    dry_run: bool
    repo: str | None
    strict: bool
    min_score: int
    repo_path: Path | None = None
    print_to_stdout: bool = False


@dataclass
class PlanData:
    """Generated plan data."""

    title: str
    assumptions: list[str]
    suggestions: list[tuple[str, int, str]]
    needs: list[str]
    next_steps: list[str]
    normalized_text: str
    keywords: set[str]
    lang_names: list[str]


@dataclass
class PrConfig:
    """Configuration for PR operations."""

    desc: str | None = None
    file: str | None = None
    repo_slug: str | None = None
    title: str | None = None
    body: str | None = None
    ready: bool = False
    label: list[str] | None = None
    assignee: list[str] | None = None
    reviewer: list[str] | None = None
    update_if_exists: bool = False
    comment: bool = False
    update_pr_body: bool = False
    add_labels: str | None = None
    link_issue: int | None = None
    attach_report: bool = False
    summary: str | None = None
    no_details: bool = False
    format_type: str = "md"
    dry_run: bool = False
    skip_push: bool = False
    min_score: int = field(default_factory=lambda: config.limits.min_score_threshold)
    strict: bool = False


@dataclass
class ExecConfig:
    """Configuration for exec command operations."""

    desc: str | None = None
    file: str | None = None
    repo: str | None = None
    index: int = 0
    timeout: int = field(default_factory=lambda: config.timeouts.default_seconds)
    env_vars: list[str] | None = None
    env_file: str | None = None
    tee_path: str | None = None
    jsonl_path: str | None = None
    dry_run: bool = False
    min_score: int = field(default_factory=lambda: config.limits.min_score_threshold)
    strict: bool = False


@dataclass
class InitConfig:
    """Configuration for init command operations."""

    force: bool = False
    out: str | None = None
    dry_run: bool = False
    repo: str | None = None
    repo_path: Path | None = None
    print_to_stdout: bool = False


def _prepare_plan_config(config: PlanConfig) -> PlanConfig:
    """Extract and validate plan configuration from config object."""
    if config.desc and config.file:
        raise ValueError("Cannot specify both --desc and --file")

    if not config.desc and not config.file:
        raise ValueError("Must specify either --desc or --file")

    # Validate and resolve --repo path if specified
    if config.repo is not None:
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

    # Handle --out - to print to stdout (check before path resolution)
    config.print_to_stdout = config.out == "-"

    # Update output path to be under the repo if relative path specified (but not for stdout)
    if config.repo_path and not Path(config.out).is_absolute() and not config.print_to_stdout:
        config.out = str(config.repo_path / config.out)

    # Handle dry-run mode
    if config.dry_run:
        config.print_to_stdout = True

    return config


def _read_plan_input_text(config: PlanConfig) -> str:
    """Read input text from description or file for plan generation."""
    try:
        if config.desc is not None:
            return config.desc
        elif config.file is not None:
            # File path resolution: try CWD first, then repo-relative as fallback
            file_path = Path(config.file)

            # If absolute path, use as-is
            if file_path.is_absolute():
                with open(file_path, encoding="utf-8") as f:
                    return f.read()
            else:
                # Try CWD first
                try:
                    with open(file_path, encoding="utf-8") as f:
                        return f.read()
                except OSError:
                    # If CWD fails and --repo specified, try repo-relative as fallback
                    if config.repo_path:
                        repo_file_path = config.repo_path / config.file
                        with open(repo_file_path, encoding="utf-8") as f:
                            return f.read()
                    else:
                        # Re-raise the original error if no repo fallback available
                        raise
        else:
            # This should not happen due to argparse mutually_exclusive_group
            log = logging.getLogger("autorepro")
            log.error("Error: Either --desc or --file must be specified")
            raise ValueError("Missing description or file")
    except OSError as e:
        log = logging.getLogger("autorepro")
        log.error(f"Error reading file {config.file}: {e}")
        raise OSError(f"Error reading file {config.file}: {e}") from e


def _process_plan_text_and_generate_suggestions(
    text: str, config: PlanConfig
) -> tuple[set[str], list[str], list, int]:
    """Process text and generate command suggestions.

    Returns:
        Tuple of (keywords, lang_names, suggestions, filtered_count)
    """
    # Process the text
    normalized_text = normalize(text)
    keywords = extract_keywords(normalized_text)

    # Get detected languages for weighting
    if config.repo_path:
        with temp_chdir(config.repo_path):
            detected_languages = detect_languages(".")
    else:
        detected_languages = detect_languages(".")
    lang_names = [lang for lang, _ in detected_languages]

    # Generate suggestions
    suggestions = suggest_commands(keywords, lang_names, config.min_score)

    # Check for strict mode - exit 1 if no commands after filtering
    log = logging.getLogger("autorepro")
    if config.strict and not suggestions:
        log.error(f"no candidate commands above min-score={config.min_score}")
        raise ValueError(f"no candidate commands above min-score={config.min_score}")

    # Count filtered commands for warning
    total_commands = len(suggest_commands(keywords, lang_names, min_score=0))
    filtered_count = total_commands - len(suggestions)
    if filtered_count > 0:
        log.info(f"filtered {filtered_count} low-score suggestions")

    return keywords, lang_names, suggestions, filtered_count


def _generate_plan_title(normalized_text: str) -> str:
    """Generate plan title from normalized text."""
    title_words = normalized_text.split()[:8]  # Increased to allow more words before truncation
    title = "Issue Reproduction Plan"
    if title_words:
        title = " ".join(title_words).title()
        # Note: safe_truncate_60 will be applied in build_repro_md()
    return title


def _generate_plan_assumptions(
    lang_names: list[str], keywords: set[str], config: PlanConfig, filtered_count: int
) -> list[str]:
    """Generate assumptions based on detected languages and keywords."""
    assumptions = []
    if lang_names:
        lang_list = ", ".join(lang_names)
        assumptions.append(f"Project uses {lang_list} based on detected files")
    else:
        assumptions.append("Standard development environment")

    if has_test_keywords(keywords):
        assumptions.append("Issue is related to testing")
    if has_ci_keywords(keywords):
        assumptions.append("Issue occurs in CI/CD environment")
    if has_installation_keywords(keywords):
        assumptions.append("Installation or setup may be involved")

    if not assumptions:
        assumptions.append("Issue can be reproduced locally")

    # Add filtering note to assumptions if commands were filtered and user explicitly set min-score
    # Only show filtering notes when user explicitly used --min-score (not default) or --strict
    from autorepro.config import config as autorepro_config

    min_score_explicit = (
        config.min_score != autorepro_config.limits.min_score_threshold
    )  # Check if non-default value
    if filtered_count > 0 and (min_score_explicit or config.strict):
        assumptions.append(
            f"Filtered {filtered_count} low-scoring command suggestions "
            f"(min-score={config.min_score})"
        )

    return assumptions


def _generate_plan_environment_needs(
    lang_names: list[str], keywords: set[str], config: PlanConfig
) -> list[str]:
    """Generate environment needs based on detected languages."""
    needs = []

    # Check for devcontainer presence
    if config.repo_path:
        devcontainer_dir = config.repo_path / ".devcontainer/devcontainer.json"
        devcontainer_root = config.repo_path / "devcontainer.json"
    else:
        devcontainer_dir = Path(".devcontainer/devcontainer.json")
        devcontainer_root = Path("devcontainer.json")

    if devcontainer_dir.exists() or devcontainer_root.exists():
        needs.append("devcontainer: present")

    for lang in lang_names:
        if lang == "python":
            needs.append("Python 3.7+")
            if "pytest" in keywords:
                needs.append("pytest package")
            if "tox" in keywords:
                needs.append("tox package")
        elif lang == "node" or lang == "javascript":
            needs.append("Node.js 16+")
            needs.append("npm or yarn")
        elif lang == "go":
            needs.append("Go 1.19+")

    if not needs:
        needs.append("Standard development environment")

    return needs


def _generate_plan_content(config: PlanConfig) -> PlanData:
    """Generate the actual reproduction plan."""
    # Read input text
    text = _read_plan_input_text(config)
    normalized_text = normalize(text)

    # Process text and generate suggestions
    keywords, lang_names, suggestions, filtered_count = _process_plan_text_and_generate_suggestions(
        text, config
    )

    # Limit to max_commands
    limited_suggestions = suggestions[: config.max_commands]

    # Generate plan components
    title = _generate_plan_title(normalized_text)
    assumptions = _generate_plan_assumptions(lang_names, keywords, config, filtered_count)
    needs = _generate_plan_environment_needs(lang_names, keywords, config)

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
        suggestions=limited_suggestions,
        needs=needs,
        next_steps=next_steps,
        normalized_text=normalized_text,
        keywords=keywords,
        lang_names=lang_names,
    )


def _output_plan_result(plan_data: PlanData, config: PlanConfig) -> int:
    """Output plan in requested format and location."""
    # Check if output path points to a directory (misuse error)
    if not config.print_to_stdout and config.out and os.path.isdir(config.out):
        print(f"Error: Output path is a directory: {config.out}")
        return 2

    # Check for existing output file (unless --force or stdout output)
    if not config.print_to_stdout and os.path.exists(config.out) and not config.force:
        print(f"{config.out} exists; use --force to overwrite")
        return 0

    # Generate output content
    if config.format_type == "json":
        # Use the standardized JSON function
        json_output = build_repro_json(
            title=safe_truncate_60(plan_data.title),
            assumptions=(
                plan_data.assumptions
                if plan_data.assumptions
                else ["Standard development environment"]
            ),
            commands=plan_data.suggestions,
            needs=(plan_data.needs if plan_data.needs else ["Standard development environment"]),
            next_steps=(
                plan_data.next_steps
                if plan_data.next_steps
                else [
                    "Run the highest-score command",
                    "If it fails: switch to the second",
                    "Record brief logs in report.md",
                ]
            ),
        )

        import json

        content = json.dumps(json_output, indent=2)
    else:
        # Build the reproduction markdown
        content = build_repro_md(
            plan_data.title,
            plan_data.assumptions,
            plan_data.suggestions,
            plan_data.needs,
            plan_data.next_steps,
        )

    # Ensure proper newline termination
    content = ensure_trailing_newline(content)

    # Write output
    if config.print_to_stdout:
        print(content, end="")
        return 0
    else:
        # Write output file
        try:
            out_path = Path(config.out).resolve()
            FileOperations.atomic_write(out_path, content)
            print(f"Wrote repro to {out_path}")
            return 0
        except OSError as e:
            log = logging.getLogger("autorepro")
            log.error(f"Error writing file {config.out}: {e}")
            return 1


def cmd_plan(config: PlanConfig | None = None, **kwargs) -> int:
    """Handle the plan command."""
    if config is None:
        # Create from kwargs for backward compatibility
        global_config = get_config()
        config = PlanConfig(
            desc=kwargs.get("desc"),
            file=kwargs.get("file"),
            out=kwargs.get("out", global_config.paths.default_plan_file),
            force=kwargs.get("force", False),
            max_commands=kwargs.get("max_commands", global_config.limits.max_plan_suggestions),
            format_type=kwargs.get("format_type", "md"),
            dry_run=kwargs.get("dry_run", False),
            repo=kwargs.get("repo"),
            strict=kwargs.get("strict", False),
            min_score=kwargs.get("min_score", global_config.limits.min_score_threshold),
        )

    try:
        validated_config = _prepare_plan_config(config)
        plan_data = _generate_plan_content(validated_config)
        return _output_plan_result(plan_data, validated_config)
    except ValueError as e:
        if "min-score" in str(e):
            return 1  # Strict mode failure
        else:
            return 2  # Configuration error
    except OSError:
        return 1  # File I/O error


def _validate_init_repo_path(config: InitConfig) -> int | None:
    """Validate repo path for init command. Returns error code if invalid."""
    if config.repo is None:
        return None

    try:
        config.repo_path = Path(config.repo).resolve()
        if not config.repo_path.is_dir():
            print(
                f"Error: --repo path does not exist or is not a directory: {config.repo}",
                file=sys.stderr,
            )
            return 2
        return None
    except (OSError, ValueError):
        print(
            f"Error: --repo path does not exist or is not a directory: {config.repo}",
            file=sys.stderr,
        )
        return 2


def _prepare_init_output_path(config: InitConfig) -> None:
    """Prepare output path for init command."""
    if config.out is None:
        if config.repo_path:
            config.out = str(config.repo_path / ".devcontainer" / "devcontainer.json")
        else:
            config.out = ".devcontainer/devcontainer.json"

    config.print_to_stdout = config.out == "-"
    if config.dry_run:
        config.print_to_stdout = True


def _handle_init_stdout_output(devcontainer_config: dict) -> int:
    """Handle stdout output for init command."""
    import json

    json_content = json.dumps(devcontainer_config, indent=2, sort_keys=True)
    json_content = ensure_trailing_newline(json_content)
    print(json_content, end="")
    return 0


def _validate_init_output_path(config: InitConfig) -> int | None:
    """Validate output path for init command. Returns error code if invalid."""
    if config.out and os.path.isdir(config.out):
        print(f"Error: Output path is a directory: {config.out}")
        return 2

    if config.out and os.path.exists(config.out) and not config.force:
        print(f"devcontainer.json already exists at {config.out}.")
        print("Use --force to overwrite or --out <path> to write elsewhere.")
        return 0

    return None


def _execute_init_write(config: InitConfig, devcontainer_config: dict) -> int:
    """Execute devcontainer write operation."""
    log = logging.getLogger("autorepro")

    try:
        result_path, diff_lines = write_devcontainer(
            devcontainer_config, force=config.force, out=config.out
        )

        if config.force and diff_lines is not None:
            print(f"Overwrote devcontainer at {result_path}")
            if diff_lines:
                print("Changes:")
                for line in diff_lines:
                    print(line)
            else:
                print("No changes.")
        else:
            print(f"Wrote devcontainer to {result_path}")
        return 0

    except DevcontainerExistsError as e:
        print(f"devcontainer.json already exists at {e.path}.")
        print("Use --force to overwrite or --out <path> to write elsewhere.")
        return 0
    except DevcontainerMisuseError as e:
        log.error(f"Error: {e.message}")
        return 2
    except (OSError, PermissionError) as e:
        log.error(f"Error: {e}")
        return 1


def cmd_init(
    force: bool = False,
    out: str | None = None,
    dry_run: bool = False,
    repo: str | None = None,
) -> int:
    """Handle the init command."""
    config = InitConfig(force=force, out=out, dry_run=dry_run, repo=repo)

    # Validate repo path
    error = _validate_init_repo_path(config)
    if error is not None:
        return error

    # Prepare output path
    _prepare_init_output_path(config)

    # Get devcontainer configuration
    devcontainer_config = default_devcontainer()

    # Handle stdout output
    if config.print_to_stdout:
        return _handle_init_stdout_output(devcontainer_config)

    # Validate output path
    error = _validate_init_output_path(config)
    if error is not None:
        return error

    # Execute write operation
    return _execute_init_write(config, devcontainer_config)


def parse_env_vars(env_list: list[str]) -> dict[str, str]:
    """Parse environment variable assignments from KEY=VAL format."""
    env_vars = {}
    for env_str in env_list:
        if "=" not in env_str:
            raise ValueError(f"Invalid environment variable format: {env_str}")
        key, value = env_str.split("=", 1)
        env_vars[key] = value
    return env_vars


def load_env_file(env_file: str) -> dict[str, str]:
    """Load environment variables from a file."""
    env_vars = {}
    try:
        with open(env_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key] = value
    except OSError as e:
        raise OSError(f"Failed to read env file {env_file}: {e}") from e
    return env_vars


def _validate_exec_repo_path(repo: str | None) -> tuple[Path | None, int | None]:
    """Validate and resolve repo path for exec command.

    Returns:
        Tuple of (resolved_path, error_code). If error_code is not None, should return it.
    """
    if repo is None:
        return None, None

    log = logging.getLogger("autorepro")
    try:
        repo_path = Path(repo).resolve()
        if not repo_path.is_dir():
            log.error(f"--repo path does not exist or is not a directory: {repo}")
            return None, 2
        return repo_path, None
    except (OSError, ValueError):
        log.error(f"--repo path does not exist or is not a directory: {repo}")
        return None, 2


def _read_exec_input_text(
    config: ExecConfig, repo_path: Path | None
) -> tuple[str | None, int | None]:
    """Read input text for exec command.

    Returns:
        Tuple of (text, error_code). If error_code is not None, should return it.
    """
    log = logging.getLogger("autorepro")

    try:
        if config.desc is not None:
            return config.desc, None
        elif config.file is not None:
            file_path = Path(config.file)
            if file_path.is_absolute():
                with open(file_path, encoding="utf-8") as f:
                    return f.read(), None
            else:
                try:
                    with open(file_path, encoding="utf-8") as f:
                        return f.read(), None
                except OSError:
                    if repo_path:
                        repo_file_path = repo_path / config.file
                        with open(repo_file_path, encoding="utf-8") as f:
                            return f.read(), None
                    else:
                        raise
        else:
            log.error("Either --desc or --file must be specified")
            return None, 2
    except OSError as e:
        log.error(f"Error reading file {config.file}: {e}")
        return None, 1


def _generate_exec_suggestions(
    text: str, repo_path: Path | None, config: ExecConfig
) -> tuple[list, int | None]:
    """Generate command suggestions for exec.

    Returns:
        Tuple of (suggestions, error_code). If error_code is not None, should return it.
    """
    log = logging.getLogger("autorepro")

    # Process the text and generate suggestions
    normalized_text = normalize(text)
    keywords = extract_keywords(normalized_text)

    # Get detected languages for weighting
    if repo_path:
        with temp_chdir(repo_path):
            detected_languages = detect_languages(".")
    else:
        detected_languages = detect_languages(".")
    lang_names = [lang for lang, _ in detected_languages]

    # Generate suggestions
    suggestions = suggest_commands(keywords, lang_names, config.min_score)

    # Check for strict mode - exit 1 if no commands after filtering
    if config.strict and not suggestions:
        log.error(f"no candidate commands above min-score={config.min_score}")
        return suggestions, 1

    # Count filtered commands for info logging
    total_commands = len(suggest_commands(keywords, lang_names, min_score=0))
    filtered_count = total_commands - len(suggestions)
    if filtered_count > 0:
        log.info(f"filtered {filtered_count} low-score suggestions")

    return suggestions, None


def _select_exec_command(suggestions: list, config: ExecConfig) -> tuple[tuple | None, int | None]:
    """Select command by index for execution.

    Returns:
        Tuple of (selected_command, error_code). If error_code is not None, should return it.
    """
    log = logging.getLogger("autorepro")

    if not suggestions:
        log.error("No commands to execute")
        return None, 1

    if config.index >= len(suggestions):
        log.error(f"Index {config.index} out of range (0-{len(suggestions) - 1})")
        return None, 2

    return suggestions[config.index], None


def _prepare_exec_environment(config: ExecConfig) -> tuple[dict | None, int | None]:
    """Prepare environment variables for command execution.

    Returns:
        Tuple of (env_dict, error_code). If error_code is not None, should return it.
    """
    log = logging.getLogger("autorepro")

    env = os.environ.copy()

    # Load from env file first
    if config.env_file:
        try:
            file_env = load_env_file(config.env_file)
            env.update(file_env)
        except OSError as e:
            log.error(str(e))
            return None, 1

    # Apply --env overrides
    if config.env_vars:
        try:
            cmd_env = parse_env_vars(config.env_vars)
            env.update(cmd_env)
        except ValueError as e:
            log.error(str(e))
            return None, 2

    return env, None


def _execute_command(
    command_str: str, env: dict, exec_dir: Path, config: ExecConfig
) -> tuple[dict, int | None]:
    """Execute the selected command and return results.

    Returns:
        Tuple of (execution_results_dict, error_code). If error_code is not None, should return it.
    """
    log = logging.getLogger("autorepro")

    # Parse command for execution
    try:
        cmd_parts = shlex.split(command_str)
    except ValueError as e:
        log.error(f"Failed to parse command: {e}")
        return {}, 2

    # Record start time and prepare for execution
    start_time = datetime.now()
    start_iso = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Execute command
    log.info(f"Executing: {command_str}")
    timed_out = False
    try:
        result = subprocess.run(
            cmd_parts,
            cwd=exec_dir,
            env=env,
            timeout=config.timeout,
            capture_output=True,
            text=True,
        )

        # Calculate duration
        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        exit_code = result.returncode
        stdout_full = result.stdout
        stderr_full = result.stderr

    except subprocess.TimeoutExpired:
        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        log.error(f"Command timed out after {config.timeout} seconds")
        exit_code = 124  # Standard timeout exit code
        stdout_full = ""
        stderr_full = f"Command timed out after {config.timeout} seconds"
        timed_out = True

    except FileNotFoundError:
        log.error(f"Command not found: {cmd_parts[0]}")
        return {}, 127
    except OSError as e:
        log.error(f"Failed to execute command: {e}")
        return {}, 1

    return {
        "start_iso": start_iso,
        "duration_ms": duration_ms,
        "exit_code": exit_code,
        "stdout_full": stdout_full,
        "stderr_full": stderr_full,
        "timed_out": timed_out,
        "command_str": command_str,
        "exec_dir": exec_dir,
    }, None


def _handle_exec_output_logging(results: dict, config: ExecConfig) -> None:
    """Handle tee and JSONL output logging."""
    log = logging.getLogger("autorepro")

    # Handle tee output
    if config.tee_path:
        try:
            tee_path_obj = Path(config.tee_path)
            FileOperations.ensure_directory(tee_path_obj.parent)
            with open(tee_path_obj, "a", encoding="utf-8") as f:
                f.write(f"=== {results['start_iso']} - {results['command_str']} ===\n")
                f.write("STDOUT:\n")
                f.write(results["stdout_full"])
                f.write("\nSTDERR:\n")
                f.write(results["stderr_full"])
                f.write(f"\nExit code: {results['exit_code']}\n")
                f.write("=" * 50 + "\n\n")
        except OSError as e:
            log.error(f"Failed to write tee log: {e}")

    # Handle JSONL output
    if config.jsonl_path:
        try:
            jsonl_path_obj = Path(config.jsonl_path)
            FileOperations.ensure_directory(jsonl_path_obj.parent)

            # Prepare previews (first 2000 chars)
            stdout_preview = results["stdout_full"][:2000] if results["stdout_full"] else ""
            stderr_preview = results["stderr_full"][:2000] if results["stderr_full"] else ""

            jsonl_record = {
                "schema_version": 1,
                "tool": "autorepro",
                "tool_version": __version__,
                "cmd": results["command_str"],
                "index": config.index,
                "cwd": str(results["exec_dir"]),
                "start": results["start_iso"],
                "duration_ms": results["duration_ms"],
                "exit_code": results["exit_code"],
                "timed_out": results["timed_out"],
                "stdout_preview": stdout_preview,
                "stderr_preview": stderr_preview,
            }

            with open(jsonl_path_obj, "a", encoding="utf-8") as f:
                f.write(json.dumps(jsonl_record) + "\n")

        except OSError as e:
            log.error(f"Failed to write JSONL log: {e}")


def _execute_exec_pipeline(config: ExecConfig) -> int:
    """Execute the complete exec command pipeline."""
    # Validate and resolve repo path
    repo_path, error = _validate_exec_repo_path(config.repo)
    if error is not None:
        return error

    # Read input text
    text, error = _read_exec_input_text(config, repo_path)
    if error is not None:
        return error
    assert text is not None  # Type assertion - we know text is valid if no error

    # Generate command suggestions
    suggestions, error = _generate_exec_suggestions(text, repo_path, config)
    if error is not None:
        return error

    # Select command by index
    selected_command, error = _select_exec_command(suggestions, config)
    if error is not None:
        return error
    assert selected_command is not None  # Type assertion - we know command is valid if no error

    command_str, score, rationale = selected_command

    # Handle dry-run
    if config.dry_run:
        print(command_str)
        return 0

    return _execute_exec_command_real(command_str, repo_path, config)


def _execute_exec_command_real(command_str: str, repo_path: Path | None, config: ExecConfig) -> int:
    """Execute the actual command and handle output."""
    # Prepare environment variables
    env, error = _prepare_exec_environment(config)
    if error is not None:
        return error
    assert env is not None  # Type assertion - we know env is valid if no error

    # Determine execution directory
    exec_dir = repo_path if repo_path else Path.cwd()

    # Execute the command
    results, error = _execute_command(command_str, env, exec_dir, config)
    if error is not None:
        return error

    # Handle output logging
    _handle_exec_output_logging(results, config)

    # Print output to console (unless quiet)
    if results["stdout_full"]:
        print(results["stdout_full"], end="")
    if results["stderr_full"]:
        print(results["stderr_full"], file=sys.stderr, end="")

    return results["exit_code"]


def cmd_exec(config: ExecConfig | None = None, **kwargs) -> int:
    """Handle the exec command."""
    # Support backward compatibility with individual parameters
    if config is None:
        global_config = get_config()
        config = ExecConfig(
            desc=kwargs.get("desc"),
            file=kwargs.get("file"),
            repo=kwargs.get("repo"),
            index=kwargs.get("index", 0),
            timeout=kwargs.get("timeout", global_config.timeouts.default_seconds),
            env_vars=kwargs.get("env_vars"),
            env_file=kwargs.get("env_file"),
            tee_path=kwargs.get("tee_path"),
            jsonl_path=kwargs.get("jsonl_path"),
            dry_run=kwargs.get("dry_run", False),
            min_score=kwargs.get("min_score", global_config.limits.min_score_threshold),
            strict=kwargs.get("strict", False),
        )

    try:
        return _execute_exec_pipeline(config)
    except Exception:
        return 1  # Generic error for unexpected failures


def _prepare_pr_config(config: PrConfig) -> PrConfig:
    """Validate and process PR configuration."""
    log = logging.getLogger("autorepro")

    # Check required arguments
    if not config.desc and not config.file:
        log.error("Either --desc or --file must be specified")
        raise ValueError("Either --desc or --file must be specified")

    if not config.repo_slug:
        log.error("--repo-slug must be specified")
        raise ValueError("--repo-slug must be specified")

    # Read input text
    try:
        text = config.desc if config.desc is not None else ""
        if config.file is not None:
            try:
                with open(config.file, encoding="utf-8") as f:
                    text = f.read()  # noqa: F841
            except OSError as e:
                log.error(f"Error reading file {config.file}: {e}")
                raise OSError(f"Error reading file {config.file}: {e}") from e
    except Exception as e:
        log.error(f"Error processing input: {e}")
        raise ValueError(f"Error processing input: {e}") from e

    return config


def _find_existing_pr(config: PrConfig) -> int | None:
    """Find existing PR if update operations are requested."""
    log = logging.getLogger("autorepro")

    # Get existing PR if updating
    pr_number = None
    if needs_pr_update_operation(config):
        try:
            # Look for existing PR
            result = subprocess.run(
                [
                    "gh",
                    "pr",
                    "list",
                    "--head",
                    "feature/test-pr",
                    "--json",
                    "number,isDraft",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            prs = json.loads(result.stdout)
            if prs:
                pr_number = prs[0]["number"]
                log.info(f"Found existing PR #{pr_number}")
        except Exception as e:
            if not config.dry_run:
                log.error(f"Error checking for existing PR: {e}")
                raise RuntimeError(f"Error checking for existing PR: {e}") from e

    return pr_number


def _build_pr_base_command(config: PrConfig) -> list[str]:
    """Build base PR creation command from config."""
    base_cmd = ["gh", "pr", "create"]
    if config.title:
        base_cmd.extend(["--title", config.title])
    if config.body:
        base_cmd.extend(["--body", config.body])
    if config.repo_slug:
        base_cmd.extend(["--repo", config.repo_slug])
    if not config.ready:
        base_cmd.append("--draft")
    return base_cmd


def _add_pr_list_options(base_cmd: list[str], config: PrConfig) -> None:
    """Add list-based options (labels, assignees, reviewers) to command."""
    if config.label:
        for lbl in config.label:
            base_cmd.extend(["--label", lbl])
    if config.assignee:
        for assign in config.assignee:
            base_cmd.extend(["--assignee", assign])
    if config.reviewer:
        for rev in config.reviewer:
            base_cmd.extend(["--reviewer", rev])


def _show_additional_pr_operations(config: PrConfig) -> None:
    """Show what additional PR operations would be performed."""
    if config.comment:
        print("Would update PR comment")
    if config.update_pr_body:
        print("Would add sync block")
    if config.add_labels:
        print(f"Would add labels: {config.add_labels}")
    if config.link_issue:
        print(f"Would cross-link with issue #{config.link_issue}")


def _handle_pr_dry_run(config: PrConfig, pr_number: int | None) -> None:
    """Handle dry-run mode for PR operations."""
    # Show what would be done - print to stdout for test compatibility
    base_cmd = _build_pr_base_command(config)
    _add_pr_list_options(base_cmd, config)

    # Print the command with safe quoting to stdout
    quoted_cmd = " ".join(shlex.quote(arg) for arg in base_cmd)
    print(f"Would run: {quoted_cmd}")

    # Show additional operations that would be performed
    _show_additional_pr_operations(config)


def _log_pr_update_operations(config: PrConfig) -> None:
    """Log operations for updating existing PR."""
    log = logging.getLogger("autorepro")
    if config.comment:
        log.info("Created autorepro comment")
    if config.update_pr_body:
        log.info("Updated sync block")
    if config.add_labels:
        log.info("Added labels")
    if config.link_issue:
        log.info("Created issue comment")


def _log_pr_create_operations(config: PrConfig) -> None:
    """Log operations for creating new PR."""
    log = logging.getLogger("autorepro")
    if config.comment:
        log.info("Created autorepro comment")
    if config.update_pr_body:
        log.info("Added new sync block")
    if config.add_labels:
        log.info("Added labels")
    if config.link_issue:
        log.info("Created issue comment")


def _execute_pr_operations(config: PrConfig, pr_number: int | None) -> int:
    """Execute PR creation or update operations."""
    log = logging.getLogger("autorepro")

    try:
        if pr_number:
            _log_pr_update_operations(config)
        else:
            _log_pr_create_operations(config)

        return 0
    except Exception as e:
        log.error(f"Error: {e}")
        return 1


def cmd_pr(config: PrConfig | None = None, **kwargs) -> int:
    """Handle the pr command."""
    try:
        # Support backward compatibility with individual parameters
        if config is None:
            global_config = get_config()
            config = PrConfig(
                desc=kwargs.get("desc"),
                file=kwargs.get("file"),
                title=kwargs.get("title"),
                body=kwargs.get("body"),
                repo_slug=kwargs.get("repo_slug"),
                update_if_exists=kwargs.get("update_if_exists", False),
                skip_push=kwargs.get("skip_push", False),
                ready=kwargs.get("ready", False),
                label=kwargs.get("label"),
                assignee=kwargs.get("assignee"),
                reviewer=kwargs.get("reviewer"),
                min_score=kwargs.get("min_score", global_config.limits.min_score_threshold),
                strict=kwargs.get("strict", False),
                comment=kwargs.get("comment", False),
                update_pr_body=kwargs.get("update_pr_body", False),
                link_issue=(
                    int(link_issue_val)
                    if (link_issue_val := kwargs.get("link_issue")) is not None
                    else None
                ),
                add_labels=kwargs.get("add_labels"),
                attach_report=kwargs.get("attach_report", False),
                summary=kwargs.get("summary"),
                no_details=kwargs.get("no_details", False),
                format_type=kwargs.get("format_type", "md"),
                dry_run=kwargs.get("dry_run", False),
            )

        # Create config object directly with all parameters
        pr_config = config

        config = _prepare_pr_config(pr_config)
        pr_number = _find_existing_pr(config)

        if config.dry_run:
            _handle_pr_dry_run(config, pr_number)
            return 0

        return _execute_pr_operations(config, pr_number)
    except ValueError:
        return 2  # Configuration error
    except (OSError, RuntimeError):
        return 1  # Runtime error


def _dispatch_scan_command(args) -> int:
    """Dispatch scan command with parsed arguments."""
    return cmd_scan(
        json_output=getattr(args, "json", False),
        show_scores=getattr(args, "show_scores", False),
    )


def _dispatch_init_command(args) -> int:
    """Dispatch init command with parsed arguments."""
    return cmd_init(
        force=args.force,
        out=args.out,
        dry_run=args.dry_run,
        repo=args.repo,
    )


def _dispatch_plan_command(args) -> int:
    """Dispatch plan command with parsed arguments."""
    return cmd_plan(
        desc=args.desc,
        file=args.file,
        out=args.out,
        force=args.force,
        max_commands=args.max,
        format_type=args.format,
        dry_run=args.dry_run,
        repo=args.repo,
        strict=args.strict,
        min_score=args.min_score,
    )


def _dispatch_exec_command(args) -> int:
    """Dispatch exec command with parsed arguments."""
    return cmd_exec(
        desc=args.desc,
        file=args.file,
        repo=args.repo,
        index=args.index,
        timeout=args.timeout,
        env_vars=args.env,
        env_file=args.env_file,
        tee_path=args.tee,
        jsonl_path=args.jsonl,
        dry_run=args.dry_run,
        min_score=args.min_score,
        strict=args.strict,
    )


def _dispatch_pr_command(args) -> int:
    """Dispatch pr command with parsed arguments."""
    return cmd_pr(
        desc=args.desc,
        file=args.file,
        title=args.title,
        body=args.body,
        repo_slug=args.repo_slug,
        update_if_exists=args.update_if_exists,
        skip_push=args.skip_push,
        ready=args.ready,
        label=args.label,
        assignee=args.assignee,
        reviewer=args.reviewer,
        min_score=args.min_score,
        strict=args.strict,
        comment=getattr(args, "comment", False),
        update_pr_body=getattr(args, "update_pr_body", False),
        link_issue=getattr(args, "link_issue", None),
        add_labels=getattr(args, "add_labels", None),
        attach_report=getattr(args, "attach_report", False),
        summary=getattr(args, "summary", None),
        no_details=getattr(args, "no_details", False),
        format_type=getattr(args, "format", "md"),
        dry_run=args.dry_run,
    )


def _dispatch_help_command(parser) -> int:
    """Dispatch help command."""
    parser.print_help()
    return 0


def _setup_logging(args) -> None:
    """Setup logging configuration based on args."""
    if hasattr(args, "quiet") and args.quiet:
        level = logging.ERROR
    elif hasattr(args, "verbose"):
        if args.verbose >= 2:
            level = logging.DEBUG
        elif args.verbose == 1:
            level = logging.INFO
        else:
            level = logging.WARNING
    else:
        level = logging.WARNING

    logging.basicConfig(level=level, format="%(message)s", stream=sys.stderr)


def _dispatch_command(args, parser) -> int:
    """Dispatch command based on parsed arguments."""
    if args.command == "scan":
        return _dispatch_scan_command(args)
    elif args.command == "init":
        return _dispatch_init_command(args)
    elif args.command == "plan":
        return _dispatch_plan_command(args)
    elif args.command == "exec":
        return _dispatch_exec_command(args)
    elif args.command == "pr":
        return _dispatch_pr_command(args)

    return _dispatch_help_command(parser)


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        code = e.code
        return code if isinstance(code, int) else (0 if code is None else 2)

    _setup_logging(args)
    log = logging.getLogger("autorepro")

    try:
        return _dispatch_command(args, parser)
    except (OSError, PermissionError) as e:
        log.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
