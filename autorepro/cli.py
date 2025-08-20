#!/usr/bin/env python3
"""AutoRepro CLI - Command line interface for AutoRepro."""

import argparse
import sys
from pathlib import Path

from autorepro import __version__
from autorepro.detect import detect_languages
from autorepro.env import (
    DevcontainerExistsError,
    DevcontainerMisuseError,
    default_devcontainer,
    write_devcontainer,
)


def create_parser():
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
  plan    Derive execution plan from issue description (coming soon)

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
        print(f"- {lang}  -> {reasons_str}")

    return 0


def cmd_init(force: bool = False, out: str | None = None) -> int:
    """Handle the init command."""
    # Get default devcontainer configuration
    config = default_devcontainer()

    try:
        # Determine output path to check if file exists before writing
        if out is None:
            output_path = Path(".devcontainer") / "devcontainer.json"
            file_existed = output_path.exists()
        else:
            try:
                output_path = Path(out).resolve()
                file_existed = output_path.exists()
            except (OSError, ValueError):
                # Let env.py handle path validation errors
                file_existed = False

        # Write devcontainer with specified options
        result_path, diff_lines = write_devcontainer(config, force=force, out=out)

        if force and file_existed:
            print(f"Overwrote devcontainer at {result_path}")
            if diff_lines is not None:
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
        return cmd_init(force=args.force, out=args.out)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
