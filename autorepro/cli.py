#!/usr/bin/env python3
"""AutoRepro CLI - Command line interface for AutoRepro."""

from __future__ import annotations

import argparse
import os
import sys
from contextlib import contextmanager
from pathlib import Path

from autorepro import __version__
from autorepro.detect import detect_languages
from autorepro.env import (
    DevcontainerExistsError,
    DevcontainerMisuseError,
    default_devcontainer,
    write_devcontainer,
)
from autorepro.planner import (
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
def temp_chdir(path: Path):
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
    subparsers.add_parser(
        "scan",
        help="Detect languages/frameworks from file pointers",
        description="Scan the current directory for language/framework indicators",
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

    return parser


def cmd_scan() -> int:
    """Handle the scan command."""
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
            print("Error: Either --desc or --file must be specified", file=sys.stderr)
            return 2
    except OSError as e:
        print(f"Error reading file {file}: {e}", file=sys.stderr)
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
    suggestions = suggest_commands(keywords, lang_names)

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

    # Generate environment needs based on detected languages
    needs = []
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
        # JSON Schema format
        json_output = {
            "title": safe_truncate_60(title),
            "assumptions": assumptions if assumptions else ["Standard development environment"],
            "commands": [
                {"command": cmd, "score": score, "rationale": rationale}
                for cmd, score, rationale in limited_suggestions
            ],
            "needs": needs if needs else ["Standard development environment"],
            "next_steps": next_steps
            if next_steps
            else [
                "Run the highest-score command",
                "If it fails: switch to the second",
                "Record brief logs in report.md",
            ],
        }

        import json

        content = json.dumps(json_output, indent=2, sort_keys=True)
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
            print(f"Error writing file {out}: {e}", file=sys.stderr)
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
            print(f"Overwrote devcontainer to {result_path}")
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
        print(f"Error: {e.message}")
        return 2

    except (OSError, PermissionError) as e:
        # I/O and permission errors - exit 1
        print(f"Error: {e}")
        return 1


def main() -> int:
    parser = create_parser()
    try:
        args = parser.parse_args()
    except SystemExit as e:
        code = e.code
        return code if isinstance(code, int) else (0 if code is None else 2)

    if args.command == "scan":
        return cmd_scan()
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
        )

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
