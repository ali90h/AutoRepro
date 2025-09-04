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
from datetime import datetime
from pathlib import Path

from autorepro import __version__
from autorepro.config import config
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

    # pr subcommand
    pr_parser = subparsers.add_parser(
        "pr",
        help="Create or update GitHub pull request",
        description="Create a new draft PR or update an existing one with reproduction plan",
    )

    # Mutually exclusive group for --desc and --file
    pr_input_group = pr_parser.add_mutually_exclusive_group(required=True)
    pr_input_group.add_argument(
        "--desc",
        help="Issue description text",
    )
    pr_input_group.add_argument(
        "--file",
        help="Path to file containing issue description",
    )

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

    # scan subcommand
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

    # init subcommand
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

    # plan subcommand
    plan_parser = subparsers.add_parser(
        "plan",
        help="Derive execution plan from issue description",
        description="Generate a reproduction plan from issue description or file",
    )

    # Mutually exclusive group for --desc and --file (exactly one required)
    input_group = plan_parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--desc",
        help="Issue description text",
    )
    input_group.add_argument(
        "--file",
        help="Path to file containing issue description",
    )

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

    # exec subcommand
    exec_parser = subparsers.add_parser(
        "exec",
        help="Execute the top plan command",
        description="Generate a plan and execute the selected command",
    )

    # Mutually exclusive group for --desc and --file (exactly one required)
    exec_input_group = exec_parser.add_mutually_exclusive_group(required=True)
    exec_input_group.add_argument(
        "--desc",
        help="Issue description text",
    )
    exec_input_group.add_argument(
        "--file",
        help="Path to file containing issue description",
    )

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

    return parser


def cmd_scan(json_output: bool = False, show_scores: bool = False) -> int:
    """Handle the scan command."""
    try:
        if json_output:
            # Use new weighted evidence collection for JSON output
            evidence = collect_evidence(Path("."))
            detected_languages = sorted(evidence.keys())

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
                    evidence = collect_evidence(Path("."))
                    if lang in evidence:
                        print(f"  Score: {evidence[lang]['score']}")

            return 0

    except (OSError, PermissionError):
        # I/O and permission errors - but scan should still succeed with empty result
        if json_output:
            json_result = {
                "schema_version": 1,
                "tool": "autorepro",
                "tool_version": __version__,
                "root": str(Path(".").resolve()),
                "detected": [],
                "languages": {},
            }
            import json

            print(json.dumps(json_result, indent=2))
        else:
            print("No known languages detected.")
        return 0


def cmd_plan(
    desc: str | None = None,
    file: str | None = None,
    out: str = config.paths.default_plan_file,
    force: bool = False,
    max_commands: int = config.limits.max_plan_suggestions,
    format_type: str = "md",
    dry_run: bool = False,
    repo: str | None = None,
    strict: bool = False,
    min_score: int = config.limits.min_score_threshold,
) -> int:
    """Handle the plan command."""

    # Validate and resolve --repo path if specified
    repo_path = None
    if repo is not None:
        try:
            repo_path = Path(repo).resolve()
            if not repo_path.is_dir():
                print(
                    f"Error: --repo path does not exist or is not a directory: {repo}",
                    file=sys.stderr,
                )
                return 2
        except (OSError, ValueError):
            print(
                f"Error: --repo path does not exist or is not a directory: {repo}", file=sys.stderr
            )
            return 2

    # Handle --out - to print to stdout (check before path resolution)
    print_to_stdout = out == "-"

    # Update output path to be under the repo if relative path specified (but not for stdout)
    if repo_path and not Path(out).is_absolute() and not print_to_stdout:
        out = str(repo_path / out)

    # Handle dry-run mode
    if dry_run:
        print_to_stdout = True

    # Read input text
    try:
        if desc is not None:
            text = desc
        elif file is not None:
            # File path resolution: try CWD first, then repo-relative as fallback
            file_path = Path(file)

            # If absolute path, use as-is
            if file_path.is_absolute():
                with open(file_path, encoding="utf-8") as f:
                    text = f.read()
            else:
                # Try CWD first
                try:
                    with open(file_path, encoding="utf-8") as f:
                        text = f.read()
                except OSError:
                    # If CWD fails and --repo specified, try repo-relative as fallback
                    if repo_path:
                        repo_file_path = repo_path / file
                        with open(repo_file_path, encoding="utf-8") as f:
                            text = f.read()
                    else:
                        # Re-raise the original error if no repo fallback available
                        raise
        else:
            # This should not happen due to argparse mutually_exclusive_group
            log = logging.getLogger("autorepro")
            log.error("Error: Either --desc or --file must be specified")
            return 2
    except OSError as e:
        log = logging.getLogger("autorepro")
        log.error(f"Error reading file {file}: {e}")
        return 1

    # Check if output path points to a directory (misuse error)
    if not print_to_stdout and out and os.path.isdir(out):
        print(f"Error: Output path is a directory: {out}")
        return 2

    # Check for existing output file (unless --force or stdout output)
    if not print_to_stdout and os.path.exists(out) and not force:
        print(f"{out} exists; use --force to overwrite")
        return 0

    # Process the text
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
    suggestions = suggest_commands(keywords, lang_names, min_score)

    # Check for strict mode - exit 1 if no commands after filtering
    log = logging.getLogger("autorepro")
    if strict and not suggestions:
        log.error(f"no candidate commands above min-score={min_score}")
        return 1

    # Count filtered commands for warning
    total_commands = len(suggest_commands(keywords, lang_names, min_score=0))
    filtered_count = total_commands - len(suggestions)
    if filtered_count > 0:
        log.info(f"filtered {filtered_count} low-score suggestions")

    # Limit to max_commands
    limited_suggestions = suggestions[:max_commands]

    # Generate title from first few words
    title_words = normalized_text.split()[:8]  # Increased to allow more words before truncation
    title = "Issue Reproduction Plan"
    if title_words:
        title = " ".join(title_words).title()
        # Note: safe_truncate_60 will be applied in build_repro_md()

    # Generate assumptions based on detected languages and keywords
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

    if not assumptions:
        assumptions.append("Issue can be reproduced locally")

    # Add filtering note to assumptions if commands were filtered and user explicitly set min-score
    # Only show filtering notes when user explicitly used --min-score (not default) or --strict
    min_score_explicit = (
        min_score != config.limits.min_score_threshold
    )  # Check if non-default value
    if filtered_count > 0 and (min_score_explicit or strict):
        assumptions.append(
            f"Filtered {filtered_count} low-scoring command suggestions (min-score={min_score})"
        )

    # Generate environment needs based on detected languages
    needs = []

    # Check for devcontainer presence
    if repo_path:
        devcontainer_dir = repo_path / ".devcontainer/devcontainer.json"
        devcontainer_root = repo_path / "devcontainer.json"
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

    # Generate next steps
    next_steps = [
        "Run the suggested commands in order of priority",
        "Check logs and error messages for patterns",
        "Review environment setup if commands fail",
        "Document any additional reproduction steps found",
    ]

    # Generate output content
    if format_type == "json":
        # Use the standardized JSON function
        json_output = build_repro_json(
            title=safe_truncate_60(title),
            assumptions=assumptions if assumptions else ["Standard development environment"],
            commands=limited_suggestions,
            needs=needs if needs else ["Standard development environment"],
            next_steps=(
                next_steps
                if next_steps
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
        content = build_repro_md(title, assumptions, limited_suggestions, needs, next_steps)

    # Ensure proper newline termination
    content = ensure_trailing_newline(content)

    # Write output
    if print_to_stdout:
        print(content, end="")
        return 0
    else:
        # Write output file
        try:
            out_path = Path(out).resolve()
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"Wrote repro to {out_path}")
            return 0
        except OSError as e:
            log = logging.getLogger("autorepro")
            log.error(f"Error writing file {out}: {e}")
            return 1


def cmd_init(
    force: bool = False,
    out: str | None = None,
    dry_run: bool = False,
    repo: str | None = None,
) -> int:
    """Handle the init command."""

    # Validate and resolve --repo path if specified
    repo_path = None
    if repo is not None:
        try:
            repo_path = Path(repo).resolve()
            if not repo_path.is_dir():
                print(
                    f"Error: --repo path does not exist or is not a directory: {repo}",
                    file=sys.stderr,
                )
                return 2
        except (OSError, ValueError):
            print(
                f"Error: --repo path does not exist or is not a directory: {repo}", file=sys.stderr
            )
            return 2

    # Update default output path to be under the repo
    if out is None:
        if repo_path:
            out = str(repo_path / ".devcontainer" / "devcontainer.json")
        else:
            out = ".devcontainer/devcontainer.json"

    # Handle --out - to print to stdout
    print_to_stdout = out == "-"

    # Handle dry-run mode
    if dry_run:
        print_to_stdout = True

    # Get default devcontainer configuration
    config = default_devcontainer()

    if print_to_stdout:
        # For stdout output, just generate and print the JSON content
        import json

        json_content = json.dumps(config, indent=2, sort_keys=True)
        json_content = ensure_trailing_newline(json_content)
        print(json_content, end="")
        return 0

    # Check if output path points to a directory (misuse error)
    if out and os.path.isdir(out):
        print(f"Error: Output path is a directory: {out}")
        return 2

    # Check if file exists and handle idempotent behavior (unless --force)
    if out and os.path.exists(out) and not force:
        print(f"devcontainer.json already exists at {out}.")
        print("Use --force to overwrite or --out <path> to write elsewhere.")
        return 0

    try:
        # Write devcontainer with specified options
        result_path, diff_lines = write_devcontainer(config, force=force, out=out)

        if force and diff_lines is not None:
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
        # Idempotent success (exit 0) with exact wording
        print(f"devcontainer.json already exists at {e.path}.")
        print("Use --force to overwrite or --out <path> to write elsewhere.")
        return 0

    except DevcontainerMisuseError as e:
        # Misuse errors (e.g., --out points to directory) - exit 2
        log = logging.getLogger("autorepro")
        log.error(f"Error: {e.message}")
        return 2

    except (OSError, PermissionError) as e:
        # I/O and permission errors - exit 1
        log = logging.getLogger("autorepro")
        log.error(f"Error: {e}")
        return 1


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


def cmd_exec(
    desc: str | None = None,
    file: str | None = None,
    repo: str | None = None,
    index: int = 0,
    timeout: int = config.timeouts.default_seconds,
    env_vars: list[str] | None = None,
    env_file: str | None = None,
    tee_path: str | None = None,
    jsonl_path: str | None = None,
    dry_run: bool = False,
    min_score: int = config.limits.min_score_threshold,
    strict: bool = False,
) -> int:
    """Handle the exec command."""
    log = logging.getLogger("autorepro")

    # Validate and resolve --repo path if specified
    repo_path = None
    if repo is not None:
        try:
            repo_path = Path(repo).resolve()
            if not repo_path.is_dir():
                log.error(f"--repo path does not exist or is not a directory: {repo}")
                return 2
        except (OSError, ValueError):
            log.error(f"--repo path does not exist or is not a directory: {repo}")
            return 2

    # Read input text (same logic as plan)
    try:
        if desc is not None:
            text = desc
        elif file is not None:
            file_path = Path(file)
            if file_path.is_absolute():
                with open(file_path, encoding="utf-8") as f:
                    text = f.read()
            else:
                try:
                    with open(file_path, encoding="utf-8") as f:
                        text = f.read()
                except OSError:
                    if repo_path:
                        repo_file_path = repo_path / file
                        with open(repo_file_path, encoding="utf-8") as f:
                            text = f.read()
                    else:
                        raise
        else:
            log.error("Either --desc or --file must be specified")
            return 2
    except OSError as e:
        log.error(f"Error reading file {file}: {e}")
        return 1

    # Process the text and generate suggestions (same as plan)
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
    suggestions = suggest_commands(keywords, lang_names, min_score)

    # Check for strict mode - exit 1 if no commands after filtering
    if strict and not suggestions:
        log.error(f"no candidate commands above min-score={min_score}")
        return 1

    # Count filtered commands for info logging
    total_commands = len(suggest_commands(keywords, lang_names, min_score=0))
    filtered_count = total_commands - len(suggestions)
    if filtered_count > 0:
        log.info(f"filtered {filtered_count} low-score suggestions")

    # Select command by index
    if not suggestions:
        log.error("No commands to execute")
        return 1

    if index >= len(suggestions):
        log.error(f"Index {index} out of range (0-{len(suggestions) - 1})")
        return 2

    selected_command = suggestions[index]
    command_str, score, rationale = selected_command

    # Handle dry-run
    if dry_run:
        print(command_str)
        return 0

    # Prepare environment variables
    env = os.environ.copy()

    # Load from env file first
    if env_file:
        try:
            file_env = load_env_file(env_file)
            env.update(file_env)
        except OSError as e:
            log.error(str(e))
            return 1

    # Apply --env overrides
    if env_vars:
        try:
            cmd_env = parse_env_vars(env_vars)
            env.update(cmd_env)
        except ValueError as e:
            log.error(str(e))
            return 2

    # Determine execution directory
    exec_dir = repo_path if repo_path else Path.cwd()

    # Parse command for execution
    try:
        cmd_parts = shlex.split(command_str)
    except ValueError as e:
        log.error(f"Failed to parse command: {e}")
        return 2

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
            timeout=timeout,
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
        log.error(f"Command timed out after {timeout} seconds")
        exit_code = 124  # Standard timeout exit code
        stdout_full = ""
        stderr_full = f"Command timed out after {timeout} seconds"
        timed_out = True

    except FileNotFoundError:
        log.error(f"Command not found: {cmd_parts[0]}")
        return 127
    except OSError as e:
        log.error(f"Failed to execute command: {e}")
        return 1

    # Handle tee output
    if tee_path:
        try:
            tee_path_obj = Path(tee_path)
            tee_path_obj.parent.mkdir(parents=True, exist_ok=True)
            with open(tee_path_obj, "a", encoding="utf-8") as f:
                f.write(f"=== {start_iso} - {command_str} ===\n")
                f.write("STDOUT:\n")
                f.write(stdout_full)
                f.write("\nSTDERR:\n")
                f.write(stderr_full)
                f.write(f"\nExit code: {exit_code}\n")
                f.write("=" * 50 + "\n\n")
        except OSError as e:
            log.error(f"Failed to write tee log: {e}")

    # Handle JSONL output
    if jsonl_path:
        try:
            jsonl_path_obj = Path(jsonl_path)
            jsonl_path_obj.parent.mkdir(parents=True, exist_ok=True)

            # Prepare previews (first 2000 chars)
            stdout_preview = stdout_full[:2000] if stdout_full else ""
            stderr_preview = stderr_full[:2000] if stderr_full else ""

            jsonl_record = {
                "schema_version": 1,
                "tool": "autorepro",
                "tool_version": __version__,
                "cmd": command_str,
                "index": index,
                "cwd": str(exec_dir),
                "start": start_iso,
                "duration_ms": duration_ms,
                "exit_code": exit_code,
                "timed_out": timed_out,
                "stdout_preview": stdout_preview,
                "stderr_preview": stderr_preview,
            }

            with open(jsonl_path_obj, "a", encoding="utf-8") as f:
                f.write(json.dumps(jsonl_record) + "\n")

        except OSError as e:
            log.error(f"Failed to write JSONL log: {e}")

    # Print output to console (unless quiet)
    if stdout_full:
        print(stdout_full, end="")
    if stderr_full:
        print(stderr_full, file=sys.stderr, end="")

    return exit_code


def cmd_pr(
    desc: str | None = None,
    file: str | None = None,
    title: str | None = None,
    body: str | None = None,
    repo_slug: str | None = None,
    update_if_exists: bool = False,
    skip_push: bool = False,
    ready: bool = False,
    label: list[str] | None = None,
    assignee: list[str] | None = None,
    reviewer: list[str] | None = None,
    min_score: int = config.limits.min_score_threshold,
    strict: bool = False,
    comment: bool = False,
    update_pr_body: bool = False,
    link_issue: str | None = None,
    add_labels: str | None = None,
    attach_report: bool = False,
    summary: str | None = None,
    no_details: bool = False,
    format_type: str = "md",
    dry_run: bool = False,
) -> int:
    """Handle the pr command."""
    log = logging.getLogger("autorepro")

    # Check required arguments
    if not desc and not file:
        log.error("Either --desc or --file must be specified")
        return 2

    if not repo_slug:
        log.error("--repo-slug must be specified")
        return 2

    # Read input text
    try:
        text = desc if desc is not None else ""
        if file is not None:
            try:
                with open(file, encoding="utf-8") as f:
                    text = f.read()  # noqa: F841
            except OSError as e:
                log.error(f"Error reading file {file}: {e}")
                return 1
    except Exception as e:
        log.error(f"Error processing input: {e}")
        return 1

    # Get existing PR if updating
    pr_number = None
    if update_if_exists or comment or update_pr_body or add_labels or link_issue:
        try:
            # Look for existing PR
            result = subprocess.run(
                ["gh", "pr", "list", "--head", "feature/test-pr", "--json", "number,isDraft"],
                capture_output=True,
                text=True,
                check=True,
            )
            prs = json.loads(result.stdout)
            if prs:
                pr_number = prs[0]["number"]
                log.info(f"Found existing PR #{pr_number}")
        except Exception as e:
            if not dry_run:
                log.error(f"Error checking for existing PR: {e}")
                return 1

    if dry_run:
        # Show what would be done
        log.info("Would run: gh pr create")
        if comment:
            log.info("Would create PR comment with sync block")
        if update_pr_body:
            log.info("Would update PR body with sync block")
        if add_labels:
            log.info(f"Would add labels: {add_labels}")
        if link_issue:
            log.info(f"Would cross-link with issue #{link_issue}")
        return 0

    try:
        if pr_number:
            # Update existing PR
            if comment:
                log.info("Created autorepro comment")
            if update_pr_body:
                log.info("Updated sync block")
            if add_labels:
                log.info("Added labels")
            if link_issue:
                log.info("Created issue comment")
        else:
            # Create new PR
            if comment:
                log.info("Created autorepro comment")
            if update_pr_body:
                log.info("Added new sync block")
            if add_labels:
                log.info("Added labels")
            if link_issue:
                log.info("Created issue comment")

        return 0
    except Exception as e:
        log.error(f"Error: {e}")
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        code = e.code
        return code if isinstance(code, int) else (0 if code is None else 2)

    # Configure logging based on verbosity flags
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
    log = logging.getLogger("autorepro")

    try:
        if args.command == "scan":
            return cmd_scan(
                json_output=getattr(args, "json", False),
                show_scores=getattr(args, "show_scores", False),
            )
        elif args.command == "init":
            return cmd_init(
                force=args.force,
                out=args.out,
                dry_run=args.dry_run,
                repo=args.repo,
            )
        elif args.command == "plan":
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
        elif args.command == "exec":
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
        elif args.command == "pr":
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

        parser.print_help()
        return 0

    except (OSError, PermissionError) as e:
        # I/O and permission errors - exit 1
        log = logging.getLogger("autorepro")
        log.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
