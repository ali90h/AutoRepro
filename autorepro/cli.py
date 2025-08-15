#!/usr/bin/env python3
"""AutoRepro CLI - Command line interface for AutoRepro."""

import argparse
import sys


def create_parser():
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        prog="autorepro",
        description="CLI for AutoRepro - transforms issue descriptions into clear repro steps and shareable workspaces",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
AutoRepro automatically detects repository technologies, generates ready-made devcontainers,
and writes prioritized repro plans with explicit assumptions.

MVP commands (coming soon):
  scan    Detect languages/frameworks from file pointers
  init    Create an installer devcontainer  
  plan    Derive execution plan from issue description

For more information, visit: https://github.com/ali90h/AutoRepro
        """.strip()
    )
    
    return parser


def main():
    """Main entry point for the autorepro CLI."""
    parser = create_parser()
    
    # If no arguments provided, show help and exit with code 0
    if len(sys.argv) == 1:
        parser.print_help()
        return 0
    
    # Parse arguments
    try:
        args = parser.parse_args()
        # Since we only support help at this stage, this shouldn't be reached
        # unless -h/--help was used, which argparse handles automatically
        parser.print_help()
        return 0
    except SystemExit as e:
        # argparse calls sys.exit() for -h/--help, we want to return the code
        return e.code if e.code is not None else 0


if __name__ == "__main__":
    sys.exit(main())