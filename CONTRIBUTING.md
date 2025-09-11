# Contributing to AutoRepro

Thanks for contributing! This project enforces automated formatting, linting, docstring cleanup, and type checks using Python 3.11.

## Quick Start

1. Install tooling
   - Python 3.11
   - `pip install -e .[dev]`
   - `pip install pre-commit`

2. Enable pre-commit hooks
   - `pre-commit install`

3. Normalize the repo once (optional but recommended)
   - `pre-commit run --all-files`

## Tooling

- Formatter: Black (line-length 88)
- Linter: Ruff (autofix; import sorting)
- Docstrings: docformatter (wrap to 88)
- Types: mypy (moderately strict)
- Logging: centralized utility with JSON or key=value formats

Configuration lives in `pyproject.toml` (Black, Ruff, docformatter) and `mypy.ini`.

### Logging

- Use `logging.getLogger("autorepro")` or `from autorepro.utils.logging import get_logger`.
- Configure once via CLI; locally you can force structured logs with `AUTOREPRO_LOG_FORMAT=json`.
- Context: prefer passing `extra={"operation": "..."}` or `get_logger(name, operation="...")` so logs carry structured context.

### Mypy strictness ratchet

We use an incremental approach to tighten type checks. See `docs/mypy-ratchet.md` for the current allowlist and how to add modules under stricter rules.

## CI

GitHub Actions enforces pre-commit on PRs and pushes to `main`. Ensure hooks pass locally to avoid CI failures.

## Updating Hooks

- Run `pre-commit autoupdate` locally and open a PR.
