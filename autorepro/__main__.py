"""Entry point for running autorepro as a module."""

from .cli import main

if __name__ == "__main__":  # pragma: no cover
    import sys

    sys.exit(main())
