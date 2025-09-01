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
from autorepro.pr import (
    build_pr_body,
    build_pr_title,
    create_or_update_pr,
    detect_repo_slug,
    ensure_pushed,
    generate_plan_data,
)
from autorepro.report import collect_env_info, maybe_exec, pack_zip, write_plan


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

For more information, visit: https://github.com/ali90h/AutoRepro
        """.strip(),
    )

    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    # Add subcommands
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

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
        default="repro.md",
        help="Output path (default: repro.md)",
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

    # report subcommand
    report_parser = subparsers.add_parser(
        "report",
        help="Combine plan + run log + environment metadata into zip artifact",
        description=(
            "Generate a comprehensive report bundle with plan, execution logs, "
            "and environment info"
        ),
    )

    # Mutually exclusive group for --desc and --file (exactly one required)
    report_input_group = report_parser.add_mutually_exclusive_group(required=True)
    report_input_group.add_argument(
        "--desc",
        help="Issue description text",
    )
    report_input_group.add_argument(
        "--file",
        help="Path to file containing issue description",
    )

    report_parser.add_argument(
        "--repo",
        help="Execute logic on specified repository path",
    )
    report_parser.add_argument(
        "--min-score",
        type=int,
        default=2,
        help="Drop commands with score < N (default: 2)",
    )
    report_parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if no commands make the cut after filtering",
    )
    report_parser.add_argument(
        "--format",
        choices=["md", "json"],
        default="md",
        help="Output format for plan (default: md)",
    )
    report_parser.add_argument(
        "--out",
        default="out/repro_bundle.zip",
        help="Output zip file path (default: out/repro_bundle.zip)",
    )
    report_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be packaged without creating zip file",
    )
    report_parser.add_argument(
        "--exec",
        action="store_true",
        help="Execute the best command before packaging",
    )
    report_parser.add_argument(
        "--index",
        type=int,
        default=0,
        help="Pick the N-th suggested command when using --exec (default: 0 = top)",
    )
    report_parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Command timeout in seconds when using --exec (default: 120)",
    )
    report_parser.add_argument(
        "--env",
        action="append",
        default=[],
        help="Set environment variable KEY=VAL when using --exec (repeatable)",
    )
    report_parser.add_argument(
        "--env-file",
        help="Load environment variables from file when using --exec",
    )
    report_parser.add_argument(
        "--tee",
        help="Append full stdout/stderr to log file when using --exec",
    )
    report_parser.add_argument(
        "--jsonl",
        help="Append JSON line record per run when using --exec",
    )
    report_parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Show errors only",
    )
    report_parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v, -vv)",
    )

    # pr subcommand
    pr_parser = subparsers.add_parser(
        "pr",
        help="Create Draft PR from reproduction plan",
        description="Automatically create GitHub Draft PR with reproduction plan content",
    )

    # Mutually exclusive group for --desc and --file (exactly one required)
    pr_input_group = pr_parser.add_mutually_exclusive_group(required=True)
    pr_input_group.add_argument(
        "--desc",
        help="Issue description text",
    )
    pr_input_group.add_argument(
        "--file",
        help="Path to file containing issue description",
    )

    pr_parser.add_argument(
        "--repo",
        help="Execute logic on specified repository path",
    )
    pr_parser.add_argument(
        "--title",
        help="Custom PR title (default: auto-generated from plan)",
    )
    pr_parser.add_argument(
        "--body",
        help="Custom PR body file or '-' for stdin (default: auto-generated from plan)",
    )
    pr_parser.add_argument(
        "--format",
        choices=["md", "json"],
        default="md",
        help="Source format for auto-generating PR body (default: md)",
    )
    pr_parser.add_argument(
        "--base",
        default="main",
        help="Target branch for PR (default: main)",
    )
    pr_parser.add_argument(
        "--draft",
        action="store_true",
        default=True,
        help="Create as draft PR (default: true)",
    )
    pr_parser.add_argument(
        "--ready",
        action="store_true",
        help="Create as ready PR (not draft)",
    )
    pr_parser.add_argument(
        "--update-if-exists",
        action="store_true",
        help="Update existing draft PR from same branch instead of creating new",
    )
    pr_parser.add_argument(
        "--label",
        action="append",
        default=[],
        help="Add label to PR (repeatable)",
    )
    pr_parser.add_argument(
        "--assignee",
        action="append",
        default=[],
        help="Assign user to PR (repeatable)",
    )
    pr_parser.add_argument(
        "--reviewer",
        action="append",
        default=[],
        help="Request review from user (repeatable)",
    )
    pr_parser.add_argument(
        "--gh",
        default="gh",
        help="Path to gh CLI tool (default: gh from PATH)",
    )
    pr_parser.add_argument(
        "--repo-slug",
        help="Repository slug (owner/repo) to bypass git remote detection",
    )
    pr_parser.add_argument(
        "--skip-push",
        action="store_true",
        help="Skip pushing branch to origin (useful for testing or locked environments)",
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
        help="Exit with code 1 if no commands make the cut after filtering",
    )
    pr_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what GitHub CLI commands would be executed without running them",
    )
    pr_parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Show errors only",
    )
    pr_parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (-v, -vv)",
    )

    return parser


def cmd_scan(json_output: bool = False, show_scores: bool = False, verbose: bool = False) -> int:
    """Handle the scan command."""
    log = logging.getLogger("autorepro")
    root = Path(".").resolve()

    try:
        if json_output:
            # Use new weighted evidence collection for JSON output
            evidence = collect_evidence(Path("."))
            detected_languages = sorted(evidence.keys())

            # Add verbose logging
            if verbose:
                detected_str = ", ".join(detected_languages) or "none"
                log.info(f"scanned {root} → detected: {detected_str}")

            # Build JSON output according to schema
            json_result = {
                "schema_version": 1,
                "tool": "autorepro",
                "tool_version": __version__,
                "root": str(root),
                "detected": detected_languages,
                "languages": evidence,
            }

            import json

            print(json.dumps(json_result, indent=2))
            return 0
        else:
            # Use legacy text output
            detected = detect_languages(".")

            # Add verbose logging for text mode
            if verbose:
                if detected:
                    languages = [lang for lang, _ in detected]
                    detected_str = ", ".join(languages)
                else:
                    detected_str = "none"
                log.info(f"scanned {root} → detected: {detected_str}")

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
        if verbose:
            log.info(f"scanned {root} → detected: none")

        if json_output:
            json_result = {
                "schema_version": 1,
                "tool": "autorepro",
                "tool_version": __version__,
                "root": str(root),
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
    out: str = "repro.md",
    force: bool = False,
    max_commands: int = 5,
    format_type: str = "md",
    dry_run: bool = False,
    repo: str | None = None,
    strict: bool = False,
    min_score: int = 2,
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
    min_score_explicit = min_score != 2  # 2 is the default value
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
    timeout: int = 120,
    env_vars: list[str] | None = None,
    env_file: str | None = None,
    tee_path: str | None = None,
    jsonl_path: str | None = None,
    dry_run: bool = False,
    min_score: int = 2,
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


def cmd_report(
    desc: str | None = None,
    file: str | None = None,
    repo: str | None = None,
    min_score: int = 2,
    strict: bool = False,
    format_type: str = "md",
    out: str = "out/repro_bundle.zip",
    dry_run: bool = False,
    exec_enabled: bool = False,
    index: int = 0,
    timeout: int = 120,
    env_vars: list[str] | None = None,
    env_file: str | None = None,
    tee_path: str | None = None,
    jsonl_path: str | None = None,
) -> int:
    """Handle the report command."""
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
    else:
        repo_path = Path.cwd()

    # Check if output path points to a directory (misuse error)
    out_path = Path(out)
    if not out_path.suffix:
        # If no extension, assume it's a directory and append default filename
        out_path = out_path / "repro_bundle.zip"

    if out_path.exists() and out_path.is_dir():
        log.error(f"Output path is a directory: {out_path}")
        return 2

    # Prepare input for functions
    desc_or_file = desc if desc is not None else file

    try:
        # Read and process input text to check candidates for strict mode
        if desc_or_file and Path(desc_or_file).exists():
            # Try to read as file
            file_path = Path(desc_or_file)
            if file_path.is_absolute():
                with open(file_path, encoding="utf-8") as f:
                    text = f.read()
            else:
                try:
                    with open(file_path, encoding="utf-8") as f:
                        text = f.read()
                except OSError:
                    if repo_path != Path.cwd():
                        repo_file_path = repo_path / desc_or_file
                        with open(repo_file_path, encoding="utf-8") as f:
                            text = f.read()
                    else:
                        raise
        else:
            text = desc_or_file or ""

        # Process text to get candidates for strict checking
        original_cwd = Path.cwd()
        os.chdir(repo_path)

        try:
            normalized_text = normalize(text)
            keywords = extract_keywords(normalized_text)
            detected_languages = detect_languages(".")
            lang_names = [lang for lang, _ in detected_languages]

            # Check candidates for strict mode
            candidates = suggest_commands(keywords, lang_names, min_score)
            if strict and not candidates:
                log.error(f"no candidate commands above min-score={min_score}")
                return 1

        finally:
            os.chdir(original_cwd)

        # Generate plan
        log.info("Generating reproduction plan...")
        plan_path, plan_content = write_plan(repo_path, desc_or_file, format_type)

        # Collect environment information
        log.info("Collecting environment information...")
        env_info = collect_env_info(repo_path)

        # Prepare files for zip
        files: dict[str, Path | str | bytes] = {}

        # Add plan file
        plan_filename = f"repro.{format_type}"
        files[plan_filename] = plan_content

        # Add environment info
        files["ENV.txt"] = env_info

        # Optionally execute command
        exec_exit_code = 0
        if exec_enabled:
            log.info("Executing selected command...")
            exec_opts = {
                "exec": True,
                "desc": desc,
                "file": file,
                "index": index,
                "timeout": timeout,
                "env": env_vars or [],
                "env_file": env_file,
                "tee": tee_path,
                "jsonl": jsonl_path,
                "min_score": min_score,
                "strict": strict,
            }

            exec_exit_code, log_path, jsonl_log_path = maybe_exec(repo_path, exec_opts)

            # Add execution logs to zip
            if log_path and log_path.exists():
                files["run.log"] = log_path
            if jsonl_log_path and jsonl_log_path.exists():
                files["runs.jsonl"] = jsonl_log_path

        if dry_run:
            print("Report bundle contents:")
            for filename, content in files.items():
                if isinstance(content, Path):
                    print(f"  {filename} -> {content}")
                else:
                    size = len(content) if isinstance(content, str | bytes) else "unknown"
                    print(f"  {filename} ({size} chars)")
            return 0

        # Handle --out - (stdout output)
        if out == "-":
            print("CONTENTS:")
            for filename in files.keys():
                print(f"- {filename}")
            return 0

        # Create zip bundle
        pack_zip(out_path, files)

        log.info(f"Report bundle created: {out_path}")

        # Clean up temp files
        if plan_path.exists():
            plan_path.unlink()

        # Return appropriate exit code
        # If --exec was used, return subprocess exit code while still creating zip
        # Requirements state: "If --exec is enabled: Return the subprocess code as the exit code"
        if exec_enabled:
            return exec_exit_code
        else:
            return 0

    except OSError as e:
        log.error(f"I/O error: {e}")
        return 1
    except Exception as e:
        log.error(f"Error creating report bundle: {e}")
        return 1


def cmd_pr(
    desc: str | None = None,
    file: str | None = None,
    repo: str | None = None,
    title: str | None = None,
    body: str | None = None,
    format_type: str = "md",
    base: str = "main",
    draft: bool = True,
    ready: bool = False,
    update_if_exists: bool = False,
    labels: list[str] | None = None,
    assignees: list[str] | None = None,
    reviewers: list[str] | None = None,
    gh_path: str = "gh",
    repo_slug: str | None = None,
    skip_push: bool = False,
    min_score: int = 2,
    strict: bool = False,
    dry_run: bool = False,
) -> int:
    """Handle the pr command."""
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
    else:
        repo_path = Path.cwd()

    # Prepare input for plan generation
    desc_or_file = desc if desc is not None else file

    try:
        # Check repository slug detection
        if repo_slug:
            log.info(f"Using provided repository: {repo_slug}")
        else:
            try:
                repo_slug = detect_repo_slug()
                log.info(f"Detected repository: {repo_slug}")
            except RuntimeError as e:
                log.error(f"Failed to detect GitHub repository: {e}")
                log.error("Try: git remote add origin https://github.com/owner/repo.git")
                log.error("Or use: --repo-slug owner/repo to specify manually")
                return 1

        # Early strict mode checking (like in report command)
        if strict:
            # Read and process input text to check candidates
            if desc_or_file and Path(desc_or_file).exists():
                file_path = Path(desc_or_file)
                if file_path.is_absolute():
                    with open(file_path, encoding="utf-8") as f:
                        text = f.read()
                else:
                    try:
                        with open(file_path, encoding="utf-8") as f:
                            text = f.read()
                    except OSError:
                        if repo_path != Path.cwd():
                            repo_file_path = repo_path / desc_or_file
                            with open(repo_file_path, encoding="utf-8") as f:
                                text = f.read()
                        else:
                            raise
            else:
                text = desc_or_file or ""

            # Check candidates for strict mode
            original_cwd = Path.cwd()
            os.chdir(repo_path)

            try:
                normalized_text = normalize(text)
                keywords = extract_keywords(normalized_text)
                detected_languages = detect_languages(".")
                lang_names = [lang for lang, _ in detected_languages]

                candidates = suggest_commands(keywords, lang_names, min_score)
                if not candidates:
                    log.error(f"no candidate commands above min-score={min_score}")
                    return 1

            finally:
                os.chdir(original_cwd)

        # Generate plan data if no custom title/body provided
        custom_title = title
        custom_body = body

        if not custom_title or not custom_body:
            log.info("Generating reproduction plan...")
            plan_content, plan_format = generate_plan_data(
                repo_path, desc_or_file, format_type, min_score
            )

        # Determine if creating draft (--ready overrides --draft)
        is_draft = draft and not ready

        # Build PR title
        if custom_title:
            pr_title = custom_title
        else:
            if format_type == "json":
                import json

                plan_data = json.loads(plan_content)
                pr_title = build_pr_title(plan_data, is_draft)
            else:
                # Extract title from markdown
                title_line = next(
                    (line for line in plan_content.split("\n") if line.startswith("# ")),
                    "# Issue Reproduction Plan",
                )
                plan_title = title_line[2:].strip()
                suffix = " [draft]" if is_draft else ""
                pr_title = f"chore(repro): {safe_truncate_60(plan_title)}{suffix}"

        # Build PR body
        if custom_body:
            if custom_body == "-":
                # Read from stdin
                import sys

                pr_body = sys.stdin.read()
            else:
                # Read from file
                with open(custom_body, encoding="utf-8") as f:
                    pr_body = f.read()
        else:
            pr_body = build_pr_body(plan_content, format_type)

        # Get current branch
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                check=True,
            )
            current_branch = result.stdout.strip()

            if not current_branch:
                log.error("Not on a named branch")
                return 1

        except subprocess.CalledProcessError as e:
            log.error(f"Failed to get current branch: {e}")
            return 1

        # Ensure branch is pushed
        if not dry_run and not skip_push:
            try:
                pushed = ensure_pushed(current_branch)
                if pushed:
                    log.info(f"Pushed branch {current_branch} to origin")
                else:
                    log.info(f"Branch {current_branch} already up to date")
            except RuntimeError as e:
                log.error(f"Push to origin failed: {e}")
                log.error(f"Try: git push -u origin {current_branch}")
                log.error("Or check: gh auth status")
                log.error("Or use: --skip-push for testing without pushing")
                return 1
        elif skip_push:
            # Check if branch exists on remote when skipping push
            try:
                result = subprocess.run(
                    ["git", "ls-remote", "--heads", "origin", current_branch],
                    capture_output=True,
                    text=True,
                )
                remote_exists = bool(result.stdout.strip())

                if not remote_exists and not dry_run:
                    log.error(f"Branch {current_branch} does not exist on origin")
                    log.error(f"Push required: git push -u origin {current_branch}")
                    log.error("Or remove --skip-push to auto-push")
                    return 1

            except subprocess.CalledProcessError:
                if not dry_run:
                    log.warning(f"Could not check if {current_branch} exists on origin")
                    log.warning("PR creation may fail if branch is not pushed")

        # Create or update PR
        exit_code, created_new = create_or_update_pr(
            title=pr_title,
            body=pr_body,
            base_branch=base,
            head_branch=current_branch,
            draft=is_draft,
            labels=labels or [],
            assignees=assignees or [],
            reviewers=reviewers or [],
            update_if_exists=update_if_exists,
            gh_path=gh_path,
            dry_run=dry_run,
        )

        if exit_code == 0 and not dry_run:
            action = "Created" if created_new else "Updated"
            pr_type = "draft" if is_draft else "ready"
            log.info(f"{action} {pr_type} PR from branch {current_branch}")

        return exit_code

    except OSError as e:
        log.error(f"I/O error: {e}")
        return 1
    except Exception as e:
        log.error(f"Error creating PR: {e}")
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
                verbose=getattr(args, "verbose", 0) > 0,
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
        elif args.command == "report":
            return cmd_report(
                desc=args.desc,
                file=args.file,
                repo=args.repo,
                min_score=args.min_score,
                strict=args.strict,
                format_type=args.format,
                out=args.out,
                dry_run=args.dry_run,
                exec_enabled=getattr(args, "exec", False),
                index=getattr(args, "index", 0),
                timeout=getattr(args, "timeout", 120),
                env_vars=getattr(args, "env", []),
                env_file=getattr(args, "env_file", None),
                tee_path=getattr(args, "tee", None),
                jsonl_path=getattr(args, "jsonl", None),
            )
        elif args.command == "pr":
            return cmd_pr(
                desc=args.desc,
                file=args.file,
                repo=args.repo,
                title=args.title,
                body=args.body,
                format_type=args.format,
                base=args.base,
                draft=args.draft,
                ready=args.ready,
                update_if_exists=getattr(args, "update_if_exists", False),
                labels=getattr(args, "label", []),
                assignees=getattr(args, "assignee", []),
                reviewers=getattr(args, "reviewer", []),
                gh_path=args.gh,
                repo_slug=getattr(args, "repo_slug", None),
                skip_push=getattr(args, "skip_push", False),
                min_score=args.min_score,
                strict=args.strict,
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
