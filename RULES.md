# AutoRepro – General Engineering Rules

These rules apply universally to any code, feature, or enhancement added to the project. They form the baseline “constitution” of development.

## Design & Structure

- **Argument grouping:** Any function requiring more than 4 related arguments must wrap them in a dedicated config object (`dataclass` or equivalent).
- **Single Responsibility Principle:** Large or multi-purpose functions/classes must be decomposed into focused services or helpers.
- **Extract Method:** Functions exceeding ~50 statements must be split into smaller units; avoid monolithic “god functions.”
- **File/function size limits:**
Files: under 500 lines.
Functions: under 80–100 lines.
Apply branch-by-abstraction if necessary.

## CLI & User Interface

- **Centralized validation:** CLI argument validation and defaults must come exclusively from shared modules (`cli_validation.py`, `defaults.py`, `argument_groups.py`). No inline ad-hoc checks.
- **Smoke tests required:** Any CLI command or flag change must include standardized smoke tests (`pytest -m smoke -q`).
- **Help text:** Help messages must be centralized in constants/config, follow a consistent format, and be covered by validation tests.
- **I/O helpers:** All CLI I/O operations must go through centralized helpers (`io_read`, `io_write`, `print_err`). No direct `print()`/`open()` scattered in the codebase.
- **No print in core:** `print()` is only allowed in CLI output functions. All other messages go through structured logging.

## Configuration & Validation

- **Self-validating configs:** Every config/dataclass must include a `validate()` method ensuring internal consistency, proper ranges, and mutual exclusivity of fields.
- **Standard error handling:** All subprocess and file operations must go through utilities (`safe_subprocess_run`, `safe_file_operation`) with consistent exception classes and messages.

## Documentation & Readability

- **Docstring standards:**

- Module-level one-liners must be single-line with quotes.
- All public functions and exception `__init__` methods must have descriptive docstrings (NumPy/Google style).
- Docstrings must follow PEP 257: summary line ends with a period, blank line before description, imperative mood.
- Every` __init__.py` (including test packages) must contain a descriptive package docstring.

## Testing

- **Failure path coverage:** Code is not complete unless failure cases (timeouts, subprocess errors, bad inputs) are tested alongside success paths.
- **Shared test utilities:** Common setup, teardown, fixtures, mocks, and temp file logic must be centralized under `tests/utils/` instead of duplicated.

## Quality & Tooling

- **Linting is law:** Ruff rules for complexity/length must be strictly enforced; no violations allowed.
- **Refactoring discipline:** Any style/complexity fix (C901, E501, etc.) must be accompanied by additional tests that prove unchanged behavior.
- **Type safety:** All functions require strict type hints; no `Any` or `object` unless absolutely necessary. Use Generics, Protocols, and Literals where appropriate. CI enforces MyPy strict mode.
- **CI barriers:** Continuous integration enforces Ruff, pytest (including goldens), and file size checks (`>500 LOC` → fail). No merges allowed if barriers fail.
- **Logging standardization:** Use a centralized logging utility with consistent format, levels, and context.
