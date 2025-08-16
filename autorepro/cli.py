#!/usr/bin/env python3
"""AutoRepro CLI - Command line interface for AutoRepro."""

import argparse
import sys

from autorepro import __version__
from autorepro.detect import detect_languages


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
  init    Create a developer container (coming soon)
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


def main() -> int:
    parser = create_parser()
    try:
        args = parser.parse_args()
    except SystemExit as e:
        code = e.code
        return code if isinstance(code, int) else (0 if code is None else 2)

    if args.command == "scan":
        return cmd_scan()

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
